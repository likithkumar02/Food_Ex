import json
import re

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

User = get_user_model()

from .decorators import role_required
from .forms import UserRegistrationForm
from .session_utils import get_active_roles, login_role_user, logout_role_user
from customer.models import CustomerProfile
from restaurant.forms import RestaurantRegistrationForm
from restaurant.models import Restaurant
from restaurant.views import restaurant_listing_context


PORTAL_CONFIG = {
    "customer": {
        "label": "Customer",
        "dashboard": "customer_dashboard",
        "template": "portals/customer.html",
        "base_template": "portals/customer_base.html",
        "portal_url": "customer_portal",
        "login_url": "customer_login",
        "register_url": "customer_register",
    },
    "restaurant_owner": {
        "label": "Restaurant Partner",
        "dashboard": "restaurant_dashboard",
        "template": "portals/restaurant.html",
        "base_template": "portals/restaurant_base.html",
        "portal_url": "restaurant_portal",
        "login_url": "restaurant_login",
        "register_url": "restaurant_register",
    },
    "delivery_partner": {
        "label": "Delivery partner",
        "dashboard": "delivery_dashboard",
        "template": "portals/delivery.html",
        "base_template": "portals/delivery_base.html",
        "portal_url": "delivery_portal",
        "login_url": "delivery_login",
        "register_url": "delivery_register",
    },
}


