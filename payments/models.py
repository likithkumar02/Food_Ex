from decimal import Decimal

from django.db import models


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("card", "Card"),
        ("wallet", "Wallet"),
        ("upi", "UPI"),
        ("cod", "Cash on Delivery"),
        ("test", "Development Test Payment"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_PARTIALLY_REFUNDED = "partially_refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_PARTIALLY_REFUNDED, "Partially Refunded"),
    ]

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="card")
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    provider = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    refund_reference = models.CharField(max_length=100, blank=True)
    refund_reason = models.CharField(max_length=255, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment for Order #{self.order_id}"

    @property
    def is_captured(self):
        return self.status in (self.STATUS_PAID, self.STATUS_PARTIALLY_REFUNDED)

    @property
    def net_amount(self):
        return self.amount - self.refund_amount
