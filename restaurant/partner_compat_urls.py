from django.urls import path

from .partner_api_views import (
    PartnerOrderActionAPIView,
    PartnerOrderDetailAPIView,
    PartnerOrderListAPIView,
)


urlpatterns = [
    path("orders/", PartnerOrderListAPIView.as_view(), name="api_restaurant_orders"),
    path(
        "orders/<int:order_id>/",
        PartnerOrderDetailAPIView.as_view(),
        name="api_restaurant_order_detail",
    ),
    path(
        "orders/<int:order_id>/<str:action>/",
        PartnerOrderActionAPIView.as_view(),
        name="api_restaurant_order_action",
    ),
]