def register_view(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        form.fields["role"].choices = [("customer", "Customer")]
        if form.is_valid():
            user = form.save()
            CustomerProfile.objects.get_or_create(user=user)
            login_role_user(request, user, "customer")
            messages.success(request, "Registration successful.")
            return redirect("home")
    else:
        form = UserRegistrationForm()
        form.fields["role"].choices = [("customer", "Customer")]

    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user_record = User.objects.filter(email__iexact=email).first()
        user = None
        if user_record is not None:
            user = authenticate(
                request,
                username=user_record.get_username(),
                password=password,
            )
        if user is not None:
            login_role_user(request, user, getattr(user, "role", "customer"))
            return redirect("dashboard")
        messages.error(request, "Email or password is incorrect.")

    return render(request, "auth/login.html")


def portal_login_view(request, role):
    portal = PORTAL_CONFIG.get(role)
    if portal is None:
        return redirect("home")

    current_role_user = getattr(request, f"{role}_user", None)
    if current_role_user and current_role_user.is_authenticated:
        return redirect(portal["dashboard"])
    elif request.user.is_authenticated and getattr(request.user, "role", None) == role:
        return redirect(portal["dashboard"])

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user_record = User.objects.filter(email__iexact=email).first()
        user = None
        if user_record is not None:
            user = authenticate(
                request,
                username=user_record.get_username(),
                password=password,
            )
        if user is not None and user.role == role:
            login_role_user(request, user, role)
            messages.success(request, f"Logged in to {portal['label']} successfully.")
            return redirect(portal["dashboard"])
        if user is not None:
            messages.error(
                request,
                f"Those credentials belong to a {user.role.replace('_', ' ').title()} account and do not belong to this portal.",
            )
        else:
            messages.error(request, "Those credentials do not belong to this portal.")

    return render(
        request,
        "auth/portal_login.html",
        {
            "portal": portal,
        },
    )


def portal_register_view(request, role):
    portal = PORTAL_CONFIG.get(role)
    if portal is None:
        return redirect("home")
    if request.user.is_authenticated and request.user.role == role:
        return redirect(portal["dashboard"])

    form_data = request.POST.copy() if request.method == "POST" else None
    if form_data is not None:
        form_data["role"] = role
    form = UserRegistrationForm(form_data, initial={"role": role})
    form.fields["role"].choices = [(role, portal["label"])]
    restaurant_form = None
    if role == "restaurant_owner":
        form.fields["first_name"].label = "Owner first name"
        form.fields["first_name"].required = True
        form.fields["last_name"].label = "Owner last name"
        form.fields["last_name"].required = True
        restaurant_form = RestaurantRegistrationForm(
            request.POST or None,
            request.FILES or None,
        )
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-control")

    registration_errors = []
    phone = request.POST.get("phone", "").strip() if request.method == "POST" else ""
    if request.method == "POST":
        if not re.fullmatch(r"\+?[0-9]{7,15}", phone):
            registration_errors.append("Enter a valid mobile number.")
        elif CustomerProfile.objects.filter(phone_number=phone).exists():
            registration_errors.append("That mobile number is already registered.")

        required_fields = {
            "delivery_partner": {
                "vehicle_type": "Vehicle type",
                "vehicle_number": "Vehicle number",
                "license_number": "Driving license number",
                "address": "Home address",
            },
        }.get(role, {})
        for field, label in required_fields.items():
            if not request.POST.get(field, "").strip():
                registration_errors.append(f"{label} is required.")

    restaurant_form_valid = role != "restaurant_owner" or restaurant_form.is_valid()
    if (
        request.method == "POST"
        and form.is_valid()
        and restaurant_form_valid
        and not registration_errors
    ):
        with transaction.atomic():
            user = form.save()
            CustomerProfile.objects.create(user=user, phone_number=phone)
            if role == "restaurant_owner":
                data = restaurant_form.cleaned_data
                lat = data.get("latitude")
                lon = data.get("longitude")
                Restaurant.objects.create(
                    owner=user,
                    name=data["restaurant_name"],
                    cuisine_type=data["cuisine_type"],
                    restaurant_type=data["restaurant_type"],
                    description=data["description"],
                    image=data["cover_image"],
                    logo=data["logo"],
                    address=data["restaurant_address"],
                    city=data["city"],
                    state=data["state"],
                    pincode=data["pincode"],
                    latitude=lat,
                    longitude=lon,
                    location_updated_at=timezone.now() if lat and lon else None,
                    phone=data["restaurant_phone"],
                    fssai_number=data["fssai_number"],
                    gst_number=data["gst_number"],
                    pan_number=data["pan_number"],
                    bank_account_number=data["bank_account_number"],
                    bank_ifsc_code=data["bank_ifsc_code"],
                    account_holder_name=data["account_holder_name"],
                    status="pending",
                    is_active=False,
                )
            elif role == "delivery_partner":
                from delivery.models import DeliveryPartnerProfile

                DeliveryPartnerProfile.objects.create(
                    user=user,
                    vehicle_type=request.POST["vehicle_type"].strip(),
                    vehicle_number=request.POST["vehicle_number"].strip(),
                    license_number=request.POST["license_number"].strip(),
                    address=request.POST["address"].strip(),
                )
        login_role_user(request, user, role)
        messages.success(request, f"Your {portal['label'].lower()} account is ready.")
        return redirect(portal["dashboard"])

    return render(
        request,
        "auth/portal_register.html",
        {
            "form": form,
            "restaurant_form": restaurant_form,
            "portal": portal,
            "registration_errors": registration_errors,
        },
    )


def customer_portal_view(request):
    return render(request, "restaurant/list.html", restaurant_listing_context(request))


def restaurant_portal_view(request):
    if (
        request.user.is_authenticated and request.user.role == "restaurant_owner"
    ) or (
        getattr(request, "restaurant_user", None)
        and request.restaurant_user.is_authenticated
    ):
        return redirect("restaurant_dashboard")
    return render(
        request,
        "portals/restaurant.html",
        {"wrong_role": False},
    )


def delivery_portal_view(request):
    if (
        request.user.is_authenticated and request.user.role == "delivery_partner"
    ) or (
        getattr(request, "delivery_user", None)
        and request.delivery_user.is_authenticated
    ):
        return redirect("delivery_dashboard")
    return render(
        request,
        "portals/delivery.html",
        {
            "wrong_role": False,
            "customer_session_active": bool(
                getattr(request, "customer_user", None)
                and request.customer_user.is_authenticated
            ),
        },
    )


def customer_logout_view(request):
    if request.method == "POST":
        logout_role_user(request, "customer")
    return redirect("customer_portal")


def delivery_logout_view(request):
    if request.method == "POST":
        logout_role_user(request, "delivery_partner")
    return redirect("delivery_portal")


def logout_view(request):
    if request.method == "POST":
        role = request.POST.get("role") or request.GET.get("role")
        if not role:
            referer = request.META.get("HTTP_REFERER", "")
            if "/delivery/" in referer:
                role = "delivery_partner"
            elif "/restaurant/" in referer or "/restaurant-partner/" in referer:
                role = "restaurant_owner"
            elif "/customer/" in referer:
                role = "customer"

        if role:
            logout_role_user(request, role)
            if role == "delivery_partner":
                return redirect("delivery_portal")
            elif role == "restaurant_owner":
                return redirect("restaurant_portal")
            return redirect("customer_portal")

        logout(request)
    return redirect("home")


def forgot_password_view(request):
    form = PasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save(
            request=request,
            email_template_name="auth/password_reset_email.txt",
            subject_template_name="auth/password_reset_subject.txt",
        )
        return redirect("password_reset_done")
    return render(request, "auth/forgot_password.html", {"form": form})


@login_required
def settings_view(request):
    role = getattr(request.user, "role", None)
    if role == "restaurant_owner":
        return redirect("restaurant_account_settings")

    context = {
        "user": request.user,
        "portal": PORTAL_CONFIG.get(role),
    }
    if role == "delivery_partner":
        from delivery.models import DeliveryPartnerProfile

        context["partner_profile"], _ = DeliveryPartnerProfile.objects.get_or_create(
            user=request.user
        )

    return render(request, "auth/settings.html", context)


@login_required
def delete_account_view(request):
    user = request.user
    if request.method == "POST":
        if user.is_superuser:
            messages.error(request, "Superuser accounts cannot be deleted.")
            return redirect("settings")

        username = user.username
        role = getattr(user, "role", "customer")

        # Clean role session and standard session
        logout_role_user(request, role)
        logout(request)

        # Delete user
        user.delete()
        messages.success(request, f"Your {role.replace('_', ' ')} account '{username}' has been permanently deleted.")

        if role == "delivery_partner":
            return redirect("delivery_portal")
        elif role == "restaurant_owner":
            return redirect("restaurant_portal")
        return redirect("customer_portal")

    return render(request, "auth/delete_account_confirm.html", {"user": user})


@role_required("admin")
def admin_delete_user_view(request, user_id):
    if request.method == "POST":
        target_user = get_object_or_404(User, pk=user_id)
        if target_user.pk == request.user.pk:
            messages.error(request, "You cannot delete your own admin account.")
            return redirect("admin_dashboard")
        username = target_user.username
        role = target_user.role
        target_user.delete()
        messages.success(request, f"User '{username}' ({role}) has been permanently deleted.")
    return redirect("admin_dashboard")


@login_required
def password_change_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed.")
        return redirect("settings")
    return render(request, "auth/password_change.html", {"form": form})


def api_signup_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST request required."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip()
    password = data.get("password") or data.get("password1")
    role = "customer"

    if not username or not email or not password:
        return JsonResponse({"success": False, "error": "Username, email, and password are required."}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"success": False, "error": "Username already exists."}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"success": False, "error": "Email already in use."}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=role,
    )
    login(request, user)
    return JsonResponse(
        {
            "success": True,
            "message": "Registration successful.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
        },
        status=201,
    )


