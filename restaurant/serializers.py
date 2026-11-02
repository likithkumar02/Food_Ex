from datetime import date
from decimal import Decimal

from django.db.models import Avg
from rest_framework import serializers

from .models import (
    MenuCategory,
    MenuItem,
    PlatformSetting,
    Restaurant,
    RestaurantDocument,
    RestaurantEarning,
    RestaurantOffer,
    RestaurantTiming,
    Settlement,
    quantize_money,
)

ALLOWED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
ALLOWED_DOCUMENT_EXTENSIONS = ("pdf", "jpg", "jpeg", "png")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def validate_upload(file_obj, label="Image", extensions=None, max_bytes=None):
    extensions = extensions or ALLOWED_IMAGE_EXTENSIONS
    max_bytes = max_bytes or MAX_IMAGE_BYTES
    if file_obj is None:
        return file_obj
    if file_obj.size > max_bytes:
        raise serializers.ValidationError(
            f"{label} must be {max_bytes // (1024 * 1024)} MB or smaller."
        )
    name = getattr(file_obj, "name", "").lower()
    if "." not in name or name.rsplit(".", 1)[-1] not in extensions:
        pretty = ", ".join(ext.upper() for ext in extensions)
        raise serializers.ValidationError(f"{label} must be one of: {pretty}.")
    return file_obj


def absolute_url(request, file_field):
    if not file_field:
        return None
    url = file_field.url
    return request.build_absolute_uri(url) if request else url


class MenuCategorySerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MenuCategory
        fields = (
            "id",
            "name",
            "description",
            "display_order",
            "is_active",
            "item_count",
            "created_at",
        )
        read_only_fields = ("id", "item_count", "created_at")

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Category name is required.")
        restaurant = self.context.get("restaurant")
        if restaurant is not None:
            duplicates = MenuCategory.objects.filter(
                restaurant=restaurant,
                name__iexact=name,
            )
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError("You already have a category with this name.")
        return name


class MenuItemSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    has_discount = serializers.BooleanField(read_only=True)
    image_url = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category", read_only=True)

    class Meta:
        model = MenuItem
        fields = (
            "id",
            "name",
            "description",
            "mrp",
            "discount_percent",
            "price",
            "final_price",
            "discount_amount",
            "has_discount",
            "category",
            "category_name",
            "menu_category",
            "food_type",
            "preparation_time_minutes",
            "image",
            "image_url",
            "is_available",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "price", "created_at", "updated_at")
        extra_kwargs = {"image": {"write_only": True, "required": False}}

    def get_image_url(self, item):
        return absolute_url(self.context.get("request"), item.image)


class MenuItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = (
            "id",
            "name",
            "description",
            "mrp",
            "discount_percent",
            "price",
            "menu_category",
            "food_type",
            "preparation_time_minutes",
            "image",
            "is_available",
        )
        read_only_fields = ("id", "price")
        extra_kwargs = {"image": {"required": False}}

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Item name is required.")
        return name

    def validate_mrp(self, value):
        if value is not None and value <= Decimal("0.00"):
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_discount_percent(self, value):
        if value is None:
            return Decimal("0.00")
        if value < 0 or value > 90:
            raise serializers.ValidationError("Discount must be between 0 and 90 percent.")
        return value

    def validate_image(self, value):
        return validate_upload(value, "Item image")

    def validate_preparation_time_minutes(self, value):
        if value is None or value < 1 or value > 240:
            raise serializers.ValidationError("Preparation time must be between 1 and 240 minutes.")
        return value

    def validate(self, attrs):
        restaurant = self.context["restaurant"]
        category = attrs.get("menu_category", getattr(self.instance, "menu_category", None))
        if category is not None and category.restaurant_id != restaurant.id:
            raise serializers.ValidationError(
                {"menu_category": "Select a category that belongs to your restaurant."}
            )
        base_price = attrs.get("mrp", getattr(self.instance, "mrp", None))
        price = attrs.get("price", getattr(self.instance, "price", None))
        if base_price is None and (price is None or price <= Decimal("0.00")):
            raise serializers.ValidationError({"price": "Enter a price for this item."})
        return attrs


