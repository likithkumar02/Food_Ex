from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer


class RestaurantReviewListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, restaurant_id):
        from restaurant.models import Restaurant

        get_object_or_404(Restaurant, pk=restaurant_id, is_active=True)
        reviews = Review.objects.filter(
            restaurant_id=restaurant_id,
            is_hidden=False,
        ).select_related("user")
        return Response(ReviewSerializer(reviews, many=True).data)


class ReviewCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, restaurant_id):
        if request.user.role != "customer":
            return Response({"detail": "Customer account required."}, status=403)
        serializer = ReviewCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=serializer.validated_data["order_id"],
            user=request.user,
            restaurant_id=restaurant_id,
        )
        if order.status != "delivered":
            return Response({"detail": "Only delivered orders can be reviewed."}, status=409)
        if hasattr(order, "review"):
            return Response({"detail": "This order has already been reviewed."}, status=409)
        review = Review.objects.create(
            user=request.user,
            order=order,
            restaurant=order.restaurant,
            rating=serializer.validated_data["rating"],
            comment=serializer.validated_data.get("comment", ""),
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)