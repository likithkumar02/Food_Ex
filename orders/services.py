from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from notifications.services import notify_user
from restaurant.models import PlatformSetting, RestaurantOffer, quantize_money

from .models import (
    MAX_CART_ITEM_QUANTITY,
    Cart,
    Order,
    OrderItem,
    OrderStatusEvent,
)
from customer.models import CustomerAddress, CustomerProfile


class CartCheckoutError(Exception):
    pass


class OrderTransitionError(Exception):
    pass


def _money(value):
    return quantize_money(value)


def compute_order_totals(subtotal, offer=None):
    """Apply the platform fee rules and an optional offer to a basket subtotal.

    All money maths happens here on the server so a tampered client payload
    can never change the amounts a customer is charged.
    """
    platform = PlatformSetting.load()
    subtotal = _money(subtotal)
    discount = _money(offer.calculate_discount(subtotal)) if offer else Decimal("0.00")
    taxable = subtotal - discount
    if taxable < Decimal("0.00"):
        taxable = Decimal("0.00")
    tax = _money(taxable * _money(platform.gst_percent) / Decimal("100"))
    delivery_fee = _money(platform.delivery_fee)
    total = _money(taxable + tax + delivery_fee)
    return {
        "subtotal": subtotal,
        "discount_amount": discount,
        "tax_amount": tax,
        "delivery_fee": delivery_fee,
        "total_price": total,
    }


def resolve_offer(restaurant, offer_code, subtotal):
    """Return the active offer matching a code, or raise with a clear reason."""
    if not offer_code:
        return None
    offer = RestaurantOffer.objects.filter(
        restaurant=restaurant,
        code__iexact=offer_code.strip(),
    ).first()
    if offer is None:
        raise CartCheckoutError("That offer code is not valid for this restaurant.")
    if not offer.is_currently_valid:
        raise CartCheckoutError("That offer is no longer available.")
    if _money(subtotal) < _money(offer.minimum_order_amount):
        raise CartCheckoutError(
            f"This offer needs a minimum order of ₹{offer.minimum_order_amount}."
        )
    return offer


@transaction.atomic
def create_order_from_cart(
    user,
    delivery_address,
    latitude=None,
    longitude=None,
    offer_code=None,
    address_id=None,
):
    address = (delivery_address or "").strip()
    selected_address = None
    if address_id is not None:
        selected_address = CustomerAddress.objects.filter(
            pk=address_id,
            user=user,
        ).first()
        if selected_address is None:
            raise CartCheckoutError("The selected delivery address was not found.")
        address = selected_address.address.strip()
        latitude = selected_address.latitude
        longitude = selected_address.longitude
    if not address:
        raise CartCheckoutError("A delivery address is required.")

    cart, _ = Cart.objects.select_for_update().get_or_create(user=user)
    items = list(
        cart.items.select_related("menu_item__restaurant").order_by("pk")
    )
    if not items:
        raise CartCheckoutError("Your cart is empty.")

    restaurant_ids = {item.menu_item.restaurant_id for item in items}
    if len(restaurant_ids) != 1:
        raise CartCheckoutError("Place separate orders for items from different restaurants.")
    restaurant = items[0].menu_item.restaurant
    if not restaurant.is_approved:
        raise CartCheckoutError("This restaurant is not accepting orders right now.")
    if not restaurant.is_open:
        raise CartCheckoutError("This restaurant is currently closed.")
    if (latitude is None) != (longitude is None):
        raise CartCheckoutError("A complete delivery location is required.")
    if latitude is not None and restaurant.latitude is not None and restaurant.longitude is not None:
        from location.services import calculate_distance

        distance = calculate_distance(
            latitude,
            longitude,
            restaurant.latitude,
            restaurant.longitude,
        )
        if distance is not None and distance > float(restaurant.delivery_radius_km):
            raise CartCheckoutError("This address is outside the restaurant's delivery area.")
    if any(not item.menu_item.is_available for item in items):
        raise CartCheckoutError("One or more items in your cart are unavailable.")

    grouped = {}
    for item in items:
        key = item.menu_item_id
        grouped[key] = grouped.get(key, 0) + item.quantity
    if any(quantity > MAX_CART_ITEM_QUANTITY for quantity in grouped.values()):
        raise CartCheckoutError("Maximum quantity per item is 20.")

    subtotal = sum(
        (Decimal(item.quantity) * item.menu_item.price for item in items),
        Decimal("0.00"),
    )
    if restaurant.minimum_order_amount and subtotal < restaurant.minimum_order_amount:
        raise CartCheckoutError(
            f"Minimum order value for this restaurant is ₹{restaurant.minimum_order_amount}."
        )

    offer = resolve_offer(restaurant, offer_code, subtotal)
    totals = compute_order_totals(subtotal, offer)
    if selected_address is None and latitude is None and longitude is None:
        customer_profile = CustomerProfile.objects.filter(user=user).first()
        if customer_profile and customer_profile.latitude is not None and customer_profile.longitude is not None:
            latitude = customer_profile.latitude
            longitude = customer_profile.longitude

    order = Order.objects.create(
        user=user,
        restaurant=restaurant,
        offer=offer,
        subtotal=totals["subtotal"],
        delivery_fee=totals["delivery_fee"],
        tax_amount=totals["tax_amount"],
        discount_amount=totals["discount_amount"],
        total_price=totals["total_price"],
        status=Order.STATUS_PLACED,
        delivery_address=address,
        address=selected_address,
        customer_latitude=latitude,
        customer_longitude=longitude,
        restaurant_latitude=restaurant.latitude,
        restaurant_longitude=restaurant.longitude,
        delivery_area=selected_address.area if selected_address else "",
        delivery_city=selected_address.city if selected_address else "",
        delivery_district=selected_address.district if selected_address else "",
        delivery_state=selected_address.state if selected_address else "",
        delivery_pincode=selected_address.pincode if selected_address else "",
    )
    OrderStatusEvent.objects.create(
        order=order,
        to_status=Order.STATUS_PLACED,
        actor=user,
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            menu_item=item.menu_item,
            name=item.menu_item.name,
            quantity=item.quantity,
            unit_price=item.menu_item.price,
        )
        for item in items
    ])
    if offer is not None:
        RestaurantOffer.objects.filter(pk=offer.pk).update(used_count=offer.used_count + 1)
    cart.items.all().delete()
    return order


