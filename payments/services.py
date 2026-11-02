from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from notifications.services import notify_user

from .models import Payment


class PaymentProcessingError(Exception):
    pass


class MockPaymentProvider:
    """Development stand-in for a real gateway.

    It never touches real money; it simply issues a deterministic-looking
    reference so the rest of the order flow can be exercised end to end.
    """

    name = "mock"

    def charge(self, order):
        return f"MOCK-{order.pk}-{uuid4().hex.upper()}"

    def refund(self, payment, amount):
        return f"REF-{payment.pk}-{uuid4().hex[:12].upper()}"


def get_provider():
    if settings.PAYMENT_PROVIDER == "mock":
        return MockPaymentProvider()
    return None


class PaymentService:
    @classmethod
    def process(cls, order, payment_method):
        with transaction.atomic():
            locked_order = type(order).objects.select_for_update().get(pk=order.pk)
            paid_payment = locked_order.payments.filter(status=Payment.STATUS_PAID).first()
            if paid_payment:
                return paid_payment

            if payment_method == "cod":
                existing_cod = locked_order.payments.filter(
                    payment_method="cod",
                    status=Payment.STATUS_PENDING,
                ).first()
                if existing_cod:
                    return existing_cod
                payment = Payment.objects.create(
                    order=locked_order,
                    amount=locked_order.total_price,
                    payment_method="cod",
                    provider="cash",
                    status=Payment.STATUS_PENDING,
                )
                notify_user(
                    locked_order.user,
                    "payment",
                    "Cash on delivery selected",
                    f"Order {locked_order.code} is placed with cash on delivery.",
                    f"/orders/orders/{locked_order.pk}/",
                )
                cls._notify_restaurant_of_new_order(locked_order, "cash-on-delivery")
                return payment

            if payment_method != "test" or settings.PAYMENT_PROVIDER != "mock":
                raise PaymentProcessingError(
                    "That payment method is not configured. Choose cash on delivery "
                    "or the development test payment."
                )

            provider = get_provider()
            transaction_id = provider.charge(locked_order)
            payment = Payment.objects.create(
                order=locked_order,
                amount=locked_order.total_price,
                payment_method="test",
                provider=provider.name,
                transaction_id=transaction_id,
                status=Payment.STATUS_PAID,
            )
            notify_user(
                locked_order.user,
                "payment",
                "Payment received",
                f"Payment for order {locked_order.code} was successful.",
                f"/orders/orders/{locked_order.pk}/",
            )
            cls._notify_restaurant_of_new_order(locked_order, "paid")
            return payment

    @staticmethod
    def _notify_restaurant_of_new_order(order, kind):
        notify_user(
            order.restaurant.owner,
            "order",
            f"New {kind} order",
            f"Order {order.code} is waiting for your response.",
            "/restaurant/orders/",
        )


@transaction.atomic
def refund_order_payments(order, reason="", amount=None):
    """Refund captured payments for an order.

    Returns the list of refunded Payment rows. Payment state is decided by the
    server, never by anything the client sends.
    """
    payments = list(
        Payment.objects.select_for_update().filter(order=order)
    )
    refunded = []
    provider = get_provider()
    remaining = Decimal(amount) if amount is not None else None

    for payment in payments:
        if not payment.is_captured:
            continue
        outstanding = payment.amount - payment.refund_amount
        if outstanding <= Decimal("0.00"):
            continue
        refund_value = outstanding
        if remaining is not None:
            refund_value = min(outstanding, remaining)
            if refund_value <= Decimal("0.00"):
                continue
            remaining -= refund_value

        reference = provider.refund(payment, refund_value) if provider else ""
        payment.refund_amount = payment.refund_amount + refund_value
        if payment.refund_amount >= payment.amount:
            payment.status = Payment.STATUS_REFUNDED
        else:
            payment.status = Payment.STATUS_PARTIALLY_REFUNDED
        payment.refund_reference = reference
        payment.refund_reason = reason[:255]
        payment.refunded_at = timezone.now()
        payment.save(
            update_fields=[
                "refund_amount",
                "status",
                "refund_reference",
                "refund_reason",
                "refunded_at",
                "updated_at",
            ]
        )
        refunded.append(payment)

    if refunded:
        notify_user(
            order.user,
            "payment",
            "Refund initiated",
            f"A refund of ₹{sum(p.refund_amount for p in refunded)} was initiated for order {order.code}.",
            f"/orders/orders/{order.pk}/",
        )
        notify_user(
            order.restaurant.owner,
            "payment",
            "Order refunded",
            f"Order {order.code} was refunded to the customer.",
            "/restaurant/payments/",
        )
    return refunded
