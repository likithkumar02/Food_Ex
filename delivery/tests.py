from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from delivery.models import (
    DeliveryAssignment,
    DeliveryAssignmentAttempt,
    DeliveryLocation,
    DeliveryPartnerProfile,
)
from orders.models import Order
from restaurant.models import MenuItem, Restaurant

User = get_user_model()


class DeliveryFlowTests(TestCase):
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
        self.partner = User.objects.create_user(
            username="partner",
            email="partner@example.com",
            password="StrongPass123!",
            role="delivery_partner",
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
        self.item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Paneer Bowl",
            description="Curried paneer bowl.",
            price=Decimal("180.00"),
            category="Main Course",
        )
        self.order = Order.objects.create(
            user=self.customer,
            restaurant=self.restaurant,
            total_price=Decimal("180.00"),
            delivery_address="Some Street",
        )

    def test_delivery_partner_cannot_self_assign_an_order(self):
        self.client.force_login(self.partner)
        response = self.client.get(reverse("assign_delivery", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(DeliveryAssignment.objects.filter(order=self.order).exists())

    def test_delivery_dashboard_loads(self):
        self.client.force_login(self.partner)
        response = self.client.get(reverse("delivery_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "delivery/js/dashboard.js")
        self.assertContains(response, "My shift")
        self.assertContains(response, "Account settings")

    def test_shared_settings_uses_delivery_partner_with_customer_session_active(self):
        self.client.force_login(self.partner)
        session = self.client.session
        session["_customer_user_id"] = str(self.customer.pk)
        session["_delivery_partner_user_id"] = str(self.partner.pk)
        session.save()

        dashboard = self.client.get(reverse("delivery_dashboard"))
        self.assertContains(
            dashboard,
            f'href="{reverse("settings")}"',
        )

        response = self.client.get(reverse("settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My shift")
        self.assertContains(response, "Account settings")
        self.assertContains(response, "Manage your personal details and account actions.")
        self.assertContains(response, self.partner.username)
        self.assertContains(response, self.partner.email)
        self.assertContains(response, "Vehicle type")
        self.assertNotContains(response, self.customer.email)

    def test_customer_settings_keeps_shared_design_without_delivery_details(self):
        self.client.force_login(self.customer)
        session = self.client.session
        session["_customer_user_id"] = str(self.customer.pk)
        session["_delivery_partner_user_id"] = str(self.partner.pk)
        session.save()

        response = self.client.get(reverse("settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account settings")
        self.assertContains(response, self.customer.email)
        self.assertNotContains(response, "Vehicle type")
        self.assertNotContains(response, "My shift")

    def test_delivery_partner_can_update_assignment_status(self):
        self.order.status = Order.STATUS_DELIVERY_PARTNER_ASSIGNED
        self.order.ready_at = timezone.now()
        self.order.save(update_fields=["status", "ready_at"])
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_ACCEPTED,
        )
        self.client.force_login(self.partner)

        response = self.client.post(
            reverse("update_delivery_status", args=[assignment.pk, "arrived_at_pickup"])
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            reverse("update_delivery_status", args=[assignment.pk, "picked_up"])
        )

        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "picked_up")

    def test_delivery_partner_cannot_skip_arrival_before_pickup(self):
        self.order.status = Order.STATUS_DELIVERY_PARTNER_ASSIGNED
        self.order.ready_at = timezone.now()
        self.order.save(update_fields=["status", "ready_at"])
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_ACCEPTED,
        )

        from delivery.services import advance_assignment

        self.assertIsNone(
            advance_assignment(
                self.partner,
                assignment.pk,
                DeliveryAssignment.STATUS_PICKED_UP,
            )
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.STATUS_ACCEPTED)

    def test_restaurant_manually_assigns_partner_who_accepts_and_completes_pickup(self):
        from customer.models import CustomerProfile
        from payments.models import Payment
        from delivery.services import advance_assignment

        self.order.status = Order.STATUS_FINDING_PARTNER
        self.order.ready_at = timezone.now()
        self.order.save(update_fields=["status", "ready_at"])
        DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            is_available=True,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            phone_number="9876543210",
        )
        Payment.objects.create(
            order=self.order,
            amount=self.order.total_price,
            payment_method="cod",
            status="pending",
        )
        self.client.force_login(self.owner)

        queue_response = self.client.get(reverse("restaurant_order_management"))
        self.assertContains(queue_response, "Send delivery request")
        self.assertContains(queue_response, self.partner.username)

        response = self.client.post(
            reverse("order_assign_delivery_partner", args=[self.order.pk]),
            {"partner_id": self.partner.pk},
        )

        self.assertEqual(response.status_code, 302)
        assignment = DeliveryAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.partner, self.partner)
        self.assertEqual(assignment.status, DeliveryAssignment.STATUS_ASSIGNED)
        self.assertTrue(
            self.partner.notifications.filter(title="New delivery request").exists()
        )

        client = APIClient()
        client.force_authenticate(user=self.partner)
        requests_response = client.get("/api/delivery/requests/")
        self.assertEqual(requests_response.status_code, 200)
        self.assertEqual(requests_response.data[0]["restaurant"], self.restaurant.name)
        self.assertEqual(requests_response.data[0]["pickup_address"], self.restaurant.address)
        self.assertEqual(requests_response.data[0]["customer_name"], self.customer.username)
        self.assertEqual(requests_response.data[0]["customer_phone"], "9876543210")
        self.assertEqual(requests_response.data[0]["delivery_address"], self.order.delivery_address)

        response = client.post(
            f"/api/delivery/requests/{assignment.pk}/accept/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_DELIVERY_PARTNER_ASSIGNED)

        self.client.force_login(self.partner)
        detail_response = self.client.get(
            reverse("delivery_detail", args=[assignment.pk])
        )
        self.assertContains(detail_response, self.restaurant.name)
        self.assertContains(detail_response, self.restaurant.phone)
        self.assertContains(detail_response, self.customer.username)
        self.assertContains(detail_response, self.order.delivery_address)
        self.assertContains(detail_response, "9876543210")

        self.assertIsNotNone(
            advance_assignment(
                self.partner,
                assignment.pk,
                DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP,
            )
        )
        self.assertIsNotNone(
            advance_assignment(
                self.partner,
                assignment.pk,
                DeliveryAssignment.STATUS_PICKED_UP,
            )
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PICKED_UP)

    def test_ready_order_is_assigned_to_nearest_online_partner(self):
        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order.status = "ready_for_pickup"
        self.order.save(update_fields=["status"])

        DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            latitude=Decimal("13.100000"),
            longitude=Decimal("77.700000"),
            location_updated_at=timezone.now(),
        )
        closer_partner = User.objects.create_user(
            username="closer_partner",
            email="closer@example.com",
            password="StrongPass123!",
            role="delivery_partner",
        )
        DeliveryPartnerProfile.objects.create(
            user=closer_partner,
            is_online=True,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.594800"),
            location_updated_at=timezone.now(),
        )

        from delivery.services import assign_ready_order

        assignment = assign_ready_order(self.order)
        self.assertEqual(assignment.partner, closer_partner)
        self.assertEqual(assignment.status, "assigned")
        self.assertTrue(closer_partner.notifications.filter(category="delivery").exists())

    def test_ready_order_does_not_assign_to_stale_or_unavailable_partner(self):
        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order.status = "ready_for_pickup"
        self.order.save(update_fields=["status"])
        DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            is_available=True,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.594800"),
            location_updated_at=timezone.now() - timedelta(minutes=10),
        )

        from delivery.services import assign_ready_order

        self.assertIsNone(assign_ready_order(self.order))
        self.assertFalse(DeliveryAssignment.objects.filter(order=self.order).exists())

    def test_unassigned_ready_order_notifies_restaurant_and_admin_only_once(self):
        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order.status = "ready_for_pickup"
        self.order.save(update_fields=["status"])
        admin = User.objects.create_user(
            username="operations_admin",
            email="operations@example.com",
            password="SecureTestPassword123!",
            role="admin",
            is_staff=True,
        )
        from delivery.services import assign_ready_order

        self.assertIsNone(assign_ready_order(self.order))
        self.assertIsNone(assign_ready_order(self.order))

        title = "Waiting for a delivery partner"
        self.assertEqual(self.owner.notifications.filter(title=title).count(), 1)
        self.assertEqual(admin.notifications.filter(title=title).count(), 1)

    def test_expired_offer_is_recorded_and_reassigned(self):
        from delivery.services import assign_ready_order
        from location.models import LocationSetting

        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order.status = Order.STATUS_READY
        self.order.save(update_fields=["status"])
        setting = LocationSetting.load()
        setting.delivery_assignment_accept_timeout_seconds = 1
        setting.save()

        DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.594800"),
            location_updated_at=timezone.now(),
        )
        second_partner = User.objects.create_user(
            username="second_partner",
            email="second@example.com",
            password="test-password",
            role="delivery_partner",
        )
        DeliveryPartnerProfile.objects.create(
            user=second_partner,
            is_online=True,
            latitude=Decimal("12.973000"),
            longitude=Decimal("77.595800"),
            location_updated_at=timezone.now(),
        )

        assignment = assign_ready_order(self.order)
        first_attempt = assignment.attempts.get()
        self.assertEqual(assignment.partner, self.partner)
        DeliveryAssignmentAttempt.objects.filter(pk=first_attempt.pk).update(
            offered_at=timezone.now() - timedelta(seconds=2)
        )

        reassigned = assign_ready_order(self.order)

        self.assertEqual(reassigned.pk, assignment.pk)
        self.assertEqual(reassigned.partner, second_partner)
        attempts = list(reassigned.attempts.order_by("offered_at"))
        self.assertEqual(
            [attempt.status for attempt in attempts],
            [
                DeliveryAssignmentAttempt.STATUS_TIMED_OUT,
                DeliveryAssignmentAttempt.STATUS_OFFERED,
            ],
        )

    def test_maximum_offers_fail_and_admin_retry_preserves_attempt_history(self):
        from delivery.services import assign_ready_order, reject_assignment, retry_delivery_assignment
        from location.models import LocationSetting

        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order.status = Order.STATUS_READY
        self.order.save(update_fields=["status"])
        setting = LocationSetting.load()
        setting.delivery_assignment_max_attempts = 1
        setting.save()
        profile = DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.594800"),
            location_updated_at=timezone.now(),
        )

        assignment = assign_ready_order(self.order)
        reject_assignment(self.partner, assignment.pk, "Vehicle issue")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_ASSIGNMENT_FAILED)
        self.assertTrue(profile.is_available)
        self.assertEqual(assignment.attempts.get().rejection_reason, "Vehicle issue")

        retried_assignment = retry_delivery_assignment(self.order.pk, actor=self.owner)

        self.assertIsNotNone(retried_assignment)
        self.assertEqual(retried_assignment.status, DeliveryAssignment.STATUS_ASSIGNED)
        self.assertEqual(retried_assignment.attempts.count(), 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_DELIVERY_ASSIGNED)

    def test_delivery_status_rejects_get_requests(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="assigned",
        )
        self.client.force_login(self.partner)
        response = self.client.get(
            reverse("update_delivery_status", args=[assignment.pk, "picked_up"])
        )
        self.assertEqual(response.status_code, 405)

    def test_delivery_completion_does_not_override_offline_choice(self):
        self.order.status = Order.STATUS_OUT_FOR_DELIVERY
        self.order.save(update_fields=["status"])
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="on_the_way",
        )
        profile = DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=False,
        )
        from delivery.services import advance_assignment

        advance_assignment(self.partner, assignment.pk, "delivered")
        profile.refresh_from_db()
        self.assertFalse(profile.is_online)

    def test_delivery_api_accepts_tracks_and_completes_own_assignment(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="assigned",
        )
        self.order.status = Order.STATUS_DELIVERY_ASSIGNED
        self.order.ready_at = timezone.now()
        self.order.save(update_fields=["status", "ready_at"])
        client = APIClient()
        client.force_authenticate(user=self.partner)

        response = client.post(
            f"/api/delivery/requests/{assignment.pk}/accept/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "accepted")

        response = client.post(
            f"/api/delivery/{assignment.pk}/arrived-at-pickup/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        response = client.post(
            f"/api/delivery/{assignment.pk}/pickup/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "picked_up")

        response = client.post(
            "/api/delivery/location/",
            {
                "assignment_id": assignment.pk,
                "latitude": "12.971600",
                "longitude": "77.594600",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DeliveryLocation.objects.filter(assignment=assignment).count(), 1)

        response = client.post(
            f"/api/delivery/{assignment.pk}/out-for-delivery/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        response = client.post(
            f"/api/delivery/{assignment.pk}/complete/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "delivered")

    def test_delivery_api_hides_other_partners_assignments(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="assigned",
        )
        other_partner = User.objects.create_user(
            username="other_delivery",
            email="other_delivery@example.com",
            password="StrongPass123!",
            role="delivery_partner",
        )
        client = APIClient()
        client.force_authenticate(user=other_partner)
        response = client.post(
            f"/api/delivery/requests/{assignment.pk}/accept/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "assigned")

    def test_full_10_step_order_and_delivery_lifecycle(self):
        from payments.models import Payment
        from orders.services import transition_restaurant_order
        from delivery.services import (
            assign_ready_order,
            accept_assignment,
            advance_assignment,
        )

        Payment.objects.create(
            order=self.order,
            amount=self.order.total_price,
            payment_method="upi",
            status="paid",
        )

        # 1. PLACED
        self.assertEqual(self.order.status, "placed")

        # 2. RESTAURANT_ACCEPTED
        transition_restaurant_order(self.owner, self.order.pk, "accepted", preparation_minutes=20)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "accepted")

        # 3. PREPARING
        transition_restaurant_order(self.owner, self.order.pk, "preparing")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "preparing")

        # Configure restaurant coords & partner profile for auto-dispatch
        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            is_available=True,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.594800"),
            location_updated_at=timezone.now(),
        )

        # 4. READY_FOR_PICKUP & 5. DELIVERY_ASSIGNED
        transition_restaurant_order(self.owner, self.order.pk, "ready_for_pickup")
        self.order.refresh_from_db()
        # transition_restaurant_order calls assign_ready_order automatically when ready
        self.assertEqual(self.order.status, "delivery_assigned")
        assignment = DeliveryAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.partner, self.partner)
        self.assertEqual(assignment.status, "assigned")

        # 6. DELIVERY_PARTNER_ASSIGNED (Partner accepts)
        accept_assignment(self.partner, assignment.pk)
        self.order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, "delivery_partner_assigned")
        self.assertEqual(assignment.status, "accepted")

        # 7. ARRIVED_AT_PICKUP (Partner reaches restaurant)
        advance_assignment(self.partner, assignment.pk, "arrived_at_pickup")
        self.order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, "arrived_at_pickup")
        self.assertEqual(assignment.status, "arrived_at_pickup")
        self.assertIsNotNone(assignment.arrived_at_pickup_time)
        self.assertIsNotNone(self.order.arrived_at_pickup_at)

        # 8. PICKED_UP (Partner picks up food)
        advance_assignment(self.partner, assignment.pk, "picked_up")
        self.order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, "picked_up")
        self.assertEqual(assignment.status, "picked_up")
        self.assertIsNotNone(assignment.pickup_time)

        # 9. OUT_FOR_DELIVERY (Partner starts delivery)
        advance_assignment(self.partner, assignment.pk, "on_the_way")
        self.order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, "out_for_delivery")
        self.assertEqual(assignment.status, "on_the_way")

        # 10. DELIVERED (Partner reaches customer)
        advance_assignment(self.partner, assignment.pk, "delivered")
        self.order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, "delivered")
        self.assertEqual(assignment.status, "delivered")
        self.assertIsNotNone(assignment.delivery_time)
        self.assertIsNotNone(self.order.delivered_at)

    def test_partner_rejects_assignment_reverts_order_to_ready(self):
        from delivery.services import assign_ready_order, reject_assignment

        self.restaurant.latitude = Decimal("12.971600")
        self.restaurant.longitude = Decimal("77.594600")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order.status = "ready_for_pickup"
        self.order.save(update_fields=["status"])
        profile = DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            is_available=True,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.594800"),
            location_updated_at=timezone.now(),
        )

        assignment = assign_ready_order(self.order)
        self.assertIsNotNone(assignment)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "delivery_assigned")

        reject_assignment(self.partner, assignment.pk)
        self.order.refresh_from_db()
        assignment.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(assignment.status, "rejected")
        self.assertTrue(profile.is_available)
        self.assertEqual(self.order.status, Order.STATUS_FINDING_PARTNER)
