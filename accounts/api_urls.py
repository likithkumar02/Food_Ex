from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .api_views import (
    CustomerLoginAPIView,
    CustomerLogoutAPIView,
    DeleteAccountAPIView,
    DeliveryLoginAPIView,
    DeliveryLogoutAPIView,
    DeliveryRegisterAPIView,
    LoginAPIView,
    LogoutAPIView,
    ProfileAPIView,
    RegisterAPIView,
    RestaurantLoginAPIView,
    RestaurantRegisterAPIView,
)


urlpatterns = [
    path("customer/register/", RegisterAPIView.as_view(), name="api_customer_register"),
    path("customer/login/", CustomerLoginAPIView.as_view(), name="api_customer_login"),
    path("customer/logout/", CustomerLogoutAPIView.as_view(), name="api_customer_logout"),
    path("restaurant/register/", RestaurantRegisterAPIView.as_view(), name="api_restaurant_register"),
    path("restaurant/login/", RestaurantLoginAPIView.as_view(), name="api_restaurant_login"),
    path("delivery/register/", DeliveryRegisterAPIView.as_view(), name="api_delivery_register"),
    path("delivery/login/", DeliveryLoginAPIView.as_view(), name="api_delivery_login"),
    path("delivery/logout/", DeliveryLogoutAPIView.as_view(), name="api_delivery_logout"),
    path("register/", RegisterAPIView.as_view(), name="auth_register_api"),
    path("login/", LoginAPIView.as_view(), name="auth_login_api"),
    path("profile/", ProfileAPIView.as_view(), name="auth_profile_api"),
    path("delete-account/", DeleteAccountAPIView.as_view(), name="auth_delete_account_api"),
    path("logout/", LogoutAPIView.as_view(), name="auth_logout_api"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth_token_refresh"),
]