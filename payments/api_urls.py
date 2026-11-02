from django.urls import path

from .api_views import OrderPaymentAPIView


urlpatterns = [
    path("orders/<int:order_id>/pay/", OrderPaymentAPIView.as_view(), name="api_order_payment"),
]