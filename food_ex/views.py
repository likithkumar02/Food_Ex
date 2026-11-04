from django.db import models
from django.shortcuts import render

from restaurant.models import MenuItem, Restaurant


def home(request):
    state = request.GET.get("state", "").strip()
    district = request.GET.get("district", "").strip()
    restaurants_for_location = Restaurant.objects.filter(
        status="approved",
        is_active=True,
    )
    dishes = MenuItem.objects.filter(
        is_available=True,
        restaurant__status="approved",
        restaurant__is_active=True,
    ).select_related("restaurant")

    if district and state:
        loc_filter = models.Q(state__icontains=state) & (
            models.Q(district__icontains=district)
            | models.Q(city__icontains=district)
            | models.Q(address__icontains=district)
        )
        restaurants_for_location = restaurants_for_location.filter(loc_filter)
        dishes = dishes.filter(
            models.Q(restaurant__state__icontains=state)
            & (
                models.Q(restaurant__district__icontains=district)
                | models.Q(restaurant__city__icontains=district)
                | models.Q(restaurant__address__icontains=district)
            )
        )
    elif district:
        loc_filter = (
            models.Q(district__icontains=district)
            | models.Q(city__icontains=district)
            | models.Q(address__icontains=district)
        )
        restaurants_for_location = restaurants_for_location.filter(loc_filter)
        dishes = dishes.filter(
            models.Q(restaurant__district__icontains=district)
            | models.Q(restaurant__city__icontains=district)
            | models.Q(restaurant__address__icontains=district)
        )
    elif state:
        restaurants_for_location = restaurants_for_location.filter(
            models.Q(state__icontains=state) | models.Q(address__icontains=state)
        )
        dishes = dishes.filter(
            models.Q(restaurant__state__icontains=state)
            | models.Q(restaurant__address__icontains=state)
        )
    restaurants = restaurants_for_location.order_by("name")[:6]
    dishes = dishes[:4]
    food_images = [
        "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=900&q=85",
        "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=900&q=85",
        "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=85",
        "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85",
    ]
    restaurant_cards = [
        {
            "restaurant": restaurant,
            "image": restaurant.image.url if restaurant.image else food_images[index % len(food_images)],
        }
        for index, restaurant in enumerate(restaurants)
    ]
    dish_cards = [
        {
            "dish": dish,
            "image": dish.image.url if dish.image else food_images[(index + 1) % len(food_images)],
        }
        for index, dish in enumerate(dishes)
    ]
    return render(
        request,
        "home.html",
        {
            "restaurant_cards": restaurant_cards,
            "dish_cards": dish_cards,
            "restaurant_count": restaurants_for_location.count(),
            "state": state,
            "district": district,
        },
    )