def api_login_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST request required."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)

    username_or_email = str(data.get("username_or_email") or data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username_or_email or not password:
        return JsonResponse({"success": False, "error": "Username/email and password are required."}, status=400)

    user = None
    if "@" in username_or_email:
        user = User.objects.filter(email__iexact=username_or_email).first()
    if user is None:
        user = User.objects.filter(username__iexact=username_or_email).first()

    if user is None or not user.check_password(password):
        return JsonResponse({"success": False, "error": "Invalid credentials."}, status=401)

    login(request, user)
    return JsonResponse(
        {
            "success": True,
            "message": "Login successful.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
        }
    )


def api_forgot_password_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST request required."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)

    form = PasswordResetForm({"email": str(data.get("email", "")).strip()})
    if not form.is_valid():
        return JsonResponse(
            {"success": False, "errors": form.errors.get_json_data()},
            status=400,
        )
    form.save(
        request=request,
        email_template_name="auth/password_reset_email.txt",
        subject_template_name="auth/password_reset_subject.txt",
    )
    return JsonResponse({
        "success": True,
        "message": "If an account exists, reset instructions were sent.",
    })


@login_required
def api_password_change_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST request required."}, status=405)
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)

    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")
    if not request.user.check_password(old_password):
        return JsonResponse({"success": False, "error": "Current password is incorrect."}, status=400)
    if new_password != confirm_password:
        return JsonResponse({"success": False, "error": "Passwords do not match."}, status=400)
    try:
        validate_password(new_password, user=request.user)
    except ValidationError as error:
        return JsonResponse({"success": False, "errors": error.messages}, status=400)

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)
    return JsonResponse({"success": True, "message": "Password changed successfully."})


