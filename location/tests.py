from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from customer.models import CustomerAddress, CustomerProfile
from delivery.models import DeliveryAssignment, DeliveryLocation, DeliveryPartnerProfile
from orders.models import Order
from restaurant.models import Restaurant

from .models import LocationSetting
from .services import calculate_distance, calculate_eta, validate_coordinates


class LocationServicesTests(TestCase):
    def test_haversine_distance_calculation(self):
        # Visakhapatnam coordinates
        # Point 1: 17.6868, 83.2185
        # Point 2: 17.7000, 83.2200
        dist = calculate_distance(17.6868, 83.2185, 17.7000, 83.2200)
        self.assertIsNotNone(dist)
        self.assertGreater(dist, 1.0)
        self.assertLess(dist, 2.0)

    def test_distance_with_none_returns_none(self):
        self.assertIsNone(calculate_distance(None, 83.2, 17.7, 83.2))
        self.assertIsNone(calculate_distance(17.6, None, 17.7, 83.2))

    def test_coordinate_validation(self):
        valid, lat, lon = validate_coordinates(17.6868, 83.2185)
        self.assertTrue(valid)
        self.assertEqual(lat, Decimal("17.6868"))

        invalid_lat, _, _ = validate_coordinates(95.0, 80.0)
        self.assertFalse(invalid_lat)

        invalid_lon, _, _ = validate_coordinates(15.0, 190.0)
        self.assertFalse(invalid_lon)

    def test_eta_calculation(self):
        eta = calculate_eta(5.0, prep_minutes=15)
        self.assertIn("min", eta["range"])
        self.assertGreaterEqual(eta["minutes"], 20)


class LocationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Customer A
        self.customer_a = User.objects.create_user(
            username="customera",
            email="cust_a@example.com",
            password="Password123!",
            role="customer",
        )
        self.profile_a = CustomerProfile.objects.create(
            user=self.customer_a,
            address="123 Beach Road",
            city="Vizag",
        )

        # Customer B
        self.customer_b = User.objects.create_user(
            username="customerb",
            email="cust_b@example.com",
            password="Password123!",
            role="customer",
        )

        # Restaurant Owner
        self.owner = User.objects.create_user(
            username="restowner",
            email="owner@example.com",
            password="Password123!",
            role="restaurant_owner",
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Sea Pearl Restaurant",
            cuisine_type="Indian",
            address="Beach Rd, Vizag",
            city="Vizag",
            latitude=Decimal("17.7000"),
            longitude=Decimal("83.2200"),
            status="approved",
            is_active=True,
            is_open=True,
        )

        # Delivery Partner A
        self.partner_a = User.objects.create_user(
            username="rider1",
            email="rider1@example.com",
            password="Password123!",
            role="delivery_partner",
        )
        self.rider_prof_a = DeliveryPartnerProfile.objects.create(
            user=self.partner_a,
            is_online=True,
            is_available=True,
            latitude=Decimal("17.6950"),
            longitude=Decimal("83.2190"),
        )

        # Delivery Partner B
        self.partner_b = User.objects.create_user(
            username="rider2",
            email="rider2@example.com",
            password="Password123!",
            role="delivery_partner",
        )
        self.rider_prof_b = DeliveryPartnerProfile.objects.create(
            user=self.partner_b,
            is_online=True,
            is_available=True,
            latitude=Decimal("17.7500"),
            longitude=Decimal("83.3000"),
        )

        # Order for Customer A
        self.order_a = Order.objects.create(
            user=self.customer_a,
            restaurant=self.restaurant,
            subtotal=Decimal("300.00"),
            total_price=Decimal("350.00"),
            status="placed",
            delivery_address="123 Beach Road",
            customer_latitude=Decimal("17.6868"),
            customer_longitude=Decimal("83.2185"),
            restaurant_latitude=Decimal("17.7000"),
            restaurant_longitude=Decimal("83.2200"),
        )

    def test_customer_location_page_shows_only_the_signed_in_customers_latest_order(self):
        other_order = Order.objects.create(
            user=self.customer_b,
            restaurant=self.restaurant,
            total_price=Decimal("125.00"),
            delivery_address="Private address for customer B",
        )
        self.client.force_login(self.customer_a)

        response = self.client.get(reverse("location_customer"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Order status")
        self.assertContains(response, self.order_a.code)
        self.assertContains(response, "customerOrderTrackingMap")
        self.assertContains(response, "Order progress")
        self.assertNotContains(response, other_order.code)
        self.assertNotContains(response, other_order.delivery_address)

    def test_customer_location_page_shows_empty_tracking_state_without_orders(self):
        self.client.force_login(self.customer_b)

        response = self.client.get(reverse("location_customer"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders to track yet")
        self.assertNotContains(response, "customerOrderTrackingMap")

    def test_customer_location_update(self):
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.post(
            reverse("api_location_customer_update"),
            {"latitude": 17.6868, "longitude": 83.2185},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.latitude, Decimal("17.6868"))
        self.assertEqual(self.profile_a.longitude, Decimal("83.2185"))
        self.assertIsNone(self.profile_a.accuracy)
        self.assertIsNotNone(self.profile_a.location_updated_at)

    def test_customer_gps_saves_accuracy_and_rejects_invalid_accuracy(self):
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.post(
            reverse("api_location_customer_update"),
            {"latitude": 17.6868, "longitude": 83.2185, "accuracy": 7.5},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.accuracy, 7.5)

        response = self.client.post(
            reverse("api_location_customer_update"),
            {"latitude": 17.6868, "longitude": 83.2185, "accuracy": -1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("location.api_views.reverse_geocode")
    def test_customer_gps_response_includes_reverse_geocoded_state(self, reverse_geocode):
        reverse_geocode.return_value = {
            "address": "Beach Road, Visakhapatnam",
            "address_line": "Beach Road",
            "area": "Beach Road",
            "city": "Visakhapatnam",
            "district": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "pincode": "530001",
        }
        self.client.force_authenticate(user=self.customer_a)

        response = self.client.post(
            reverse("api_location_customer_update"),
            {
                "latitude": 17.6868,
                "longitude": 83.2185,
                "reverse_geocode": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["state"], "Andhra Pradesh")
        self.assertEqual(response.data["city"], "Visakhapatnam")

    def test_order_checkout_stores_customer_and_restaurant_location_snapshots(self):
        from orders.models import Cart, CartItem
        from restaurant.models import MenuItem

        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Test meal",
            price=Decimal("100.00"),
            category="Meals",
        )
        cart, _ = Cart.objects.get_or_create(user=self.customer_a)
        CartItem.objects.create(cart=cart, menu_item=item, quantity=1)
        address = CustomerAddress.objects.create(
            user=self.customer_a,
            name="Home",
            address="123 Beach Road",
            area="Beach Road",
            city="Vizag",
            district="Visakhapatnam",
            state="Andhra Pradesh",
            latitude=Decimal("17.6868"),
            longitude=Decimal("83.2185"),
        )
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.post(
            "/api/orders/",
            {"address_id": address.pk, "delivery_address": address.address},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.customer_latitude, address.latitude)
        self.assertEqual(order.customer_longitude, address.longitude)
        self.assertEqual(order.restaurant_latitude, self.restaurant.latitude)
        self.assertEqual(order.restaurant_longitude, self.restaurant.longitude)
        self.assertEqual(order.delivery_area, address.area)

        self.restaurant.latitude = Decimal("17.8000")
        self.restaurant.save(update_fields=["latitude"])
        order.refresh_from_db()
        self.assertEqual(order.restaurant_latitude, Decimal("17.7000"))

    def test_nearby_restaurants_honors_delivery_radius_and_location_filters(self):
        self.restaurant.delivery_radius_km = Decimal("0.50")
        self.restaurant.state = "Andhra Pradesh"
        self.restaurant.district = "Visakhapatnam"
        self.restaurant.city = "Vizag"
        self.restaurant.area = "Beach Road"
        self.restaurant.save()
        response = self.client.get(
            reverse("api_location_nearby_restaurants"),
            {
                "latitude": 17.6868,
                "longitude": 83.2185,
                "radius": 10,
                "district": "Visakhapatnam",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        self.restaurant.delivery_radius_km = Decimal("8.00")
        self.restaurant.save(update_fields=["delivery_radius_km"])
        response = self.client.get(
            reverse("api_location_nearby_restaurants"),
            {
                "latitude": 17.6868,
                "longitude": 83.2185,
                "radius": 10,
                "district": "Other District",
            },
        )
        self.assertEqual(response.data["count"], 0)

    def test_checkout_rejects_delivery_address_outside_restaurant_radius(self):
        from orders.models import Cart, CartItem
        from restaurant.models import MenuItem

        self.restaurant.delivery_radius_km = Decimal("0.50")
        self.restaurant.save(update_fields=["delivery_radius_km"])
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Test meal",
            price=Decimal("100.00"),
            category="Meals",
        )
        cart, _ = Cart.objects.get_or_create(user=self.customer_a)
        CartItem.objects.create(cart=cart, menu_item=item)
        address = CustomerAddress.objects.create(
            user=self.customer_a,
            name="Home",
            address="123 Beach Road",
            latitude=Decimal("17.6868"),
            longitude=Decimal("83.2185"),
        )
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.post(
            "/api/orders/",
            {"address_id": address.pk, "delivery_address": address.address},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("outside the restaurant's delivery area", response.data["detail"])
        self.assertEqual(Order.objects.filter(user=self.customer_a).count(), 1)

    def test_invalid_coordinates_rejected(self):
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.post(
            reverse("api_location_customer_update"),
            {"latitude": 95.0, "longitude": 83.2185},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])

    def test_unauthenticated_user_cannot_update_customer_location(self):
        response = self.client.post(
            reverse("api_location_customer_update"),
            {"latitude": 17.6868, "longitude": 83.2185},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_customer_saved_addresses_isolation(self):
        # Customer A adds an address
        self.client.force_authenticate(user=self.customer_a)
        res = self.client.post(
            reverse("api_location_customer_addresses"),
            {
                "name": "Home",
                "address": "Flat 101, Sea View, Beach Road",
                "latitude": 17.6868,
                "longitude": 83.2185,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        addr_id = res.data["address"]["id"]

        # Customer B should NOT see Customer A's address
        self.client.force_authenticate(user=self.customer_b)
        list_res = self.client.get(reverse("api_location_customer_addresses"))
        self.assertEqual(len(list_res.data["addresses"]), 0)

        # Customer B cannot delete Customer A's address (404)
        del_res = self.client.delete(reverse("api_location_customer_address_detail", args=[addr_id]))
        self.assertEqual(del_res.status_code, 404)

    def test_customer_can_update_only_their_saved_address(self):
        address = CustomerAddress.objects.create(
            user=self.customer_a,
            name="Home",
            address="Old address",
        )
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.patch(
            reverse("api_location_customer_address_detail", args=[address.pk]),
            {
                "area": "Beach Road",
                "district": "Visakhapatnam",
                "latitude": "17.686800",
                "longitude": "83.218500",
                "is_default": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        address.refresh_from_db()
        self.assertEqual(address.area, "Beach Road")
        self.assertEqual(address.district, "Visakhapatnam")
        self.assertTrue(address.is_default)

        self.client.force_authenticate(user=self.customer_b)
        response = self.client.patch(
            reverse("api_location_customer_address_detail", args=[address.pk]),
            {"address": "Unauthorized change"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_restaurant_owner_can_update_restaurant_location(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            reverse("api_location_restaurant_update"),
            {
                "latitude": 17.7123,
                "longitude": 83.2345,
                "address": "New Kitchen Location, Main Road",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.latitude, Decimal("17.7123"))
        self.assertEqual(self.restaurant.address, "New Kitchen Location, Main Road")

    def test_customer_cannot_update_restaurant_location(self):
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.post(
            reverse("api_location_restaurant_update"),
            {"latitude": 17.7123, "longitude": 83.2345},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_delivery_partner_location_update(self):
        self.client.force_authenticate(user=self.partner_a)
        response = self.client.post(
            reverse("api_location_delivery_update"),
            {
                "latitude": 17.6900,
                "longitude": 83.2100,
                "accuracy": 8.5,
                "speed": 15.0,
                "heading": 45.0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.rider_prof_a.refresh_from_db()
        self.assertEqual(self.rider_prof_a.latitude, Decimal("17.6900"))
        self.assertEqual(self.rider_prof_a.longitude, Decimal("83.2100"))
        self.rider_prof_a.refresh_from_db()
        self.assertEqual(self.rider_prof_a.accuracy, 8.5)
        self.assertEqual(self.rider_prof_a.speed, 15.0)
        self.assertEqual(self.rider_prof_a.heading, 45.0)
        self.assertFalse(DeliveryLocation.objects.filter(delivery_partner=self.partner_a).exists())

    def test_nearby_restaurants_api(self):
        response = self.client.get(
            reverse("api_location_nearby_restaurants"),
            {"latitude": 17.6868, "longitude": 83.2185, "radius": 10},
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 1)
        first = response.data["restaurants"][0]
        self.assertEqual(first["id"], self.restaurant.id)
        self.assertIsNotNone(first["distance"])
        alias_response = self.client.get(
            reverse("api_location_nearby_restaurants_short"),
            {"latitude": 17.6868, "longitude": 83.2185, "radius": 10},
        )
        self.assertEqual(alias_response.status_code, 200)

    def test_order_tracking_privacy_security(self):
        # Customer A can track their own order
        self.client.force_authenticate(user=self.customer_a)
        res_a = self.client.get(reverse("api_order_delivery_location", args=[self.order_a.id]))
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.data["order_id"], self.order_a.id)

        # Customer B CANNOT track Customer A's order (must return 403 Forbidden)
        self.client.force_authenticate(user=self.customer_b)
        res_b = self.client.get(reverse("api_order_delivery_location", args=[self.order_a.id]))
        self.assertEqual(res_b.status_code, 403)
        self.assertFalse(res_b.data.get("success", True))

    def test_nearby_restaurants_rejects_radius_over_twenty_km(self):
        response = self.client.get(
            reverse("api_location_nearby_restaurants"),
            {"latitude": 17.6868, "longitude": 83.2185, "radius": 20.1},
        )
        self.assertEqual(response.status_code, 400)

    def test_nearby_delivery_partners_returns_only_fresh_available_partners(self):
        from django.utils import timezone

        self.rider_prof_a.location_updated_at = timezone.now()
        self.rider_prof_a.save(update_fields=["location_updated_at"])
        self.rider_prof_b.is_online = False
        self.rider_prof_b.location_updated_at = timezone.now()
        self.rider_prof_b.save(update_fields=["is_online", "location_updated_at"])
        self.client.force_authenticate(user=self.customer_a)

        response = self.client.get(
            reverse("api_location_nearby_delivery_partners"),
            {"latitude": 17.6950, "longitude": 83.2190, "radius": 3},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        partner = response.data["delivery_partners"][0]
        self.assertEqual(partner["id"], self.rider_prof_a.pk)
        self.assertNotIn("email", partner)
        self.assertNotIn("phone", partner)

    def test_nearby_delivery_partners_requires_authentication(self):
        response = self.client.get(
            reverse("api_location_nearby_delivery_partners"),
            {"latitude": 17.6950, "longitude": 83.2190},
        )
        self.assertEqual(response.status_code, 401)

    def test_delivery_location_cannot_update_an_unassigned_order(self):
        self.client.force_authenticate(user=self.partner_a)

        response = self.client.post(
            reverse("api_location_delivery_update"),
            {
                "order_id": self.order_a.pk,
                "latitude": 17.6900,
                "longitude": 83.2100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.order_a.refresh_from_db()
        self.assertIsNone(self.order_a.delivery_latitude)
        self.assertIsNone(self.order_a.delivery_longitude)

    def test_tracking_api_alias_and_customer_tracking_page(self):
        self.client.force_authenticate(user=self.customer_a)

        response = self.client.get(reverse("api_order_tracking", args=[self.order_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order_id"], self.order_a.pk)
        self.assertIn("restaurant", response.data)
        self.assertIn("customer", response.data)

        self.client.force_login(self.customer_a)
        page = self.client.get(reverse("customer_order_track", args=[self.order_a.pk]))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "customerOrderTrackingMap")

    def test_online_partner_gps_update_retries_ready_order_dispatch(self):
        from django.utils import timezone
        from delivery.models import DeliveryAssignment

        self.restaurant.latitude = Decimal("17.7000")
        self.restaurant.longitude = Decimal("83.2200")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order_a.status = Order.STATUS_READY
        self.order_a.save(update_fields=["status"])
        self.rider_prof_a.is_online = True
        self.rider_prof_a.is_available = True
        self.rider_prof_a.location_updated_at = timezone.now()
        self.rider_prof_a.save(
            update_fields=["is_online", "is_available", "location_updated_at"]
        )
        self.client.force_authenticate(user=self.partner_a)

        response = self.client.post(
            reverse("api_location_delivery_update"),
            {"latitude": 17.6950, "longitude": 83.2190},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        assignment = DeliveryAssignment.objects.get(order=self.order_a)
        self.assertEqual(assignment.partner, self.partner_a)
        self.assertEqual(assignment.status, "assigned")

    def test_ready_order_waits_when_online_partner_is_outside_dispatch_radius(self):
        from django.utils import timezone
        from delivery.services import assign_ready_order

        self.restaurant.latitude = Decimal("17.7000")
        self.restaurant.longitude = Decimal("83.2200")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        self.order_a.status = Order.STATUS_READY
        self.order_a.save(update_fields=["status"])
        self.rider_prof_a.is_online = True
        self.rider_prof_a.is_available = True
        self.rider_prof_a.latitude = Decimal("17.8000")
        self.rider_prof_a.longitude = Decimal("83.2200")
        self.rider_prof_a.location_updated_at = timezone.now()
        self.rider_prof_a.save()

        self.assertIsNone(assign_ready_order(self.order_a))
        self.assertFalse(
            DeliveryAssignment.objects.filter(order=self.order_a).exists()
        )

    def test_admin_live_feed_includes_private_operational_states_only_for_admin(self):
        admin = User.objects.create_user(
            username="locationadmin",
            email="locationadmin@example.com",
            password="SecureTestPassword123!",
            role="admin",
            is_staff=True,
        )
        self.rider_prof_b.is_online = False
        self.rider_prof_b.save(update_fields=["is_online"])
        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("api_location_admin_live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"]["total_customers"], 2)
        partner = next(
            item for item in response.data["delivery_partners"]
            if item["user_id"] == self.partner_b.pk
        )
        self.assertEqual(partner["status"], "offline")
        self.assertNotIn("email", partner)

        self.client.force_login(admin)
        dashboard = self.client.get(reverse("location_admin"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "mapContentFilter")
        self.assertContains(dashboard, "partnerStatusFilter")

    def test_partner_gps_update_with_assigned_status(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order_a,
            partner=self.partner_a,
            status="assigned",
        )
        self.client.force_authenticate(user=self.partner_a)
        response = self.client.post(
            reverse("api_delivery_location_update"),
            {
                "assignment_id": assignment.id,
                "order_id": self.order_a.id,
                "latitude": 17.6912,
                "longitude": 83.2145,
                "accuracy": 15.0,
                "speed": 4.5,
                "heading": 90.0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.rider_prof_a.refresh_from_db()
        self.assertEqual(self.rider_prof_a.latitude, Decimal("17.6912"))
        self.assertEqual(self.rider_prof_a.longitude, Decimal("83.2145"))
        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.delivery_latitude, Decimal("17.6912"))

    def test_partner_gps_update_forbidden_for_other_partner(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order_a,
            partner=self.partner_a,
            status="accepted",
        )
        self.client.force_authenticate(user=self.partner_b)
        response = self.client.post(
            reverse("api_delivery_location_update"),
            {
                "assignment_id": assignment.id,
                "latitude": 17.6912,
                "longitude": 83.2145,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_partner_gps_update_returns_410_on_completed_delivery(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order_a,
            partner=self.partner_a,
            status="delivered",
        )
        self.client.force_authenticate(user=self.partner_a)
        response = self.client.post(
            reverse("api_delivery_location_update"),
            {
                "assignment_id": assignment.id,
                "latitude": 17.6912,
                "longitude": 83.2145,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.data["code"], "DELIVERY_COMPLETED")

    def test_partner_gps_update_rejects_invalid_coordinates(self):
        self.client.force_authenticate(user=self.partner_a)
        response = self.client.post(
            reverse("api_delivery_location_update"),
            {
                "latitude": 95.0,
                "longitude": 83.2145,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_customer_order_tracking_returns_live_location(self):
        from django.utils import timezone
        assignment = DeliveryAssignment.objects.create(
            order=self.order_a,
            partner=self.partner_a,
            status="on_the_way",
        )
        self.order_a.status = Order.STATUS_OUT_FOR_DELIVERY
        self.order_a.save(update_fields=["status"])
        self.rider_prof_a.latitude = Decimal("17.6920")
        self.rider_prof_a.longitude = Decimal("83.2150")
        self.rider_prof_a.location_updated_at = timezone.now()
        self.rider_prof_a.save()

        self.client.force_authenticate(user=self.customer_a)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order_a.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["location"])
        self.assertEqual(response.data["location"]["latitude"], 17.6920)
        self.assertEqual(response.data["location"]["longitude"], 83.2150)
        self.assertTrue(response.data["location"]["is_fresh"])

    def test_customer_order_tracking_forbidden_for_other_customer(self):
        self.client.force_authenticate(user=self.customer_b)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order_a.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_order_tracking_stale_location_returns_gracefully(self):
        from datetime import timedelta
        from django.utils import timezone
        assignment = DeliveryAssignment.objects.create(
            order=self.order_a,
            partner=self.partner_a,
            status="on_the_way",
        )
        self.order_a.status = Order.STATUS_OUT_FOR_DELIVERY
        self.order_a.save(update_fields=["status"])
        self.rider_prof_a.latitude = Decimal("17.6920")
        self.rider_prof_a.longitude = Decimal("83.2150")
        self.rider_prof_a.location_updated_at = timezone.now() - timedelta(minutes=10)
        self.rider_prof_a.save()

        self.client.force_authenticate(user=self.customer_a)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order_a.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["location"])
        self.assertEqual(response.data["location"]["latitude"], 17.6920)
        self.assertFalse(response.data["location"]["is_fresh"])

    def test_location_setting_carto_tile_url_default(self):
        setting = LocationSetting.load()
        self.assertIn("cartocdn.com", setting.tile_layer_url)
        self.assertNotIn("tile.openstreetmap.org", setting.tile_layer_url)


class RealTimeGPSAndRestaurantFirstRouteTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Customer A
        self.customer = User.objects.create_user(
            username="customer_test",
            email="cust@example.com",
            password="Password123!",
            role="customer",
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer,
            address="45-1 Beach Road",
            city="Visakhapatnam",
            latitude=Decimal("17.720000"),
            longitude=Decimal("83.310000"),
        )

        # Customer B (unauthorized)
        self.other_customer = User.objects.create_user(
            username="other_customer",
            email="other@example.com",
            password="Password123!",
            role="customer",
        )

        # Restaurant Owner & Restaurant
        self.owner = User.objects.create_user(
            username="owner_test",
            email="owner_test@example.com",
            password="Password123!",
            role="restaurant_owner",
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Coastal Spice Kitchen",
            cuisine_type="South Indian",
            address="12 Main Junction, Vizag",
            city="Visakhapatnam",
            latitude=Decimal("17.700000"),
            longitude=Decimal("83.300000"),
            status="approved",
            is_active=True,
            is_open=True,
        )

        # Delivery Partner A (assigned)
        self.partner = User.objects.create_user(
            username="delivery_rider",
            email="rider@example.com",
            password="Password123!",
            role="delivery_partner",
        )
        self.partner_profile = DeliveryPartnerProfile.objects.create(
            user=self.partner,
            is_online=True,
            is_available=False,
            vehicle_type="Motorbike",
            vehicle_number="AP39AB1234",
            latitude=Decimal("17.695000"),
            longitude=Decimal("83.295000"),
            location_updated_at=timezone.now(),
        )

        # Delivery Partner B (unauthorized)
        self.other_partner = User.objects.create_user(
            username="other_rider",
            email="other_rider@example.com",
            password="Password123!",
            role="delivery_partner",
        )
        self.other_partner_profile = DeliveryPartnerProfile.objects.create(
            user=self.other_partner,
            is_online=True,
            is_available=True,
        )

        # Order
        self.order = Order.objects.create(
            user=self.customer,
            restaurant=self.restaurant,
            subtotal=Decimal("350.00"),
            total_price=Decimal("380.00"),
            status=Order.STATUS_ACCEPTED,
            delivery_address="45-1 Beach Road, Visakhapatnam",
            customer_latitude=Decimal("17.720000"),
            customer_longitude=Decimal("83.310000"),
            restaurant_latitude=Decimal("17.700000"),
            restaurant_longitude=Decimal("83.300000"),
        )

    def test_geofence_arrival_detection_helper(self):
        from .services import check_restaurant_geofence
        # Coordinate ~30 meters away
        near_lat, near_lon = 17.7002, 83.3001
        self.assertTrue(check_restaurant_geofence(near_lat, near_lon, 17.7000, 83.3000, radius_meters=100))

        # Coordinate ~500 meters away
        far_lat, far_lon = 17.7050, 83.3050
        self.assertFalse(check_restaurant_geofence(far_lat, far_lon, 17.7000, 83.3000, radius_meters=100))

    def test_road_route_service_returns_valid_data(self):
        from .services import get_road_route
        route = get_road_route(17.6950, 83.2950, 17.7000, 83.3000)
        self.assertIsNotNone(route)
        self.assertIn("coordinates", route)
        self.assertGreaterEqual(len(route["coordinates"]), 2)
        self.assertGreater(route["distance_km"], 0)

    def test_phase_a_partner_to_restaurant_route(self):
        # Assign delivery partner
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_ACCEPTED,
        )
        self.order.status = Order.STATUS_DELIVERY_PARTNER_ASSIGNED
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.customer)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(response.status_code, 200)
        data = response.data

        # Phase A checks
        self.assertEqual(data["delivery_phase"], "to_restaurant")
        self.assertEqual(data["phase_message"], "Your delivery partner is on the way to the restaurant.")
        self.assertEqual(data["target_destination"]["type"], "restaurant")
        self.assertEqual(data["target_destination"]["latitude"], 17.7000)
        self.assertEqual(data["target_destination"]["longitude"], 83.3000)
        self.assertIsNotNone(data["route"])
        self.assertGreaterEqual(len(data["route"]["coordinates"]), 2)

    def test_phase_b_geofence_arrival_triggers_status_update(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_ACCEPTED,
        )
        self.order.status = Order.STATUS_DELIVERY_PARTNER_ASSIGNED
        self.order.save(update_fields=["status"])

        # Partner moves within 30m of the restaurant
        self.client.force_authenticate(user=self.partner)
        response = self.client.post(
            reverse("api_location_delivery_update"),
            {
                "assignment_id": assignment.id,
                "order_id": self.order.id,
                "latitude": "17.7001",
                "longitude": "83.3001",
                "accuracy": 10.0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("arrived_at_pickup"))

        # Verify database updated to arrived_at_pickup
        assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP)
        self.assertEqual(self.order.status, Order.STATUS_ARRIVED_AT_PICKUP)

        # Verify customer tracking response reflects arrived at restaurant
        self.client.force_authenticate(user=self.customer)
        track_resp = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(track_resp.status_code, 200)
        self.assertEqual(track_resp.data["delivery_phase"], "at_restaurant")
        self.assertEqual(track_resp.data["phase_message"], "Your delivery partner has arrived at the restaurant.")
        self.assertEqual(track_resp.data["target_destination"]["type"], "restaurant")

    def test_phase_c_and_d_pickup_switches_destination_to_customer(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_ON_THE_WAY,
        )
        self.order.status = Order.STATUS_OUT_FOR_DELIVERY
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.customer)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(response.status_code, 200)
        data = response.data

        # Destination must now be Customer!
        self.assertEqual(data["delivery_phase"], "to_customer")
        self.assertEqual(data["phase_message"], "Your order is on the way to you.")
        self.assertEqual(data["target_destination"]["type"], "customer")
        self.assertEqual(data["target_destination"]["latitude"], 17.7200)
        self.assertEqual(data["target_destination"]["longitude"], 83.3100)

    def test_phase_e_delivered_status(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_DELIVERED,
        )
        self.order.status = Order.STATUS_DELIVERED
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.customer)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_phase"], "delivered")
        self.assertEqual(response.data["phase_message"], "Your order has been delivered.")

    def test_unauthorized_partner_gps_update_rejected(self):
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status=DeliveryAssignment.STATUS_ACCEPTED,
        )

        # Other partner tries to post location for this assignment
        self.client.force_authenticate(user=self.other_partner)
        response = self.client.post(
            reverse("api_location_delivery_update"),
            {
                "assignment_id": assignment.id,
                "order_id": self.order.id,
                "latitude": "17.7000",
                "longitude": "83.3000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_unauthorized_customer_cannot_track_order(self):
        self.client.force_authenticate(user=self.other_customer)
        response = self.client.get(
            reverse("api_order_delivery_location", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(response.status_code, 403)

