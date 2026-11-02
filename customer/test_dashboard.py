from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from restaurant.models import Restaurant


class CustomerDashboardTests(TestCase):
    def test_restaurants_use_full_width_listing_cards(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username="dashboard_customer",
            email="dashboard_customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        owner = user_model.objects.create_user(
            username="dashboard_restaurant_owner",
            email="dashboard_owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="Dashboard Kitchen",
            cuisine_type="Indian",
            description="Fresh local food.",
            address="Main Street",
            phone="9876543210",
            status="approved",
            is_active=True,
        )
        self.client.force_login(customer)

        response = self.client.get(reverse("customer_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, restaurant.name)
        self.assertContains(response, "restaurant-card")
        self.assertContains(response, "restaurant-list-image")
        self.assertContains(response, "Fresh local food.")
        self.assertContains(response, "View menu")
