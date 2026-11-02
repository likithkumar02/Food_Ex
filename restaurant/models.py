from datetime import time as dt_time
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .fields import EncryptedCharField


PLATFORM_COMMISSION_DEFAULT = Decimal("20.00")
PLATFORM_GST_DEFAULT = Decimal("5.00")
PLATFORM_DELIVERY_FEE_DEFAULT = Decimal("40.00")


def quantize_money(value):
    """Round any numeric value to two decimal places using half-up rounding."""
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PlatformSetting(models.Model):
    """Singleton-style configuration for platform-wide money rules."""

    name = models.CharField(max_length=60, unique=True, default="default")
    default_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=PLATFORM_COMMISSION_DEFAULT,
        validators=[MinValueValidator(Decimal("0"))],
    )
    gst_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=PLATFORM_GST_DEFAULT,
        validators=[MinValueValidator(Decimal("0"))],
    )
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=PLATFORM_DELIVERY_FEE_DEFAULT,
        validators=[MinValueValidator(Decimal("0"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform setting"
        verbose_name_plural = "Platform settings"

    def __str__(self):
        return f"Platform settings ({self.default_commission_percent}% commission)"

    def save(self, *args, **kwargs):
        self.name = "default"
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        setting, _ = cls.objects.get_or_create(name="default")
        return setting


class Restaurant(models.Model):
    RESTAURANT_TYPE_CHOICES = [
        ("veg", "Veg"),
        ("non_veg", "Non-Veg"),
        ("both", "Both"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    ]
    CUISINE_CHOICES = [
        ("Indian", "Indian"),
        ("South Indian", "South Indian"),
        ("North Indian", "North Indian"),
        ("Biryani", "Biryani"),
        ("Chinese", "Chinese"),
        ("Fast Food", "Fast Food"),
        ("Bakery", "Bakery"),
        ("Desserts", "Desserts"),
        ("Pizza", "Pizza"),
        ("Burgers", "Burgers"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="restaurants",
    )
    name = models.CharField(max_length=200)
    cuisine_type = models.CharField(max_length=100)
    restaurant_type = models.CharField(
        max_length=10,
        choices=RESTAURANT_TYPE_CHOICES,
        default="both",
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="restaurants/", blank=True, null=True)
    logo = models.ImageField(upload_to="restaurants/logos/", blank=True, null=True)
    address = models.CharField(max_length=255)
    address_line = models.CharField(max_length=255, blank=True)
    area = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=12, blank=True)
    phone = models.CharField(max_length=20)
    fssai_number = models.CharField(max_length=32, blank=True)
    gst_number = models.CharField(max_length=32, blank=True)
    pan_number = models.CharField(max_length=16, blank=True)
    bank_account_number = EncryptedCharField(max_length=255, blank=True, editable=False)
    bank_ifsc_code = models.CharField(max_length=11, blank=True)
    account_holder_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    status_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_restaurants",
        limit_choices_to={"role": "admin"},
    )
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Restaurant-specific commission. Leave empty to use the "
            "platform default set in Food_Ex settings."
        ),
    )
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    is_open = models.BooleanField(
        default=True,
        help_text="Manual open/closed switch controlled by the restaurant owner.",
    )
    minimum_order_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    delivery_radius_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("8.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_approved(self):
        return self.status == "approved" and self.is_active

    @property
    def commission_rate(self):
        """Effective commission percentage for this restaurant."""
        if self.commission_percent is not None:
            return quantize_money(self.commission_percent)
        return quantize_money(PlatformSetting.load().default_commission_percent)

    @property
    def accepts_orders(self):
        return self.is_approved and self.is_open

    @property
    def average_rating(self):
        result = self.reviews.aggregate(value=models.Avg("rating"))["value"]
        return round(result, 1) if result is not None else None
class MenuCategory(models.Model):
    """A menu section owned by a single restaurant."""

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="menu_categories",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "name"],
                name="unique_menu_category_per_restaurant",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"

    @property
    def item_count(self):
        return self.items.count()


class MenuItem(models.Model):
    FOOD_TYPE_CHOICES = [
        ("veg", "Veg"),
        ("non_veg", "Non-Veg"),
        ("egg", "Egg"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    menu_category = models.ForeignKey(
        MenuCategory,
        on_delete=models.SET_NULL,
        related_name="items",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "List price before the discount. Leave empty when the item "
            "has no discount."
        ),
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final price charged to the customer, after the discount.",
    )
    category = models.CharField(max_length=100, blank=True)
    food_type = models.CharField(
        max_length=10,
        choices=FOOD_TYPE_CHOICES,
        default="veg",
    )
    preparation_time_minutes = models.PositiveIntegerField(default=20)
    image = models.ImageField(upload_to="menu_items/", blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} - {self.restaurant.name}"

    @property
    def discount_amount(self):
        if self.mrp is None:
            return Decimal("0.00")
        return quantize_money(self.mrp - self.price)

    @property
    def has_discount(self):
        return bool(self.mrp is not None and self.discount_amount > 0)

    @property
    def final_price(self):
        return self.price

    def clean(self):
        if self.menu_category_id and self.menu_category.restaurant_id != self.restaurant_id:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {"menu_category": "Category belongs to a different restaurant."}
            )

    def save(self, *args, **kwargs):
        if self.menu_category_id and not self.category:
            self.category = self.menu_category.name
        self.discount_percent = Decimal(self.discount_percent or 0)
        if self.mrp is not None:
            multiplier = (Decimal("100") - self.discount_percent) / Decimal("100")
            self.price = (Decimal(self.mrp) * multiplier).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        self.price = Decimal(self.price or 0).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        super().save(*args, **kwargs)


class RestaurantTiming(models.Model):
    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="timings",
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    opening_time = models.TimeField(default=dt_time(9, 0))
    closing_time = models.TimeField(default=dt_time(23, 0))
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["day_of_week"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "day_of_week"],
                name="unique_timing_per_restaurant_day",
            ),
        ]

    def __str__(self):
        return f"{self.get_day_of_week_display()} - {self.restaurant.name}"


class RestaurantDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("fssai", "FSSAI Licence"),
        ("gst", "GST Certificate"),
        ("pan", "PAN Card"),
        ("bank", "Bank Proof"),
        ("owner_id", "Owner ID Proof"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to="restaurant_documents/")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    remark = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.restaurant.name}"


class RestaurantOffer(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("flat", "Flat Amount"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="offers",
    )
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, blank=True)
    discount_type = models.CharField(
        max_length=12,
        choices=DISCOUNT_TYPE_CHOICES,
        default="percentage",
    )
    discount_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    minimum_order_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    maximum_discount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    usage_limit = models.PositiveIntegerField(default=0, help_text="0 means unlimited.")
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"

    @property
    def is_currently_valid(self):
        today = timezone.localdate()
        if not self.is_active:
            return False
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True

    def calculate_discount(self, order_amount):
        """Return the discount for an order amount, capped and validated."""
        amount = quantize_money(order_amount)
        if amount < quantize_money(self.minimum_order_amount):
            return Decimal("0.00")
        if self.discount_type == "percentage":
            discount = amount * quantize_money(self.discount_value) / Decimal("100")
        else:
            discount = quantize_money(self.discount_value)
        if self.maximum_discount is not None:
            discount = min(discount, quantize_money(self.maximum_discount))
        discount = quantize_money(discount)
        return min(discount, amount)
class RestaurantEarning(models.Model):
    """Per-order money split between Food_Ex, the restaurant, and the rider.

    Payout breakdown (see project memory / Food_Ex hard constraints):
      * Customer pays: subtotal + GST + delivery_fee - discount = total_price
      * Restaurant payout: (subtotal - discount + GST) - commission% on food
      * Rider payout:        fixed delivery_fee
      * Admin revenue:       commission + platform_fee portion

    Every field here is stored as-of transaction time so the earning row is
    immutable even if commission rules change later.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("settled", "Settled"),
        ("cancelled", "Cancelled"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="earnings",
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="earning",
    )
    settlement = models.ForeignKey(
        "Settlement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="earnings_set",
        help_text="The payout batch that paid this earning.",
    )
    order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Food subtotal the customer paid, after offer discount.",
    )
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Platform commission deducted from the food subtotal.",
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="GST collected on the food portion (passed through to restaurant).",
    )
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Fixed delivery fee collected (paid to the delivery partner).",
    )
    platform_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Additional platform fee retained by Food_Ex (0 when none).",
    )
    restaurant_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount due to restaurant (food + GST - commission).",
    )
    rider_payout = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Delivery partner payout (mirrors delivery_fee unless overridden).",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Earning for order #{self.order_id}"


class Settlement(models.Model):
    """A payout of accumulated restaurant earnings for a period."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="settlements",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    reference = models.CharField(max_length=60, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Settlement {self.period_start} to {self.period_end}"
