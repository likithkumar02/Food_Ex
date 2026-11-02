from django.urls import path

from .admin_views import (
    AdminPlatformSettingsAPIView,
    AdminRestaurantActionAPIView,
    AdminRestaurantCommissionAPIView,
    AdminRestaurantListAPIView,
    AdminReviewModerateAPIView,
)


urlpatterns = [
    path("restaurants/", AdminRestaurantListAPIView.as_view(), name="api_admin_restaurant_list"),
    path("restaurants/<int:restaurant_id>/<str:action>/", AdminRestaurantActionAPIView.as_view(), name="api_admin_restaurant_action"),
    path("restaurants/<int:restaurant_id>/commission/", AdminRestaurantCommissionAPIView.as_view(), name="api_admin_restaurant_commission"),
    path("platform/settings/", AdminPlatformSettingsAPIView.as_view(), name="api_admin_platform_settings"),
    path("reviews/<int:review_id>/moderate/", AdminReviewModerateAPIView.as_view(), name="api_admin_review_moderate"),
]
