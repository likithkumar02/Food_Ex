from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from customer.models import CustomerProfile
from orders.models import Order
from restaurant.models import Restaurant

User = get_user_model()


class CustomerProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customerprofile",
            email="profile@example.com",
            password="StrongPass123!",
            role="customer",
        )

    def test_customer_profile_page_loads(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("customer_profile"))
        self.assertEqual(response.status_code, 200)

    def test_customer_profile_can_be_updated(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("customer_profile"),
            {
                "first_name": "Asha",
                "last_name": "Patel",
                "phone_number": "9876543210",
            },
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.first_name, "Asha")
        self.assertEqual(self.user.last_name, "Patel")

    def test_customer_profile_updates_are_private_to_each_account(self):
        other_user = User.objects.create_user(
            username="other_profile",
            email="other_profile@example.com",
            password="StrongPass123!",
            role="customer",
        )
        CustomerProfile.objects.create(
            user=self.user,
            phone_number="9876543210",
            address="Asha's address",
        )
        other_profile = CustomerProfile.objects.create(
            user=other_user,
            phone_number="9876543211",
            address="Ravi's address",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("customer_profile"),
            {
                "first_name": "Asha",
                "email": self.user.email,
                "phone_number": "9876543212",
                "address": "Updated private address",
            },
        )

        self.assertEqual(response.status_code, 302)
        other_profile.refresh_from_db()
        self.assertEqual(other_profile.phone_number, "9876543211")
        self.assertEqual(other_profile.address, "Ravi's address")

    def test_customer_can_review_only_a_delivered_order(self):
        owner = User.objects.create_user(
            username="review_owner",
            email="review_owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="Review Kitchen",
            cuisine_type="Indian",
            description="Fresh food.",
            address="Main Street",
            phone="9876543210",
            status="approved",
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            restaurant=restaurant,
            total_price="100.00",
            delivery_address="Customer Street",
            status="delivered",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("order_review", args=[order.pk]),
            {"rating": "5", "comment": "Great meal."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.review.rating, 5)

    def test_undelivered_order_cannot_be_reviewed(self):
        owner = User.objects.create_user(
            username="review_owner_pending",
            email="review_owner_pending@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="Pending Kitchen",
            cuisine_type="Indian",
            description="Fresh food.",
            address="Main Street",
            phone="9876543211",
            status="approved",
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            restaurant=restaurant,
            total_price="100.00",
            delivery_address="Customer Street",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("order_review", args=[order.pk]),
            {"rating": "5"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(hasattr(order, "review"))

    def test_review_api_accepts_only_customers_with_delivered_orders(self):
        owner = User.objects.create_user(
            username="review_api_owner",
            email="review_api_owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="API Review Kitchen",
            cuisine_type="Indian",
            description="Fresh food.",
            address="Main Street",
            phone="9876543212",
            status="approved",
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            restaurant=restaurant,
            total_price="100.00",
            delivery_address="Customer Street",
            status="delivered",
        )
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            f"/api/customer/restaurants/{restaurant.pk}/reviews/create/",
            {"order_id": order.pk, "rating": 4, "comment": "Tasty."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        response = client.get(f"/api/customer/restaurants/{restaurant.pk}/reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["rating"], 4)
