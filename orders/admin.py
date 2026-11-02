from django.contrib import admin, messages

from .models import Cart, CartItem, Order, OrderItem, OrderStatusEvent


@admin.action(description="Retry delivery-partner assignment")
def retry_delivery_assignment_action(modeladmin, request, queryset):
    from delivery.services import retry_delivery_assignment

    queued = 0
    for order in queryset:
        assignment = retry_delivery_assignment(order.pk, actor=request.user)
        if assignment is not None:
            queued += 1

    if queued:
        messages.success(
            request,
            f"Delivery assignment retried for {queued} order(s).",
        )
    if queued < queryset.count():
        messages.warning(
            request,
            "Some selected orders could not be retried. Check their status and available partners.",
        )


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "total_items", "total_price")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "menu_item", "quantity", "subtotal")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "restaurant", "status", "total_price", "created_at")
    list_filter = ("status",)
    actions = (retry_delivery_assignment_action,)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "menu_item", "quantity", "unit_price", "subtotal")


@admin.register(OrderStatusEvent)
class OrderStatusEventAdmin(admin.ModelAdmin):
    list_display = ("order", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("order__code", "order__id", "reason", "actor__username")
    readonly_fields = (
        "order",
        "from_status",
        "to_status",
        "actor",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
