from django.urls import path

from location.api_views import OrderDeliveryLocationAPIView, OrderRouteAPIView
from .api_views import (
    CartAPIView,
    CartItemAPIView,
    CheckoutSummaryAPIView,
    OrderDetailAPIView,
    OrderListCreateAPIView,
    OrderStatusAPIView,
)


urlpatterns = [
    path("cart/", CartAPIView.as_view(), name="api_cart"),
    path("cart/summary/", CheckoutSummaryAPIView.as_view(), name="api_cart_summary"),
    path("cart/items/<int:item_id>/", CartItemAPIView.as_view(), name="api_cart_item"),
    path("orders/", OrderListCreateAPIView.as_view(), name="api_orders"),
    path("orders/<int:order_id>/", OrderDetailAPIView.as_view(), name="api_order_detail"),
    path("orders/<int:order_id>/status/", OrderStatusAPIView.as_view(), name="api_order_status"),
    path("orders/<int:order_id>/delivery-location/", OrderDeliveryLocationAPIView.as_view(), name="api_order_delivery_location_alt"),
    path("orders/<int:order_id>/tracking/", OrderDeliveryLocationAPIView.as_view(), name="api_order_tracking"),
    path("orders/<int:order_id>/route/", OrderRouteAPIView.as_view(), name="api_order_route_alt"),
]