class RestaurantSerializer(serializers.ModelSerializer):
    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    delivery_time_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = (
            "id",
            "name",
            "cuisine_type",
            "description",
            "phone",
            "address",
            "address_line",
            "area",
            "city",
            "district",
            "state",
            "pincode",
            "restaurant_type",
            "image",
            "image_url",
            "logo_url",
            "is_open",
            "minimum_order_amount",
            "delivery_radius_km",
            "latitude",
            "longitude",
            "rating",
            "review_count",
            "delivery_time_minutes",
        )
        read_only_fields = fields

    def get_rating(self, restaurant):
        average = restaurant.reviews.filter(is_hidden=False).aggregate(value=Avg("rating"))["value"]
        return round(average, 1) if average is not None else None

    def get_review_count(self, restaurant):
        return restaurant.reviews.filter(is_hidden=False).count()

    def get_image_url(self, restaurant):
        return absolute_url(self.context.get("request"), restaurant.image)

    def get_logo_url(self, restaurant):
        return absolute_url(self.context.get("request"), restaurant.logo)

    def get_delivery_time_minutes(self, restaurant):
        average = restaurant.menu_items.filter(is_available=True).aggregate(
            value=Avg("preparation_time_minutes")
        )["value"]
        base = int(average) if average else 25
        return base + 15


class RestaurantProfileUpdateSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)
    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Restaurant
        fields = (
            "name",
            "owner",
            "description",
            "address",
            "city",
            "area",
            "district",
            "state",
            "pincode",
            "phone",
            "cuisine_type",
            "restaurant_type",
            "fssai_number",
            "gst_number",
            "pan_number",
            "bank_ifsc_code",
            "account_holder_name",
            "opening_time",
            "closing_time",
            "is_open",
            "minimum_order_amount",
            "delivery_radius_km",
            "latitude",
            "longitude",
            "logo",
            "image",
            "image_url",
            "logo_url",
            "status",
            "status_reason",
            "commission_percent",
        )
        read_only_fields = ("owner", "status", "status_reason", "image_url", "logo_url")

    def validate_logo(self, value):
        return validate_upload(value, "Restaurant logo")

    def validate_image(self, value):
        return validate_upload(value, "Cover image")

    def get_image_url(self, restaurant):
        return absolute_url(self.context.get("request"), restaurant.image)

    def get_logo_url(self, restaurant):
        return absolute_url(self.context.get("request"), restaurant.logo)


class RestaurantOfferSerializer(serializers.ModelSerializer):
    is_currently_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = RestaurantOffer
        fields = (
            "id",
            "name",
            "code",
            "discount_type",
            "discount_value",
            "minimum_order_amount",
            "maximum_discount",
            "start_date",
            "end_date",
            "usage_limit",
            "used_count",
            "is_active",
            "is_currently_valid",
            "created_at",
        )
        read_only_fields = ("id", "used_count", "is_currently_valid", "created_at")


class RestaurantOfferWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantOffer
        fields = (
            "name",
            "code",
            "discount_type",
            "discount_value",
            "minimum_order_amount",
            "maximum_discount",
            "start_date",
            "end_date",
            "usage_limit",
            "is_active",
        )

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"end_date": "End date must be after or equal to the start date."}
            )
        if attrs.get("discount_type") == "percentage":
            value = attrs.get("discount_value", 0)
            if value < 0 or value > 90:
                raise serializers.ValidationError(
                    {"discount_value": "Percentage discount must be between 0 and 90."}
                )
        return attrs


class RestaurantTimingSerializer(serializers.ModelSerializer):
    day_label = serializers.CharField(source="get_day_of_week_display", read_only=True)

    class Meta:
        model = RestaurantTiming
        fields = (
            "id",
            "day_of_week",
            "day_label",
            "opening_time",
            "closing_time",
            "is_closed",
        )
        read_only_fields = ("id", "day_label")


class RestaurantTimingBulkSerializer(serializers.ListSerializer):
    child = RestaurantTimingSerializer()

    def validate(self, items):
        if len(items) != 7:
            raise serializers.ValidationError(
                "Provide exactly 7 entries, one for each day (Mon-Sun)."
            )
        days = {item["day_of_week"] for item in items}
        if days != set(range(7)):
            raise serializers.ValidationError(
                "Each day of the week (0–6) must appear exactly once."
            )
        return items


class RestaurantDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField(read_only=True)
    type_label = serializers.CharField(source="get_document_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RestaurantDocument
        fields = (
            "id",
            "document_type",
            "type_label",
            "file",
            "file_url",
            "status",
            "status_label",
            "remark",
            "uploaded_at",
        )
        read_only_fields = ("id", "status", "file_url", "type_label", "status_label", "uploaded_at")

    def validate_file(self, value):
        return validate_upload(
            value,
            "Document",
            extensions=ALLOWED_DOCUMENT_EXTENSIONS,
            max_bytes=MAX_DOCUMENT_BYTES,
        )

    def get_file_url(self, document):
        return absolute_url(self.context.get("request"), document.file)


class RestaurantEarningSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(source="order.code", read_only=True)
    order_created_at = serializers.DateTimeField(source="order.created_at", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RestaurantEarning
        fields = (
            "id",
            "order_id",
            "order_code",
            "order_created_at",
            "order_amount",
            "commission_percent",
            "commission_amount",
            "tax_amount",
            "delivery_fee",
            "platform_fee",
            "restaurant_amount",
            "rider_payout",
            "status",
            "status_label",
            "settlement_id",
            "settled_at",
            "created_at",
        )
        read_only_fields = fields


class SettlementSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    earning_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Settlement
        fields = (
            "id",
            "period_start",
            "period_end",
            "gross_amount",
            "commission_amount",
            "net_amount",
            "status",
            "status_label",
            "reference",
            "notes",
            "paid_at",
            "earning_count",
            "created_at",
        )
        read_only_fields = fields


class ReviewSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    order_code = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    rating = serializers.IntegerField(read_only=True)
    stars = serializers.CharField(read_only=True)
    comment = serializers.CharField(read_only=True, allow_blank=True)
    restaurant_reply = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    replied_at = serializers.DateTimeField(read_only=True)
    is_hidden = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class ReviewReplySerializer(serializers.Serializer):
    reply = serializers.CharField(max_length=2000)

    def validate_reply(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Reply must be at least 2 characters.")
        return value


class NotificationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    category = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    is_read = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class OrderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    menu_item_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    food_type = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)


class DeliveryInfoSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    status_label = serializers.CharField(read_only=True)
    partner_id = serializers.IntegerField(read_only=True, allow_null=True)
    partner_name = serializers.CharField(read_only=True, allow_null=True)
    partner_phone = serializers.CharField(read_only=True, allow_null=True)
    pickup_time = serializers.DateTimeField(read_only=True, allow_null=True)
    delivery_time = serializers.DateTimeField(read_only=True, allow_null=True)


class PartnerOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    customer_phone = serializers.CharField(read_only=True, allow_blank=True)
    delivery_address = serializers.CharField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    delivery_fee = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    payment_status = serializers.CharField(read_only=True)
    rejection_reason = serializers.CharField(read_only=True, allow_blank=True)
    rejection_note = serializers.CharField(read_only=True, allow_blank=True)
    estimated_preparation_minutes = serializers.IntegerField(read_only=True, allow_null=True)
    delivery = DeliveryInfoSerializer(read_only=True, allow_null=True)
    accepted_at = serializers.DateTimeField(read_only=True, allow_null=True)
    preparing_at = serializers.DateTimeField(read_only=True, allow_null=True)
    ready_at = serializers.DateTimeField(read_only=True, allow_null=True)
    picked_up_at = serializers.DateTimeField(read_only=True, allow_null=True)
    delivered_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class MenuCategoryPreviewSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = MenuCategory
        fields = ("id", "name", "description", "items")

    def get_items(self, category):
        items = category.items.filter(is_available=True)
        return MenuItemSerializer(
            items,
            many=True,
            context=self.context,
        ).data


class RestaurantDetailSerializer(RestaurantSerializer):
    categories = serializers.SerializerMethodField()
    menu_items = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()

    class Meta(RestaurantSerializer.Meta):
        fields = RestaurantSerializer.Meta.fields + ("categories", "menu_items", "offers")

    def get_categories(self, restaurant):
        categories = restaurant.menu_categories.filter(is_active=True).prefetch_related("items")
        payload = []
        for category in categories:
            items = category.items.filter(is_available=True)
            if not items.exists():
                continue
            payload.append({
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "items": MenuItemSerializer(items, many=True, context=self.context).data,
            })
        uncategorised = restaurant.menu_items.filter(
            is_available=True,
            menu_category__isnull=True,
        )
        if uncategorised.exists():
            payload.append({
                "id": None,
                "name": "More dishes",
                "description": "",
                "items": MenuItemSerializer(
                    uncategorised, many=True, context=self.context
                ).data,
            })
        return payload

    def get_menu_items(self, restaurant):
        items = restaurant.menu_items.filter(is_available=True).order_by("category", "name")
        return MenuItemSerializer(items, many=True, context=self.context).data

    def get_offers(self, restaurant):
        offers = [offer for offer in restaurant.offers.all() if offer.is_currently_valid]
        return RestaurantOfferSerializer(offers, many=True).data
