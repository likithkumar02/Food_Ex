from django.urls import path

from . import views

urlpatterns = [
    path("", views.customer_location_view, name="location_index"),
    path("customer/", views.customer_location_view, name="location_customer"),
    path("restaurant/", views.restaurant_location_view, name="location_restaurant"),
    path("admin/", views.admin_location_dashboard_view, name="location_admin"),
]