TRANSITIONS = {
    Order.STATUS_PLACED: {Order.STATUS_ACCEPTED, Order.STATUS_REJECTED, Order.STATUS_CANCELLED},
    Order.STATUS_ACCEPTED: {Order.STATUS_PREPARING, Order.STATUS_CANCELLED},
    Order.STATUS_PREPARING: {Order.STATUS_READY, Order.STATUS_CANCELLED},
    Order.STATUS_READY: {Order.STATUS_FINDING_PARTNER, Order.STATUS_CANCELLED},
    Order.STATUS_FINDING_PARTNER: {
        Order.STATUS_DELIVERY_ASSIGNED,
        Order.STATUS_ASSIGNMENT_FAILED,
        Order.STATUS_READY,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_DELIVERY_ASSIGNED: {
        Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
        Order.STATUS_FINDING_PARTNER,
        Order.STATUS_ASSIGNMENT_FAILED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_DELIVERY_PARTNER_ASSIGNED: {
        Order.STATUS_ARRIVED_AT_PICKUP,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_ARRIVED_AT_PICKUP: {
        Order.STATUS_PICKED_UP,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_PICKED_UP: {Order.STATUS_OUT_FOR_DELIVERY},
    Order.STATUS_OUT_FOR_DELIVERY: {Order.STATUS_DELIVERED},
}

TRANSITION_NOTICES = {
    Order.STATUS_ACCEPTED: (
        "Restaurant accepted your order",
        "Order {code} has been accepted. Estimated preparation time is {minutes} minutes.",
    ),
    Order.STATUS_PREPARING: (
        "Your food is being prepared",
        "Order {code} is now being prepared in the kitchen.",
    ),
    Order.STATUS_READY: (
        "Your order is ready",
        "Order {code} is packed and waiting for a delivery partner.",
    ),
    Order.STATUS_REJECTED: (
        "Order rejected",
        "Order {code} could not be accepted by the restaurant.",
    ),
    Order.STATUS_CANCELLED: (
        "Order cancelled",
        "Order {code} was cancelled.",
    ),
}


def _assert_order_is_paid(order):
    has_paid_payment = order.payments.filter(status="paid").exists()
    has_cod = order.payments.filter(status="pending", payment_method="cod").exists()
    if not (has_paid_payment or has_cod):
        raise OrderTransitionError("This order has not completed payment.")


@transaction.atomic
def transition_restaurant_order(
    user,
    order_id,
    new_status,
    rejection_reason="",
    rejection_note="",
    preparation_minutes=None,
):
    order = (
        Order.objects.select_for_update()
        .select_related("restaurant")
        .filter(pk=order_id, restaurant__owner=user)
        .first()
    )
    if order is None:
        raise OrderTransitionError("Order not found for this restaurant.")
    if order.restaurant.status != "approved" or not order.restaurant.is_active:
        raise OrderTransitionError("Your restaurant is not approved to process orders.")
    previous_status = order.status
    if new_status not in TRANSITIONS.get(previous_status, set()):
        raise OrderTransitionError("Invalid order status transition.")

    if order.status == Order.STATUS_PLACED and new_status != Order.STATUS_REJECTED:
        _assert_order_is_paid(order)

    if new_status == Order.STATUS_REJECTED:
        reason = (rejection_reason or "").strip()
        valid_reasons = dict(Order.REJECTION_REASON_CHOICES)
        if reason not in valid_reasons:
            raise OrderTransitionError("Select a valid reason for rejecting this order.")
        order.rejection_reason = reason
        order.rejection_note = (rejection_note or "").strip()[:255]
        order.closed_at = timezone.now()
        _refund_if_prepaid(order)
        _cancel_order_earning(order)
    elif new_status == Order.STATUS_CANCELLED:
        order.closed_at = timezone.now()
        _refund_if_prepaid(order)
        _cancel_order_earning(order)
        from delivery.services import cancel_order_assignment

        cancel_order_assignment(
            order,
            actor=user,
            reason=(rejection_note or "Order cancelled by restaurant"),
        )

    if new_status == Order.STATUS_ACCEPTED:
        if preparation_minutes is not None:
            try:
                minutes = int(preparation_minutes)
            except (TypeError, ValueError) as error:
                raise OrderTransitionError("Preparation time must be a whole number.") from error
            if not 5 <= minutes <= 180:
                raise OrderTransitionError("Preparation time must be between 5 and 180 minutes.")
            order.estimated_preparation_minutes = minutes
        order.accepted_at = timezone.now()
    elif new_status == Order.STATUS_PREPARING:
        order.preparing_at = timezone.now()
    elif new_status == Order.STATUS_READY:
        order.ready_at = timezone.now()

    order.status = new_status
    order.save()
    transition_reason = ""
    if new_status in (Order.STATUS_CANCELLED, Order.STATUS_REJECTED):
        transition_reason = (rejection_note or rejection_reason or "").strip()
    record_order_status_event(
        order,
        previous_status,
        user,
        reason=transition_reason,
    )

    template = TRANSITION_NOTICES.get(new_status)
    if template:
        title, message = template
        notify_user(
            order.user,
            "order",
            title,
            message.format(
                code=order.code,
                minutes=order.estimated_preparation_minutes or 0,
            ),
            f"/orders/orders/{order.pk}/",
        )

    if new_status == Order.STATUS_READY:
        from delivery.models import DeliveryAssignment
        from delivery.services import assign_ready_order

        assign_ready_order(order)
        assignment = DeliveryAssignment.objects.filter(order=order).first()
        if assignment and assignment.status == DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP:
            previous_status = order.status
            order.status = Order.STATUS_ARRIVED_AT_PICKUP
            order.save(update_fields=["status", "updated_at"])
            record_order_status_event(
                order,
                previous_status,
                actor=user,
                reason="Restaurant marked the order ready while the partner was at pickup.",
            )
    return order


def record_order_status_event(order, from_status, actor=None, reason=""):
    if from_status == order.status:
        return None
    return OrderStatusEvent.objects.create(
        order=order,
        from_status=from_status,
        to_status=order.status,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        reason=(reason or "")[:255],
    )


def _refund_if_prepaid(order):
    """Mark captured payments as refunded when the restaurant declines."""
    from payments.services import refund_order_payments

    refund_order_payments(order, reason="Order declined by restaurant")


def _cancel_order_earning(order):
    """Flip any pending earning row to cancelled when order never completes."""
    from restaurant.services import cancel_order_earning

    cancel_order_earning(order)
