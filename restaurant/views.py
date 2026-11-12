from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import role_required
from customer.models import CustomerProfile

from .forms import RestaurantOwnerAccountForm, RestaurantProfileForm
from .models import MenuItem, Restaurant


def restaurant_list_view(request):
    target = reverse("customer_portal")
    query_string = request.GET.urlencode()
    if query_string:
        target = f"{target}?{query_string}"
    return redirect(target)


def restaurant_listing_context(request):
    query = request.GET.get("q", "").strip()
    area = request.GET.get("area", "").strip()
    city = request.GET.get("city", "").strip()
    state = request.GET.get("state", "").strip()
    district = request.GET.get("district", "").strip()
    lat = request.GET.get("lat", "").strip() or request.GET.get("latitude", "").strip()
    lon = request.GET.get("lon", "").strip() or request.GET.get("longitude", "").strip()

    # An explicitly empty state means the customer selected "All states".
    location_was_selected = any(
        key in request.GET
        for key in ("state", "district", "city", "area", "lat", "latitude")
    )
    if not location_was_selected and not (state or district or city or area or lat):
        if request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
            profile = getattr(request.user, "customer_profile", None)
            if profile:
                state = profile.state or ""
                district = profile.district or ""
                city = profile.city or ""
                area = profile.area or ""
                if profile.latitude and profile.longitude:
                    lat = str(profile.latitude)
                    lon = str(profile.longitude)
        else:
            state = request.session.get("user_state", "") or request.COOKIES.get("user_state", "")
            district = request.session.get("user_district", "") or request.COOKIES.get("user_district", "")
            city = request.session.get("user_city", "") or request.COOKIES.get("user_city", "")
            area = request.session.get("user_area", "") or request.COOKIES.get("user_area", "")
            lat = request.session.get("user_lat", "") or request.COOKIES.get("user_lat", "")
            lon = request.session.get("user_lon", "") or request.COOKIES.get("user_lon", "")

    restaurants = Restaurant.objects.filter(
        status="approved",
        is_active=True,
    ).prefetch_related("menu_items").order_by("name")
    states = (
        Restaurant.objects.filter(status="approved", is_active=True)
        .exclude(state="")
        .values_list("state", flat=True)
        .distinct()
        .order_by("state")
    )

    filter_label = None
    fallback_reason = None

    # Filter State & District wise first
    if district and state:
        district_terms = [district]
        first_word = district.split()[0]
        if len(first_word) >= 4 and first_word not in district_terms:
            district_terms.append(first_word)
        if "bengaluru" in district.lower():
            district_terms.append("Bangalore")
        elif "bangalore" in district.lower():
            district_terms.append("Bengaluru")

        district_q = models.Q()
        for term in district_terms:
            district_q |= (
                models.Q(district__icontains=term) |
                models.Q(city__icontains=term) |
                models.Q(address__icontains=term)
            )

        district_qs = restaurants.filter(models.Q(state__icontains=state) & district_q)
        if district_qs.exists():
            restaurants = district_qs
            filter_label = f"Showing nearby restaurants in {district}, {state}"
        else:
            state_qs = restaurants.filter(
                models.Q(state__icontains=state) | models.Q(address__icontains=state)
            )
            if state_qs.exists():
                restaurants = state_qs
                filter_label = f"Showing restaurants in {state} (none in {district} yet)"
            else:
                filter_label = f"Showing all restaurants (none in {district}, {state} yet)"
                fallback_reason = f"No approved restaurants in {state} yet"
    elif city and state:
        city_terms = [city]
        first_word = city.split()[0]
        if len(first_word) >= 4 and first_word not in city_terms:
            city_terms.append(first_word)
        if "bengaluru" in city.lower():
            city_terms.append("Bangalore")
        elif "bangalore" in city.lower():
            city_terms.append("Bengaluru")

        city_q = models.Q()
        for term in city_terms:
            city_q |= (
                models.Q(city__icontains=term) |
                models.Q(district__icontains=term) |
                models.Q(address__icontains=term)
            )

        city_qs = restaurants.filter(models.Q(state__icontains=state) & city_q)
        if city_qs.exists():
            restaurants = city_qs
            filter_label = f"Showing restaurants in {city}, {state}"
        else:
            state_qs = restaurants.filter(
                models.Q(state__icontains=state) | models.Q(address__icontains=state)
            )
            if state_qs.exists():
                restaurants = state_qs
                filter_label = f"Showing restaurants in {state} (none in {city} yet)"
            else:
                filter_label = f"Showing all restaurants (none in {city}, {state} yet)"
                fallback_reason = f"No approved restaurants in {state} yet"
    elif district:
        district_terms = [district]
        first_word = district.split()[0]
        if len(first_word) >= 4 and first_word not in district_terms:
            district_terms.append(first_word)
        if "bengaluru" in district.lower():
            district_terms.append("Bangalore")
        elif "bangalore" in district.lower():
            district_terms.append("Bengaluru")

        district_q = models.Q()
        for term in district_terms:
            district_q |= (
                models.Q(district__icontains=term) |
                models.Q(city__icontains=term) |
                models.Q(address__icontains=term)
            )

        district_qs = restaurants.filter(district_q)
        if district_qs.exists():
            restaurants = district_qs
            filter_label = f"Showing nearby restaurants in {district}"
        else:
            filter_label = f"Showing all restaurants (none in {district} yet)"
            fallback_reason = f"No approved restaurants in {district} yet"
    elif state:
        state_qs = restaurants.filter(
            models.Q(state__icontains=state) | models.Q(address__icontains=state)
        )
        if state_qs.exists():
            restaurants = state_qs
            filter_label = f"Showing restaurants in {state}"
        else:
            filter_label = f"Showing all restaurants (none in {state} yet)"
            fallback_reason = f"No approved restaurants in {state} yet"
    elif city:
        city_qs = restaurants.filter(
            models.Q(city__icontains=city) | models.Q(address__icontains=city)
        )
        if city_qs.exists():
            restaurants = city_qs
            filter_label = f"Showing restaurants in {city}"
        else:
            filter_label = f"Showing all restaurants (none in {city} yet)"
            fallback_reason = f"No approved restaurants in {city} yet"
    elif area:
        area_qs = restaurants.filter(
            models.Q(area__icontains=area) | models.Q(address__icontains=area) | models.Q(city__icontains=area)
        )
        if area_qs.exists():
            restaurants = area_qs
            filter_label = f"Showing restaurants near {area}"
        else:
            filter_label = f"Showing all restaurants (none near {area} yet)"
            fallback_reason = f"No approved restaurants near {area} yet"

    if query:
        restaurants = restaurants.filter(
            models.Q(name__icontains=query) |
            models.Q(cuisine_type__icontains=query) |
            models.Q(address__icontains=query) |
            models.Q(phone__icontains=query) |
            models.Q(description__icontains=query) |
            models.Q(menu_items__name__icontains=query) |
            models.Q(menu_items__category__icontains=query) |
            models.Q(menu_items__description__icontains=query)
        ).distinct()

    # Calculate distance and sort by nearest if user coordinates are known
    if lat and lon:
        from location.services import calculate_distance, calculate_eta
        try:
            user_lat = float(lat)
            user_lon = float(lon)
            restaurants_list = list(restaurants)
            for r in restaurants_list:
                if r.latitude is not None and r.longitude is not None:
                    d = calculate_distance(user_lat, user_lon, float(r.latitude), float(r.longitude))
                    r.distance_km = d
                    if d is not None:
                        r.eta_info = calculate_eta(d)
                else:
                    r.distance_km = None
                    r.eta_info = None
            restaurants_list.sort(key=lambda x: (x.distance_km is None, x.distance_km or 999999))
            restaurants = restaurants_list
        except (ValueError, TypeError):
            pass

    return {
        "restaurants": restaurants,
        "query": query,
        "area": area,
        "city": city,
        "district": district,
        "state": state,
        "states": states,
        "user_lat": lat,
        "user_lon": lon,
        "filter_label": filter_label,
        "fallback_reason": fallback_reason,
    }


