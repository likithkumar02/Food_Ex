from django.contrib import admin
from customer.models import CustomerAddress
from .models import LocationSetting


@admin.register(LocationSetting)
class LocationSettingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "default_latitude",
        "default_longitude",
        "min_update_interval_seconds",
        "min_movement_meters",
        "partner_location_max_age_seconds",
        "delivery_assignment_accept_timeout_seconds",
        "delivery_assignment_max_attempts",
        "delivery_assignment_initial_radius_km",
        "delivery_assignment_max_radius_km",
        "updated_at",
    )


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "city", "state", "latitude", "longitude", "is_default", "created_at")
    search_fields = ("name", "address", "city", "user__username", "user__email")
    list_filter = ("is_default", "city", "state")
