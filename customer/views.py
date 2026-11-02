import re

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from orders.models import Order

from .models import CustomerProfile, Review

User = get_user_model()


@login_required
def customer_profile_view(request):
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        email = request.POST.get("email", request.user.email).strip()
        phone_number = request.POST.get("phone_number", profile.phone_number or "").strip()
        errors = []

        try:
            validate_email(email)
        except ValidationError:
            errors.append("Enter a valid email address.")
        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            errors.append("An account with this email already exists.")

        if phone_number and not re.fullmatch(r"\+?[0-9]{7,15}", phone_number):
            errors.append("Enter a valid mobile number.")
        elif phone_number and CustomerProfile.objects.filter(
            phone_number=phone_number
        ).exclude(user=request.user).exists():
            errors.append("An account with this mobile number already exists.")

        image = request.FILES.get("profile_image")
        if image and image.size > 5 * 1024 * 1024:
            errors.append("Profile images must be 5 MB or smaller.")

        if errors:
            return render(request, "customer/profile.html", {
                "profile": profile,
                "errors": errors,
                "submitted": request.POST,
            })

        request.user.first_name = request.POST.get("first_name", request.user.first_name).strip()
        request.user.last_name = request.POST.get("last_name", request.user.last_name).strip()
        request.user.email = email
        profile.phone_number = phone_number or None
        profile.address = request.POST.get("address", profile.address).strip()
        profile.address_line = request.POST.get("address_line", profile.address_line or "").strip()
        profile.area = request.POST.get("area", profile.area or "").strip()
        profile.city = request.POST.get("city", profile.city or "").strip()
        profile.district = request.POST.get("district", profile.district or "").strip()
        profile.state = request.POST.get("state", profile.state or "").strip()
        profile.pincode = request.POST.get("pincode", profile.pincode or "").strip()
        if image:
            profile.profile_image = image
        request.user.save(update_fields=["first_name", "last_name", "email"])
        profile.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("customer_profile")

    recent_orders = request.user.orders.select_related("restaurant").order_by("-created_at")[:5]
    return render(
        request,
        "customer/profile.html",
        {
            "profile": profile,
            "recent_orders": recent_orders,
            "orders_count": request.user.orders.count(),
        },
    )


@role_required("customer")
@require_POST
def order_review_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.status != "delivered":
        messages.error(request, "You can review an order after it is delivered.")
        return redirect("order_detail", order_id=order.pk)
    if hasattr(order, "review"):
        messages.error(request, "This order has already been reviewed.")
        return redirect("order_detail", order_id=order.pk)

    try:
        rating = int(request.POST.get("rating", ""))
    except ValueError:
        rating = 0
    if not 1 <= rating <= 5:
        messages.error(request, "Choose a rating from 1 to 5.")
        return redirect("order_detail", order_id=order.pk)

    Review.objects.create(
        user=request.user,
        order=order,
        restaurant=order.restaurant,
        rating=rating,
        comment=request.POST.get("comment", "").strip(),
    )
    messages.success(request, "Thanks for reviewing this restaurant.")
    return redirect("order_detail", order_id=order.pk)
