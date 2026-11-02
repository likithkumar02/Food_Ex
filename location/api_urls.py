from django.urls import path

from .api_views import (
    AdminLiveGPSAPIView,
    CustomerAddressDetailAPIView,
    CustomerLocationUpdateAPIView,
    CustomerSavedAddressesAPIView,
    DeliveryLocationUpdateAPIView,
    DetectLocationAPIView,
    NearbyDeliveryPartnersAPIView,
    NearbyRestaurantsAPIView,
    OrderDeliveryLocationAPIView,
    OrderRouteAPIView,
    RestaurantLocationUpdateAPIView,
)

urlpatterns = [
    # Location auto-detection
    path("detect/", DetectLocationAPIView.as_view(), name="api_location_detect"),
    # Customer
    path("customer/update/", CustomerLocationUpdateAPIView.as_view(), name="api_location_customer_update"),
    path("customer/addresses/", CustomerSavedAddressesAPIView.as_view(), name="api_location_customer_addresses"),
    path("customer/addresses/<int:address_id>/", CustomerAddressDetailAPIView.as_view(), name="api_location_customer_address_detail"),

    # Restaurant
    path("restaurant/update/", RestaurantLocationUpdateAPIView.as_view(), name="api_location_restaurant_update"),

    # Delivery
    path("delivery/update/", DeliveryLocationUpdateAPIView.as_view(), name="api_location_delivery_update"),

    # Nearby restaurants discovery
    path("restaurants/nearby/", NearbyRestaurantsAPIView.as_view(), name="api_location_nearby_restaurants"),
    path(
        "nearby/restaurants/",
        NearbyRestaurantsAPIView.as_view(),
        name="api_location_nearby_restaurants_short",
    ),
    path(
        "nearby/delivery-partners/",
        NearbyDeliveryPartnersAPIView.as_view(),
        name="api_location_nearby_delivery_partners",
    ),

    # Order tracking
    path("orders/<int:order_id>/delivery-location/", OrderDeliveryLocationAPIView.as_view(), name="api_order_delivery_location"),
    path("orders/<int:order_id>/route/", OrderRouteAPIView.as_view(), name="api_order_route"),

    # Admin live GPS
    path("admin/live/", AdminLiveGPSAPIView.as_view(), name="api_location_admin_live"),
]
