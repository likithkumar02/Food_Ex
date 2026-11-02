from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.test import APIClient

from .models import Notification

User = get_user_model()


class NotificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notice_user",
            email="notice_user@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.other_user = User.objects.create_user(
            username="other_notice_user",
            email="other_notice_user@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.notification = Notification.objects.create(
            user=self.user,
            category="order",
            title="Order update",
            message="Your order is being prepared.",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_customer_can_list_and_mark_own_notification_read(self):
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

        response = self.client.patch(
            f"/api/notifications/{self.notification.pk}/read/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_customer_cannot_read_another_users_notification(self):
        private_notification = Notification.objects.create(
            user=self.other_user,
            category="order",
            title="Private order update",
            message="This belongs to a different account.",
        )
        response = self.client.patch(
            f"/api/notifications/{private_notification.pk}/read/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        private_notification.refresh_from_db()
        self.assertFalse(private_notification.is_read)

    def test_html_notification_center_shows_only_signed_in_user_notices(self):
        Notification.objects.create(
            user=self.other_user,
            category="order",
            title="Private notice",
            message="Hidden from this account.",
        )
        client = Client()
        client.force_login(self.user)
        response = client.get("/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Order update")
        self.assertNotContains(response, "Private notice")
