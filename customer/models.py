from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    address = models.TextField(blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    area = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=12, blank=True)
    profile_image = models.ImageField(
        upload_to="customer_profiles/",
        blank=True,
        null=True,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username}"


class CustomerAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_addresses",
    )
    name = models.CharField(max_length=50, default="Home")  # e.g. Home, Work, Other
    address = models.TextField()
    address_line = models.CharField(max_length=255, blank=True)
    area = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=12, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "Customer address"
        verbose_name_plural = "Customer addresses"

    def __str__(self):
        return f"{self.name}: {self.address[:30]}"


class Review(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="review",
    )
    restaurant = models.ForeignKey(
        "restaurant.Restaurant",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    restaurant_reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_replies",
        limit_choices_to={"role": "restaurant_owner"},
    )
    is_hidden = models.BooleanField(
        default=False,
        help_text="Set by platform moderation when a review breaks the guidelines.",
    )
    moderation_note = models.CharField(
        max_length=255,
        blank=True,
        help_text="Admin-only note explaining why the review was hidden or flagged.",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews",
        limit_choices_to={"role": "admin"},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def stars(self):
        """Simple 1-5 star outline used by the partner UI."""
        return "★" * self.rating + "☆" * (5 - self.rating)

    def clean(self):
        if not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})
        if self.order_id and self.user_id and self.order.user_id != self.user_id:
            raise ValidationError({"order": "You can only review your own order."})
        if self.order_id and self.restaurant_id and self.order.restaurant_id != self.restaurant_id:
            raise ValidationError({"restaurant": "Review restaurant must match the order."})
        if self.order_id and self.order.status != "delivered":
            raise ValidationError({"order": "Only delivered orders can be reviewed."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rating}/5 review for {self.restaurant.name}"
