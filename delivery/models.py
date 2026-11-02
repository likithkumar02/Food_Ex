from django.conf import settings
from django.db import models

from orders.models import Order


class DeliveryPartnerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_profile",
        limit_choices_to={"role": "delivery_partner"},
    )
    is_online = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    vehicle_type = models.CharField(max_length=40, blank=True)
    vehicle_number = models.CharField(max_length=30, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Delivery profile for {self.user.username}"


class DeliveryAssignment(models.Model):
    STATUS_ASSIGNED = "assigned"
    STATUS_ACCEPTED = "accepted"
    STATUS_ARRIVED_AT_PICKUP = "arrived_at_pickup"
    STATUS_PICKED_UP = "picked_up"
    STATUS_ON_THE_WAY = "on_the_way"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_REJECTED = "rejected"
    STATUS_TIMED_OUT = "timed_out"

    STATUS_CHOICES = [
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_ARRIVED_AT_PICKUP, "Arrived at Pickup"),
        (STATUS_PICKED_UP, "Picked Up"),
        (STATUS_ON_THE_WAY, "On the Way"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_TIMED_OUT, "Timed Out"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery_assignment")
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deliveries",
        limit_choices_to={"role": "delivery_partner"},
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_ASSIGNED)
    arrived_at_pickup_time = models.DateTimeField(null=True, blank=True)
    pickup_time = models.DateTimeField(null=True, blank=True)
    delivery_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Delivery for Order #{self.order_id}"


class DeliveryAssignmentAttempt(models.Model):
    STATUS_OFFERED = "offered"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_TIMED_OUT = "timed_out"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_OFFERED, "Offered"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_TIMED_OUT, "Timed out"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    assignment = models.ForeignKey(
        DeliveryAssignment,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_assignment_attempts",
        limit_choices_to={"role": "delivery_partner"},
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OFFERED,
    )
    rejection_reason = models.CharField(max_length=255, blank=True)
    offered_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["offered_at", "pk"]
        indexes = [models.Index(fields=["assignment", "status"])]

    def __str__(self):
        return f"Attempt for assignment #{self.assignment_id} to {self.partner}"


class DeliveryLocation(models.Model):
    delivery_partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_records",
        limit_choices_to={"role": "delivery_partner"},
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        related_name="delivery_locations",
        null=True,
        blank=True,
    )
    assignment = models.ForeignKey(
        DeliveryAssignment,
        on_delete=models.CASCADE,
        related_name="locations",
        null=True,
        blank=True,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["delivery_partner", "-recorded_at"]),
            models.Index(fields=["order", "-recorded_at"]),
        ]

    def __str__(self):
        return f"Location for partner {self.delivery_partner_id} at {self.recorded_at}"
