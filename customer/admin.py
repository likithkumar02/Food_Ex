from django.contrib import admin

from .models import CustomerProfile, Review


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "phone_number", "city")
	search_fields = ("user__username", "user__email", "phone_number")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
	list_display = ("restaurant", "user", "rating", "order", "created_at")
	list_filter = ("rating", "created_at")
	search_fields = ("restaurant__name", "user__email", "comment")
