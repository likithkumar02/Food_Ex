from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import User
from customer.models import CustomerAddress, CustomerProfile
from delivery.models import DeliveryPartnerProfile
from orders.models import Order
from restaurant.models import Restaurant

from .models import LocationSetting


@role_required("admin")
def admin_location_dashboard_view(request):
    """Admin dashboard dedicated to live GPS monitoring across the platform."""
    setting = LocationSetting.load()
    total_customers = User.objects.filter(role="customer").count()
    total_restaurants = Restaurant.objects.count()
    online_partners = DeliveryPartnerProfile.objects.filter(is_online=True).count()
    active_deliveries = Order.objects.filter(status__in=Order.LIVE_STATUSES).count()

    return render(
        request,
        "location/admin_location.html",
        {
            "setting": setting,
            "metrics": {
                "total_customers": total_customers,
                "total_restaurants": total_restaurants,
                "online_partners": online_partners,
                "active_deliveries": active_deliveries,
            },
        },
    )


@role_required("customer")
def customer_location_view(request):
    """Customer page to manage saved addresses and current location."""
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    addresses = CustomerAddress.objects.filter(user=request.user)
    latest_order = (
        Order.objects.filter(user=request.user)
        .select_related("restaurant")
        .order_by("-created_at")
        .first()
    )
    setting = LocationSetting.load()

    return render(
        request,
        "location/customer_location.html",
        {
            "profile": profile,
            "addresses": addresses,
            "latest_order": latest_order,
            "setting": setting,
        },
    )


@role_required("restaurant_owner")
def restaurant_location_view(request):
    """Restaurant partner page to view and set store location on map."""
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    if not restaurant:
        return redirect("restaurant_management")
    setting = LocationSetting.load()

    return render(
        request,
        "location/restaurant_location.html",
        {
            "restaurant": restaurant,
            "setting": setting,
        },
    )
