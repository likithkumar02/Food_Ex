from django.urls import path

from .views import (
    restaurant_account_settings_view,
    restaurant_detail_view,
    restaurant_list_view,
    restaurant_management_view,
)


urlpatterns = [
    path("restaurants/", restaurant_list_view, name="restaurant_list"),
    path("restaurants/<int:restaurant_id>/", restaurant_detail_view, name="restaurant_detail"),
    path("restaurants/manage/", restaurant_management_view, name="restaurant_management"),
    path("restaurant/account-settings/", restaurant_account_settings_view, name="restaurant_account_settings"),
]