def restaurant_detail_view(request, restaurant_id):
    restaurant = get_object_or_404(
        Restaurant.objects.prefetch_related("menu_items"),
        pk=restaurant_id,
        status="approved",
        is_active=True,
    )
    return render(request, "restaurant/detail.html", {
        "restaurant": restaurant,
        "menu_items": restaurant.menu_items.filter(is_available=True),
    })


@role_required("restaurant_owner")
def restaurant_management_view(request):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    if not restaurant:
        restaurant = Restaurant.objects.create(
            owner=request.user,
            name=f"{request.user.username}'s Restaurant",
            cuisine_type="General",
            description="Fresh meals and daily specials.",
            address="Your Address",
            phone="0000000000",
        )

    profile_form = RestaurantProfileForm(instance=restaurant)
    if request.method == "POST" and request.POST.get("action") == "update_restaurant":
        profile_form = RestaurantProfileForm(
            request.POST,
            request.FILES,
            instance=restaurant,
        )
        if profile_form.is_valid():
            profile_form.save()
            return redirect("restaurant_management")

    if request.method == "POST" and request.POST.get("action") == "update_menu_item":
        item = get_object_or_404(
            MenuItem,
            pk=request.POST.get("item_id"),
            restaurant=restaurant,
        )
        item.name = request.POST.get("name", item.name).strip()
        item.description = request.POST.get("description", item.description).strip()
        item.price = request.POST.get("price", item.price)
        item.category = request.POST.get("category", item.category).strip()
        item.is_available = request.POST.get("is_available") == "on"
        image = request.FILES.get("image")
        if image:
            item.image = image
        item.save()
        return redirect("restaurant_management")

    if request.method == "POST" and request.POST.get("action") == "add_menu_item":
        MenuItem.objects.create(
            restaurant=restaurant,
            name=request.POST.get("name"),
            description=request.POST.get("description", ""),
            price=request.POST.get("price"),
            category=request.POST.get("category", "Other"),
            image=request.FILES.get("image"),
        )
        return redirect("restaurant_management")

    return render(request, "restaurant/management.html", {
        "restaurant": restaurant,
        "profile_form": profile_form,
        "menu_items": restaurant.menu_items.all().order_by("name"),
    })


