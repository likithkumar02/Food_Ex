from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from orders.models import Order
from restaurant.models import MenuItem, Restaurant

User = get_user_model()


class PaymentFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Tandoor House",
            cuisine_type="Indian",
            description="Indian food.",
            address="City Center",
            phone="9999999999",
            status="approved",
            is_active=True,
        )
        self.order = Order.objects.create(
            user=self.customer,
            restaurant=self.restaurant,
            total_price=Decimal("180.00"),
            delivery_address="Some Street",
        )

    def test_payment_page_loads_for_customer(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("payment_page", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)

    @override_settings(PAYMENT_PROVIDER="mock")
    def test_mock_payment_generates_reference_on_the_server(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("payment_page", args=[self.order.pk]),
            {
                "payment_method": "test",
                "transaction_id": "CLIENT-SUPPLIED-REFERENCE",
            },
        )
        self.assertEqual(response.status_code, 302)
        payment = self.order.payments.get()
        self.assertEqual(payment.status, "paid")
        self.assertTrue(payment.transaction_id.startswith(f"MOCK-{self.order.pk}-"))
        self.assertNotEqual(payment.transaction_id, "CLIENT-SUPPLIED-REFERENCE")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PLACED)
        self.assertTrue(
            self.customer.notifications.filter(category="payment").exists()
        )
        self.assertTrue(
            self.owner.notifications.filter(category="order").exists()
        )

    def test_cash_on_delivery_is_not_marked_paid(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("payment_page", args=[self.order.pk]),
            {"payment_method": "cod"},
        )
        self.assertEqual(response.status_code, 302)
        payment = self.order.payments.get()
        self.assertEqual(payment.status, "pending")
        self.assertIsNone(payment.transaction_id)

    def test_repeated_cash_on_delivery_submission_is_idempotent(self):
        self.client.force_login(self.customer)
        for _ in range(2):
            response = self.client.post(
                reverse("payment_page", args=[self.order.pk]),
                {"payment_method": "cod"},
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order.payments.count(), 1)

    def test_unconfigured_card_payment_is_rejected(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("payment_page", args=[self.order.pk]),
            {
                "payment_method": "card",
                "transaction_id": "CLIENT-SUPPLIED-REFERENCE",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.order.payments.exists())
        self.assertContains(response, "not configured")

    @override_settings(PAYMENT_PROVIDER="mock")
    def test_payment_api_generates_its_own_transaction_reference(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.post(
            f"/api/payments/orders/{self.order.pk}/pay/",
            {
                "payment_method": "test",
                "transaction_id": "ATTACKER-REFERENCE",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(
            response.data["transaction_id"],
            "ATTACKER-REFERENCE",
        )
