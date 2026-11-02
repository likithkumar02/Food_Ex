from django.contrib import admin

from .models import (
    DeliveryAssignment,
    DeliveryAssignmentAttempt,
    DeliveryLocation,
    DeliveryPartnerProfile,
)


class DeliveryAssignmentAttemptInline(admin.TabularInline):
    model = DeliveryAssignmentAttempt
    extra = 0
    can_delete = False
    readonly_fields = (
        "partner",
        "status",
        "rejection_reason",
        "offered_at",
        "responded_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ("order", "partner", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order__id", "partner__username")
    inlines = (DeliveryAssignmentAttemptInline,)


@admin.register(DeliveryAssignmentAttempt)
class DeliveryAssignmentAttemptAdmin(admin.ModelAdmin):
    list_display = ("assignment", "partner", "status", "offered_at", "responded_at")
    list_filter = ("status", "offered_at")
    search_fields = ("assignment__order__code", "assignment__order__id", "partner__username", "rejection_reason")
    readonly_fields = (
        "assignment",
        "partner",
        "status",
        "rejection_reason",
        "offered_at",
        "responded_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryPartnerProfile)
class DeliveryPartnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_online", "vehicle_type", "vehicle_number")
    list_filter = ("is_online", "vehicle_type")
    search_fields = ("user__username", "user__email", "vehicle_number")


@admin.register(DeliveryLocation)
class DeliveryLocationAdmin(admin.ModelAdmin):
    list_display = ("assignment", "latitude", "longitude", "recorded_at")
    list_filter = ("recorded_at",)