@login_required
@role_required("restaurant_owner")
def restaurant_account_settings_view(request):
    """
    Dedicated account settings view for authenticated restaurant owners.
    Loads actual user profile and restaurant records from the database,
    displays owner and business details, and allows editing with validation.
    """
    user = request.user
    restaurant = Restaurant.objects.filter(owner=user).first()
    if not restaurant:
        restaurant = Restaurant.objects.create(
            owner=user,
            name=f"{user.first_name or user.username}'s Restaurant",
            cuisine_type="General",
            description="Fresh meals and daily specials.",
            address="Your Address",
            phone="0000000000",
        )

    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    mobile_number = profile.phone_number or restaurant.phone or ""

    edit_mode = request.GET.get("edit") == "1"

    if request.method == "POST":
        form = RestaurantOwnerAccountForm(
            request.POST,
            request.FILES,
            user=user,
            restaurant=restaurant,
        )
        if form.is_valid():
            data = form.cleaned_data

            # 1. Update User personal fields
            user.first_name = data.get("first_name", "").strip()
            user.last_name = data.get("last_name", "").strip()
            user.email = data.get("email", "").strip().lower()
            user.save(update_fields=["first_name", "last_name", "email"])

            # 2. Update CustomerProfile mobile number
            new_mobile = data.get("mobile_number", "").strip()
            profile.phone_number = new_mobile or None
            profile.save(update_fields=["phone_number"])

            # 3. Update Restaurant business details
            restaurant.name = data.get("restaurant_name", "").strip()
            restaurant.restaurant_type = data.get("restaurant_type")
            restaurant.cuisine_type = data.get("cuisine_type", "").strip()
            restaurant.phone = data.get("phone", "").strip() or new_mobile
            restaurant.address = data.get("address", "").strip()
            restaurant.city = data.get("city", "").strip()
            restaurant.state = data.get("state", "").strip()
            restaurant.pincode = data.get("pincode", "").strip()
            restaurant.description = data.get("description", "").strip()

            if form.cleaned_data.get("image"):
                restaurant.image = form.cleaned_data["image"]
            if form.cleaned_data.get("logo"):
                restaurant.logo = form.cleaned_data["logo"]

            restaurant.save()

            messages.success(request, "Your restaurant and account profile have been updated successfully.")
            return redirect("restaurant_account_settings")
        else:
            messages.error(request, "Please correct the errors in the form below.")
            edit_mode = True
    else:
        initial_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "mobile_number": mobile_number,
            "restaurant_name": restaurant.name,
            "restaurant_type": restaurant.restaurant_type,
            "cuisine_type": restaurant.cuisine_type,
            "phone": restaurant.phone,
            "address": restaurant.address,
            "city": restaurant.city,
            "state": restaurant.state,
            "pincode": restaurant.pincode,
            "description": restaurant.description,
        }
        form = RestaurantOwnerAccountForm(
            initial=initial_data,
            user=user,
            restaurant=restaurant,
        )

    context = {
        "user": user,
        "restaurant": restaurant,
        "profile": profile,
        "mobile_number": mobile_number,
        "form": form,
        "edit_mode": edit_mode,
    }
    return render(request, "restaurant/account_settings.html", context)
