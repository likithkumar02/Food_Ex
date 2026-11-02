from django.urls import path

from .views import (
    add_to_cart_view,
    cart_view,
    cart_item_update_view,
    checkout_view,
    order_accept_view,
    order_assign_delivery_partner_view,
    order_cancel_view,
    order_detail_view,
    order_history_view,
    order_preparing_view,
    order_ready_view,
    order_reject_view,
    restaurant_order_management_view,
)


urlpatterns = [
    path("cart/", cart_view, name="cart"),
    path("cart/add/<int:menu_item_id>/", add_to_cart_view, name="add_to_cart"),
    path(
        "cart/items/<int:item_id>/<str:action>/",
        cart_item_update_view,
        name="cart_item_update",
    ),
    path("checkout/", checkout_view, name="checkout"),
    path("orders/", order_history_view, name="orders_index"),
    path("orders/<int:order_id>/", order_detail_view, name="order_detail"),
    path("<int:order_id>/", order_detail_view, name="order_detail_direct"),
    path("orders/history/", order_history_view, name="order_history"),
    path("restaurant/orders/", restaurant_order_management_view, name="restaurant_order_management"),
    path("restaurant/orders/<int:order_id>/accept/", order_accept_view, name="order_accept"),
    path(
        "restaurant/orders/<int:order_id>/assign-delivery/",
        order_assign_delivery_partner_view,
        name="order_assign_delivery_partner",
    ),
    path("restaurant/orders/<int:order_id>/reject/", order_reject_view, name="order_reject"),
    path("restaurant/orders/<int:order_id>/cancel/", order_cancel_view, name="order_cancel"),
    path("restaurant/orders/<int:order_id>/preparing/", order_preparing_view, name="order_preparing"),
    path("restaurant/orders/<int:order_id>/ready/", order_ready_view, name="order_ready"),
]
