from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MenuItem, Restaurant
from .serializers import (
    MenuItemSerializer,
    RestaurantDetailSerializer,
    RestaurantSerializer,
)


class RestaurantListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        restaurants = Restaurant.objects.filter(
            status="approved",
            is_active=True,
        ).order_by("name")
        query = request.query_params.get("q", "").strip()
        if query:
            restaurants = restaurants.filter(
                Q(name__icontains=query)
                | Q(cuisine_type__icontains=query)
                | Q(address__icontains=query)
                | Q(description__icontains=query)
                | Q(menu_items__name__icontains=query)
            ).distinct()
        return Response(RestaurantSerializer(restaurants, many=True).data)


class RestaurantDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, restaurant_id):
        restaurant = get_object_or_404(
            Restaurant.objects.prefetch_related("menu_items"),
            pk=restaurant_id,
            status="approved",
            is_active=True,
        )
        return Response(RestaurantDetailSerializer(restaurant).data)


class RestaurantMenuAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, restaurant_id):
        restaurant = get_object_or_404(
            Restaurant,
            pk=restaurant_id,
            status="approved",
            is_active=True,
        )
        items = restaurant.menu_items.filter(is_available=True).order_by("category", "name")
        return Response(MenuItemSerializer(items, many=True).data)


def owned_restaurant(user):
    if user.role != "restaurant_owner":
        return None
    return Restaurant.objects.filter(owner=user).first()


class RestaurantMenuManageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        restaurant = owned_restaurant(request.user)
        if restaurant is None:
            return Response({"detail": "Restaurant profile not found."}, status=404)
        items = restaurant.menu_items.order_by("category", "name")
        return Response(MenuItemSerializer(items, many=True).data)

    def post(self, request):
        restaurant = owned_restaurant(request.user)
        if restaurant is None:
            return Response({"detail": "Restaurant profile not found."}, status=404)
        serializer = MenuItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        item = serializer.save(restaurant=restaurant)
        return Response(MenuItemSerializer(item).data, status=status.HTTP_201_CREATED)


class RestaurantMenuItemManageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _owned_item(self, request, item_id):
        restaurant = owned_restaurant(request.user)
        if restaurant is None:
            return None
        return MenuItem.objects.filter(pk=item_id, restaurant=restaurant).first()

    def put(self, request, item_id):
        return self._update(request, item_id, partial=False)

    def patch(self, request, item_id):
        return self._update(request, item_id, partial=True)

    def _update(self, request, item_id, partial):
        item = self._owned_item(request, item_id)
        if item is None:
            return Response({"detail": "Menu item not found."}, status=404)
        serializer = MenuItemSerializer(item, data=request.data, partial=partial)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, item_id):
        item = self._owned_item(request, item_id)
        if item is None:
            return Response({"detail": "Menu item not found."}, status=404)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)