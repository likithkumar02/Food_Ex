from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


MAX_CART_ITEM_QUANTITY = 20


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        return sum(
            (item.quantity * item.menu_item.price for item in self.items.all()),
            Decimal("0.00"),
        )


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(
        "restaurant.MenuItem",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "menu_item")

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name}"

    @property
    def subtotal(self):
        return Decimal(self.quantity) * self.menu_item.price


class Order(models.Model):
    STATUS_PLACED = "placed"
    STATUS_ACCEPTED = "accepted"
    STATUS_PREPARING = "preparing"
    STATUS_READY = "ready_for_pickup"
    STATUS_FINDING_PARTNER = "finding_delivery_partner"
    STATUS_DELIVERY_ASSIGNED = "delivery_assigned"
    STATUS_DELIVERY_PARTNER_ASSIGNED = "delivery_partner_assigned"
    STATUS_ASSIGNMENT_FAILED = "assignment_failed"
    STATUS_ARRIVED_AT_PICKUP = "arrived_at_pickup"
    STATUS_PICKED_UP = "picked_up"
    STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
    STATUS_DELIVERED = "delivered"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PLACED, "Placed"),
        (STATUS_ACCEPTED, "Restaurant Accepted"),
        (STATUS_PREPARING, "Preparing"),
        (STATUS_READY, "Ready for Pickup"),
        (STATUS_FINDING_PARTNER, "Finding a delivery partner"),
        (STATUS_DELIVERY_ASSIGNED, "Delivery Assigned"),
        (STATUS_DELIVERY_PARTNER_ASSIGNED, "Delivery Partner Assigned"),
        (STATUS_ASSIGNMENT_FAILED, "Delivery partner search needs attention"),
        (STATUS_ARRIVED_AT_PICKUP, "Partner at restaurant"),
        (STATUS_PICKED_UP, "Picked Up"),
        (STATUS_OUT_FOR_DELIVERY, "Out for Delivery"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # Statuses a restaurant owner is allowed to drive.
    RESTAURANT_MANAGED_STATUSES = (
        STATUS_PLACED,
        STATUS_ACCEPTED,
        STATUS_PREPARING,
        STATUS_READY,
    )
    LIVE_STATUSES = (
        STATUS_PLACED,
        STATUS_ACCEPTED,
        STATUS_PREPARING,
        STATUS_READY,
        STATUS_FINDING_PARTNER,
        STATUS_DELIVERY_ASSIGNED,
        STATUS_DELIVERY_PARTNER_ASSIGNED,
        STATUS_ASSIGNMENT_FAILED,
        STATUS_ARRIVED_AT_PICKUP,
        STATUS_PICKED_UP,
        STATUS_OUT_FOR_DELIVERY,
    )
    CLOSED_STATUSES = (STATUS_DELIVERED, STATUS_CANCELLED, STATUS_REJECTED)

    PAYMENT_METHOD_CHOICES = [
        ("card", "Card"),
        ("upi", "UPI"),
        ("wallet", "Wallet"),
        ("cod", "Cash on Delivery"),
        ("test", "Development Test Payment"),
    ]

    REJECTION_REASON_CHOICES = [
        ("restaurant_closed", "Restaurant Closed"),
        ("item_unavailable", "Item Unavailable"),
        ("too_many_orders", "Too Many Orders"),
        ("technical_problem", "Technical Problem"),
        ("other", "Other"),
    ]

    code = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    restaurant = models.ForeignKey("restaurant.Restaurant", on_delete=models.CASCADE, related_name="orders")
    offer = models.ForeignKey(
        "restaurant.RestaurantOffer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PLACED)
    rejection_reason = models.CharField(
        max_length=30,
        choices=REJECTION_REASON_CHOICES,
        blank=True,
    )
    rejection_note = models.CharField(max_length=255, blank=True)
    estimated_preparation_minutes = models.PositiveIntegerField(null=True, blank=True)
    delivery_address = models.TextField()
    delivery_area = models.CharField(max_length=100, blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_district = models.CharField(max_length=100, blank=True)
    delivery_state = models.CharField(max_length=100, blank=True)
    delivery_pincode = models.CharField(max_length=12, blank=True)
    address = models.ForeignKey(
        "customer.CustomerAddress",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    customer_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    restaurant_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    restaurant_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_location_updated_at = models.DateTimeField(null=True, blank=True)
    delivery_distance = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    estimated_delivery_time = models.PositiveIntegerField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    preparing_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivery_assigned_at = models.DateTimeField(null=True, blank=True)
    delivery_partner_assigned_at = models.DateTimeField(null=True, blank=True)
    arrived_at_pickup_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.code or self.pk} - {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

    def _generate_code(self):
        """Build a unique, collision-safe order code."""
        stamp = timezone.now().strftime("%y%m%d%H%M%S")
        suffix = 1
        candidate = f"FE{stamp}{suffix:03d}"
        while Order.objects.filter(code=candidate).exists():
            suffix += 1
            candidate = f"FE{stamp}{suffix:03d}"
        return candidate

    @property
    def is_live(self):
        return self.status in self.LIVE_STATUSES

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def payment_status(self):
        """Best-effort payment state for display in dashboards."""
        payments = list(self.payments.all())
        if any(payment.status == "paid" for payment in payments):
            if any(payment.status == "refunded" for payment in payments):
                return "refunded"
            return "paid"
        if any(payment.status == "refunded" for payment in payments):
            return "refunded"
        if any(payment.status == "pending" for payment in payments):
            return "pending"
        if any(payment.status == "failed" for payment in payments):
            return "failed"
        return "unpaid"

    @property
    def customer_display_name(self):
        name = self.user.get_full_name().strip()
        return name or self.user.username

    @property
    def customer_phone(self):
        profile = getattr(self.user, "customer_profile", None)
        return profile.phone_number if profile else ""


class OrderStatusEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_events")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_events",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [models.Index(fields=["order", "created_at"])]

    def __str__(self):
        return f"Order #{self.order_id}: {self.from_status} -> {self.to_status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(
        "restaurant.MenuItem",
        on_delete=models.CASCADE,
        related_name="order_items",
    )
    name = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.name or self.menu_item_id}"

    def save(self, *args, **kwargs):
        if not self.name and self.menu_item_id:
            self.name = self.menu_item.name
        return super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return Decimal(self.quantity) * self.unit_price