def api_profile_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Authentication required."}, status=401)

    return JsonResponse({
        "success": True,
        "user": {
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "role": request.user.role,
        },
    })


@login_required
def dashboard_view(request):
    role_routes = {
        "customer": "customer_dashboard",
        "restaurant_owner": "restaurant_dashboard",
        "delivery_partner": "delivery_dashboard",
        "admin": "admin_dashboard",
    }
    route_name = role_routes.get(request.user.role, "home")
    return redirect(route_name)


def customer_dashboard_view(request):
    is_customer_authenticated = (
        request.user.is_authenticated and request.user.role == "customer"
    )
    state = request.GET.get("state", "").strip()

    if not is_customer_authenticated:
        return render(
            request,
            "dashboard/customer.html",
            {
                "show_auth_prompt": True,
            },
        )

    profile = CustomerProfile.objects.filter(user=request.user).first()
    if not state and profile:
        state = profile.state.strip()

    return render(
        request,
        "dashboard/customer.html",
        {
            "show_auth_prompt": False,
            "restaurants": _customer_restaurants_for_state(state),
            "state": state,
            "customer_profile": profile,
        },
    )


def _customer_restaurants_for_state(state):
    restaurants = Restaurant.objects.filter(
        status="approved",
        is_active=True,
    )
    if state:
        restaurants = restaurants.filter(
            Q(state__icontains=state) | Q(address__icontains=state)
        )
    return restaurants.order_by("name")[:6]


@role_required("restaurant_owner")
def restaurant_dashboard_view(request):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    approved = bool(restaurant and restaurant.status == "approved" and restaurant.is_active)
    orders = restaurant.orders.order_by("-created_at") if approved else []
    return render(
        request,
        "dashboard/restaurant.html",
        {
            "restaurant": restaurant,
            "approved": approved,
            "menu_items": restaurant.menu_items.all()[:8] if approved else [],
            "orders": orders[:5],
            "order_count": orders.count() if approved else 0,
            "pending_count": orders.filter(status="pending").count() if approved else 0,
            "menu_count": restaurant.menu_items.count() if approved else 0,
        },
    )


@login_required
@role_required("delivery_partner")
def delivery_dashboard_view(request):
    from delivery.models import DeliveryAssignment

    assignments = DeliveryAssignment.objects.filter(partner=request.user).order_by(
        "-created_at"
    )
    return render(
        request,
        "dashboard/delivery.html",
        {
            "assignments": assignments[:5],
            "active_count": assignments.exclude(
                status__in=["delivered", "cancelled"]
            ).count(),
            "delivery_count": assignments.count(),
        },
    )


