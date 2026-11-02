from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "customer_name", "rating", "comment", "created_at")
        read_only_fields = ("id", "customer_name", "created_at")

    def get_customer_name(self, review):
        return review.user.first_name or review.user.username


class ReviewCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)