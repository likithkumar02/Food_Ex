from django.urls import path

from .views import payment_page


urlpatterns = [
    path("orders/<int:order_id>/payment/", payment_page, name="payment_page"),
]
