from django.contrib import admin

from .models import MenuItem, Restaurant


@admin.action(description="Approve selected restaurants")
def approve_restaurants(modeladmin, request, queryset):
    queryset.update(status="approved", is_active=True, status_reason="")


@admin.action(description="Reject selected restaurants")
def reject_restaurants(modeladmin, request, queryset):
    queryset.update(status="rejected", is_active=False)


@admin.action(description="Suspend selected restaurants")
def suspend_restaurants(modeladmin, request, queryset):
    queryset.update(status="suspended", is_active=False)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "city", "status", "is_active")
    list_filter = ("status", "is_active", "restaurant_type")
    search_fields = ("name", "owner__username", "city", "state", "fssai_number")
    readonly_fields = ("masked_bank_account_number",)
    actions = (approve_restaurants, reject_restaurants, suspend_restaurants)

    @admin.display(description="Bank account")
    def masked_bank_account_number(self, obj):
        account_number = obj.bank_account_number
        if not account_number:
            return "Not provided"
        return f"Ending in {account_number[-4:]}"


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "price", "category", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name", "restaurant__name")
