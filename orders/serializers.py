from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    food_type = serializers.CharField(source="menu_item.food_type", read_only=True)
    image = serializers.ImageField(source="menu_item.image", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "menu_item",
            "name",
            "food_type",
            "image",
            "quantity",
            "unit_price",
            "subtotal",
        )


class OrderSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    user_name = serializers.CharField(source="customer_display_name", read_only=True)
    payment_status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "code",
            "restaurant",
            "restaurant_name",
            "user",
            "user_name",
            "items",
            "subtotal",
            "delivery_fee",
            "tax_amount",
            "discount_amount",
            "total_price",
            "status",
            "status_display",
            "payment_status",
            "rejection_reason",
            "rejection_note",
            "estimated_preparation_minutes",
            "delivery_address",
            "delivery_area",
            "delivery_city",
            "delivery_district",
            "delivery_state",
            "delivery_pincode",
            "customer_latitude",
            "customer_longitude",
            "restaurant_latitude",
            "restaurant_longitude",
            "delivery_latitude",
            "delivery_longitude",
            "delivery_location_updated_at",
            "created_at",
            "updated_at",
        )


class OrderCreateSerializer(serializers.Serializer):
    delivery_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
    )
    address_id = serializers.IntegerField(required=False, allow_null=True)
    delivery_latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    delivery_longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    offer_code = serializers.CharField(
        max_length=30, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        latitude = attrs.get("delivery_latitude")
        longitude = attrs.get("delivery_longitude")
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                "Provide both delivery latitude and longitude."
            )
        if attrs.get("address_id") is None and not attrs.get("delivery_address", "").strip():
            raise serializers.ValidationError(
                {"delivery_address": "A delivery address is required."}
            )
        return attrs

    def validate_delivery_address(self, value):
        value = value.strip()
        if value and len(value) < 6:
            raise serializers.ValidationError("Enter a complete delivery address.")
        return value
