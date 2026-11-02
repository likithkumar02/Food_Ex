from django.urls import path

from orders.views import order_detail_view

from .views import customer_profile_view, order_review_view


urlpatterns = [
    path("profile/", customer_profile_view, name="customer_profile"),
    path("orders/<int:order_id>/review/", order_review_view, name="order_review"),
    path(
        "orders/<int:order_id>/track/",
        order_detail_view,
        name="customer_order_track",
    ),
]