@login_required
@role_required("admin")
def admin_dashboard_view(request):
    from datetime import datetime, time, timedelta

    from django.db.models import Count, Sum
    from django.utils import timezone

    from delivery.models import DeliveryPartnerProfile
    from orders.models import Order
    from restaurant.models import RestaurantEarning

    try:
        days = int(request.GET.get("range", "7"))
    except (TypeError, ValueError):
        days = 7
    if days not in (7, 30, 90):
        days = 7

    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)

    users = User.objects.all().order_by("username")
    orders = Order.objects.all()
    earnings = RestaurantEarning.objects.exclude(status="cancelled")

    order_totals = orders.aggregate(
        total=Count("id"),
        delivered=Count(
            "id",
            filter=Q(status=Order.STATUS_DELIVERED),
        ),
        active=Count(
            "id",
            filter=Q(status__in=Order.LIVE_STATUSES),
        ),
        cancelled=Count(
            "id",
            filter=Q(
                status__in=(Order.STATUS_CANCELLED, Order.STATUS_REJECTED),
            ),
        ),
    )
    financial_totals = earnings.aggregate(
        platform_commission=Sum("commission_amount"),
        platform_fee=Sum("platform_fee"),
        restaurant_payouts=Sum("restaurant_amount"),
        delivery_earnings=Sum("rider_payout"),
    )
    period_start = timezone.make_aware(datetime.combine(start_date, time.min))
    period_end = timezone.make_aware(
        datetime.combine(today + timedelta(days=1), time.min),
    )
    chart_days = []
    daily_order_aggregates = {}
    daily_earning_aggregates = {}
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        day_start = timezone.make_aware(datetime.combine(day, time.min))
        day_end = timezone.make_aware(
            datetime.combine(day + timedelta(days=1), time.min),
        )
        chart_days.append(day)
        day_filter = Q(created_at__gte=day_start, created_at__lt=day_end)
        daily_order_aggregates[f"orders_{offset}"] = Count(
            "id",
            filter=day_filter,
        )
        daily_order_aggregates[f"delivered_{offset}"] = Count(
            "id",
            filter=day_filter & Q(status=Order.STATUS_DELIVERED),
        )
        daily_earning_aggregates[f"commission_{offset}"] = Sum(
            "commission_amount",
            filter=day_filter,
        )
        daily_earning_aggregates[f"platform_fee_{offset}"] = Sum(
            "platform_fee",
            filter=day_filter,
        )

    daily_order_totals = orders.filter(
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).aggregate(**daily_order_aggregates)
    daily_earning_totals = earnings.filter(
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).aggregate(**daily_earning_aggregates)
    chart_labels = []
    chart_orders = []
    chart_delivered = []
    chart_revenue = []
    for offset, day in enumerate(chart_days):
        chart_labels.append(day.strftime("%b %d"))
        chart_orders.append(daily_order_totals[f"orders_{offset}"])
        chart_delivered.append(daily_order_totals[f"delivered_{offset}"])
        chart_revenue.append(
            float(
                (daily_earning_totals[f"commission_{offset}"] or 0)
                + (daily_earning_totals[f"platform_fee_{offset}"] or 0)
            )
        )

    recent_orders = (
        orders.select_related("restaurant")
        .order_by("-updated_at", "-pk")[:8]
    )
    pending_restaurants = (
        Restaurant.objects.filter(status="pending")
        .select_related("owner")
        .order_by("created_at")[:5]
    )
    context = {
        "users": users,
        "range_days": days,
        "chart_data": {
            "labels": chart_labels,
            "orders": chart_orders,
            "delivered": chart_delivered,
            "platform_revenue": chart_revenue,
        },
        "metrics": {
            "customers": User.objects.filter(role="customer").count(),
            "restaurants": Restaurant.objects.count(),
            "delivery_partners": User.objects.filter(role="delivery_partner").count(),
            "online_partners": DeliveryPartnerProfile.objects.filter(
                is_online=True,
            ).count(),
            "orders": order_totals["total"],
            "active_orders": order_totals["active"],
            "completed_orders": order_totals["delivered"],
            "cancelled_orders": order_totals["cancelled"],
            "platform_revenue": (
                financial_totals["platform_commission"] or 0
            ) + (financial_totals["platform_fee"] or 0),
            "restaurant_payouts": financial_totals["restaurant_payouts"] or 0,
            "delivery_earnings": financial_totals["delivery_earnings"] or 0,
        },
        "recent_orders": recent_orders,
        "pending_restaurants": pending_restaurants,
        "pending_restaurant_count": Restaurant.objects.filter(
            status="pending",
        ).count(),
    }
    return render(request, "dashboard/admin.html", context)
