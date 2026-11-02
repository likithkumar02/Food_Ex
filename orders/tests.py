from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from customer.models import CustomerProfile
from payments.models import Payment
from delivery.models import (
    DeliveryAssignment,
    DeliveryAssignmentAttempt,
    DeliveryLocation,
    DeliveryPartnerProfile,
)
from restaurant.models import MenuItem, Restaurant

from .models import Cart, CartItem, Order, OrderItem

User = get_user_model()


class OrderFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customeruser",
            email="customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.owner = User.objects.create_user(
            username="owneruser",
            email="owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Tandoor House",
            cuisine_type="Indian",
            description="Indian food.",
            address="Main Road",
            phone="9999999999",
            status="approved",
            is_active=True,
        )
        self.item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Paneer Bowl",
            description="Curry bowl.",
            price=Decimal("220.00"),
            category="Main Course",
        )

    def test_cart_is_created_for_user(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(cart.user, self.user)

    def test_order_can_be_created_from_cart(self):
        self.client.force_login(self.user)
        self.client.post(reverse("add_to_cart", args=[self.item.pk]))
        response = self.client.post(
            reverse("checkout"),
            {"delivery_address": "123 Market Street"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(user=self.user).exists())

    def test_menu_has_an_authenticated_post_add_to_cart_action(self):
        response = self.client.get(reverse("restaurant_detail", args=[self.restaurant.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add to Cart")
        self.assertContains(response, reverse("add_to_cart", args=[self.item.pk]))

    def test_add_to_cart_increments_existing_item_and_enforces_one_restaurant_choice(self):
        second_restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Second Kitchen",
            cuisine_type="Indian",
            address="Second Road",
            phone="9999999998",
            status="approved",
            is_active=True,
        )
        second_item = MenuItem.objects.create(
            restaurant=second_restaurant,
            name="Veg Wrap",
            price=Decimal("160.00"),
            category="Wraps",
        )
        self.client.force_login(self.user)
        add_url = reverse("add_to_cart", args=[self.item.pk])
        self.client.post(add_url)
        self.client.post(add_url)
        cart = Cart.objects.get(user=self.user)
        cart_item = cart.items.get(menu_item=self.item)
        self.assertEqual(cart_item.quantity, 2)

        conflict = self.client.post(reverse("add_to_cart", args=[second_item.pk]))
        self.assertEqual(conflict.status_code, 409)
        self.assertContains(conflict, "Your cart contains items from another restaurant.", status_code=409)
        self.assertEqual(cart.items.count(), 1)

        continue_response = self.client.post(
            reverse("add_to_cart", args=[second_item.pk]),
            {"decision": "continue"},
        )
        self.assertEqual(continue_response.status_code, 302)
        cart.refresh_from_db()
        self.assertTrue(cart.items.filter(menu_item=self.item).exists())

        clear_response = self.client.post(
            reverse("add_to_cart", args=[second_item.pk]),
            {"decision": "clear"},
        )
        self.assertEqual(clear_response.status_code, 302)
        self.assertFalse(cart.items.filter(menu_item=self.item).exists())
        self.assertEqual(cart.items.get().menu_item, second_item)

    def test_cart_page_has_server_calculated_summary_and_item_controls(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, menu_item=self.item, quantity=2)
        self.client.force_login(self.user)

        response = self.client.get(reverse("cart"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item total")
        self.assertContains(response, "Delivery charge")
        self.assertContains(response, "Taxes / fees")
        self.assertContains(response, "Grand total")
        self.assertContains(response, reverse("cart_item_update", args=[item.pk, "increase"]))
        self.assertContains(response, reverse("cart_item_update", args=[item.pk, "decrease"]))

    def test_cart_contents_are_private_to_each_customer_account(self):
        other_customer = User.objects.create_user(
            username="cart_customer",
            email="cart_customer@example.com",
            password="test-password",
            role="customer",
        )
        other_item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Private Customer Dish",
            price=Decimal("180.00"),
            category="Main Course",
        )
        own_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=own_cart, menu_item=self.item)
        other_cart = Cart.objects.create(user=other_customer)
        CartItem.objects.create(cart=other_cart, menu_item=other_item)

        self.client.force_login(self.user)
        own_response = self.client.get(reverse("cart"))
        self.assertContains(own_response, self.item.name)
        self.assertNotContains(own_response, other_item.name)

        self.client.force_login(other_customer)
        other_response = self.client.get(reverse("cart"))
        self.assertContains(other_response, other_item.name)
        self.assertNotContains(other_response, self.item.name)

    def test_cart_item_quantity_buttons_decrease_and_remove(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, menu_item=self.item, quantity=2)
        self.client.force_login(self.user)

        self.client.post(reverse("cart_item_update", args=[item.pk, "decrease"]))
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)
        self.client.post(reverse("cart_item_update", args=[item.pk, "decrease"]))
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_order_history_page_loads(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("order_history"))
        self.assertEqual(response.status_code, 200)

    def test_customer_accounts_share_order_features_but_only_see_their_own_orders(self):
        other_customer = User.objects.create_user(
            username="another_customer",
            email="another_customer@example.com",
            password="test-password",
            role="customer",
        )
        own_order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="Customer One Address",
        )
        other_order = Order.objects.create(
            user=other_customer,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="Customer Two Address",
        )

        self.client.force_login(self.user)
        own_history = self.client.get(reverse("order_history"))
        own_tracking = self.client.get(reverse("order_detail", args=[own_order.pk]))
        inaccessible_tracking = self.client.get(
            reverse("order_detail", args=[other_order.pk]),
        )

        self.assertEqual(own_history.status_code, 200)
        self.assertContains(own_history, own_order.code)
        self.assertNotContains(own_history, other_order.code)
        self.assertEqual(own_tracking.status_code, 200)
        self.assertEqual(inaccessible_tracking.status_code, 404)

        self.client.force_login(other_customer)
        other_history = self.client.get(reverse("order_history"))
        self.assertContains(other_history, other_order.code)
        self.assertNotContains(other_history, own_order.code)

    def test_customer_dashboard_only_shows_greeting(self):
        CustomerProfile.objects.create(
            user=self.user,
            phone_number="9876501234",
            address="42 Beach Road, Visakhapatnam",
        )
        hidden_item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Cart Only Secret Item",
            price=Decimal("150.00"),
            is_available=False,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, menu_item=hidden_item, quantity=2)
        self.client.force_login(self.user)

        response = self.client.get(reverse("customer_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Good to see you, customeruser.")
        self.assertNotContains(response, "9876501234")
        self.assertNotContains(response, "Cart Only Secret Item")
        self.assertNotContains(response, "Recent orders")
        self.assertContains(response, "Use my current location")
        self.assertContains(response, "Delivery location")
        self.assertNotContains(response, "Switch to Delivery Shift")
        self.assertLess(
            response.content.index(b"customer-account-trigger-name"),
            response.content.index(b"id=\"customerGpsButton\""),
        )

    def test_customer_dashboard_uses_saved_gps_state_to_filter_restaurants(self):
        matching = Restaurant.objects.create(
            owner=self.owner,
            name="Andhra Kitchen",
            cuisine_type="Indian",
            address="Beach Road",
            city="Visakhapatnam",
            state="Andhra Pradesh",
            status="approved",
            is_active=True,
        )
        other = Restaurant.objects.create(
            owner=self.owner,
            name="Karnataka Kitchen",
            cuisine_type="Indian",
            address="MG Road",
            city="Bengaluru",
            state="Karnataka",
            status="approved",
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.user,
            state="Andhra Pradesh",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("customer_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.name)
        self.assertNotContains(response, other.name)
        self.assertContains(response, "Restaurants in Andhra Pradesh")

    def test_restaurant_owner_can_accept_or_reject_order(self):
        owner = User.objects.create_user(
            username="restaurantowner2",
            email="owner2@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="Green Bowl",
            cuisine_type="Healthy",
            description="Healthy meals.",
            address="Central Avenue",
            phone="9876500000",
            status="approved",
            is_active=True,
        )
        item = MenuItem.objects.create(
            restaurant=restaurant,
            name="Salad Bowl",
            description="Fresh bowl.",
            price=Decimal("140.00"),
            category="Healthy",
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, menu_item=item, quantity=2)
        order = Order.objects.create(
            user=self.user,
            restaurant=restaurant,
            total_price=Decimal("280.00"),
            delivery_address="12 Market Street",
        )
        Payment.objects.create(
            order=order,
            amount=order.total_price,
            payment_method="test",
            transaction_id="TEST-ORDER-ACCEPT",
            status="paid",
        )
        OrderItem.objects.create(
            order=order,
            menu_item=item,
            quantity=2,
            unit_price=item.price,
        )

        self.client.force_login(owner)
        response = self.client.get(reverse("restaurant_order_management"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Order progress")
        self.assertContains(response, "Finding a delivery partner")
        self.assertContains(response, "Partner at restaurant")
        self.assertContains(response, "Delivered")
        self.assertContains(response, "Cancelled")
        self.assertContains(response, "Rejected")
        self.assertContains(response, "Salad Bowl")
        self.assertContains(response, "× 2")
        self.assertContains(response, "₹280.00")

        accept_response = self.client.post(reverse("order_accept", args=[order.pk]))
        self.assertEqual(accept_response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_ACCEPTED)

        rejected_order = Order.objects.create(
            user=self.user,
            restaurant=restaurant,
            total_price=Decimal("140.00"),
            delivery_address="12 Market Street",
        )
        Payment.objects.create(
            order=rejected_order,
            amount=rejected_order.total_price,
            payment_method="cod",
            status="pending",
        )
        reject_response = self.client.post(
            reverse("order_reject", args=[rejected_order.pk]),
            {"rejection_reason": "item_unavailable", "rejection_note": "Out of stock"},
        )
        self.assertEqual(reject_response.status_code, 302)
        rejected_order.refresh_from_db()
        self.assertEqual(rejected_order.status, Order.STATUS_REJECTED)
        self.assertEqual(rejected_order.rejection_reason, "item_unavailable")
        self.assertEqual(rejected_order.rejection_note, "Out of stock")

    def test_restaurant_can_cancel_an_accepted_order(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
            status=Order.STATUS_ACCEPTED,
        )
        Payment.objects.create(
            order=order,
            amount=order.total_price,
            payment_method="test",
            transaction_id="TEST-ORDER-CANCEL",
            status="paid",
        )
        self.client.force_login(self.owner)

        response = self.client.post(reverse("order_cancel", args=[order.pk]))

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)

    def test_restaurant_cancellation_releases_an_active_delivery_offer(self):
        from orders.services import transition_restaurant_order

        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
            status=Order.STATUS_DELIVERY_ASSIGNED,
        )
        partner = User.objects.create_user(
            username="cancel_partner",
            email="cancel_partner@example.com",
            password="test-password",
            role="delivery_partner",
        )
        profile = DeliveryPartnerProfile.objects.create(
            user=partner,
            is_available=False,
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            partner=partner,
            status=DeliveryAssignment.STATUS_ASSIGNED,
        )
        attempt = DeliveryAssignmentAttempt.objects.create(
            assignment=assignment,
            partner=partner,
        )

        transition_restaurant_order(
            self.owner,
            order.pk,
            Order.STATUS_CANCELLED,
            rejection_note="Kitchen closed",
        )

        order.refresh_from_db()
        assignment.refresh_from_db()
        attempt.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertEqual(assignment.status, DeliveryAssignment.STATUS_CANCELLED)
        self.assertEqual(attempt.status, DeliveryAssignmentAttempt.STATUS_CANCELLED)
        self.assertEqual(attempt.rejection_reason, "Kitchen closed")
        self.assertTrue(profile.is_available)

    def test_restaurant_order_decisions_reject_get_requests(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("order_accept", args=[order.pk]))
        self.assertEqual(response.status_code, 405)

    def test_customer_api_checkout_uses_database_prices_and_clears_cart(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        add_response = client.post(
            "/api/cart/",
            {"menu_item_id": self.item.pk, "quantity": 2},
            format="json",
        )
        self.assertEqual(add_response.status_code, 201)

        response = client.post(
            "/api/orders/",
            {
                "delivery_address": "123 Market Street",
                "total_price": "0.01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.subtotal, Decimal("440.00"))
        self.assertEqual(
            order.total_price,
            order.subtotal + order.tax_amount + order.delivery_fee - order.discount_amount,
        )
        self.assertNotEqual(order.total_price, Decimal("0.01"))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertFalse(self.user.cart.items.exists())

    def test_customer_order_api_does_not_expose_another_users_order(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
        )
        other_customer = User.objects.create_user(
            username="other_customer",
            email="other_customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        client = APIClient()
        client.force_authenticate(user=other_customer)
        response = client.get(f"/api/orders/{order.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_non_customer_cannot_use_cart_api(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.get("/api/cart/")
        self.assertEqual(response.status_code, 403)

    def test_order_status_api_returns_timeline_only_to_its_customer(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
            status="preparing",
        )
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get(f"/api/orders/{order.pk}/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "preparing")
        self.assertTrue(response.data["timeline"][2]["current"])

        other_customer = User.objects.create_user(
            username="tracking_other",
            email="tracking_other@example.com",
            password="StrongPass123!",
            role="customer",
        )
        client.force_authenticate(user=other_customer)
        response = client.get(f"/api/orders/{order.pk}/status/")
        self.assertEqual(response.status_code, 404)

    def test_order_detail_page_includes_live_tracking(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("order_detail", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "orderTracking")
        self.assertContains(response, reverse("api_order_status", args=[order.pk]))
        self.assertContains(response, "Restaurant")
        self.assertContains(response, "Delivery address")
        self.assertContains(response, self.restaurant.name)

    def test_order_tracking_api_includes_restaurant_and_delivery_details(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
            status=Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
        )
        partner = User.objects.create_user(
            username="tracking_partner",
            email="tracking_partner@example.com",
            password="test-password",
            role="delivery_partner",
        )
        profile = DeliveryPartnerProfile.objects.create(
            user=partner,
            vehicle_type="Bike",
            vehicle_number="AP01AB1234",
        )
        DeliveryAssignment.objects.create(
            order=order,
            partner=partner,
            status=DeliveryAssignment.STATUS_ACCEPTED,
        )
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.get(f"/api/orders/{order.pk}/tracking/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["restaurant"]["name"], self.restaurant.name)
        self.assertEqual(response.data["restaurant"]["phone"], self.restaurant.phone)
        self.assertEqual(response.data["delivery_partner"]["name"], partner.username)
        self.assertEqual(response.data["delivery_partner"]["vehicle"], profile.vehicle_type)
        self.assertEqual(response.data["delivery_partner"]["vehicle_number"], profile.vehicle_number)
        self.assertEqual(
            response.data["delivery_partner"]["status_display"],
            DeliveryAssignment.STATUS_CHOICES[1][1],
        )

    def test_terminal_tracking_hides_partner_location_and_denies_partner_access(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
            status=Order.STATUS_CANCELLED,
        )
        partner = User.objects.create_user(
            username="ended_tracking_partner",
            email="ended_partner@example.com",
            password="test-password",
            role="delivery_partner",
        )
        profile = DeliveryPartnerProfile.objects.create(
            user=partner,
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            location_updated_at=timezone.now(),
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            partner=partner,
            status=DeliveryAssignment.STATUS_CANCELLED,
        )
        DeliveryLocation.objects.create(
            assignment=assignment,
            delivery_partner=partner,
            order=order,
            latitude=profile.latitude,
            longitude=profile.longitude,
        )
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.get(f"/api/orders/{order.pk}/tracking/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["location"])
        client.force_authenticate(user=partner)
        response = client.get(f"/api/orders/{order.pk}/tracking/")
        self.assertEqual(response.status_code, 403)

    def test_restaurant_order_api_is_scoped_and_uses_valid_transitions(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
        )
        Payment.objects.create(
            order=order,
            amount=order.total_price,
            payment_method="test",
            transaction_id="TEST-API-ACCEPT",
            status="paid",
        )
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.get("/api/restaurant/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [order.pk])

        response = client.post(
            f"/api/restaurant/orders/{order.pk}/accept/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Order.STATUS_ACCEPTED)

        other_owner = User.objects.create_user(
            username="api_other_owner",
            email="api_other_owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        client.force_authenticate(user=other_owner)
        response = client.post(
            f"/api/restaurant/orders/{order.pk}/preparing/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_restaurant_queue_hides_unpaid_online_orders(self):
        Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
        )
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.get("/api/restaurant/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_ready_restaurant_order_is_assigned_to_an_online_partner(self):
        order = Order.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            total_price=Decimal("220.00"),
            delivery_address="12 Market Street",
        )
        Payment.objects.create(
            order=order,
            amount=order.total_price,
            payment_method="test",
            transaction_id="TEST-READY-ASSIGNMENT",
            status="paid",
        )
        self.restaurant.latitude = Decimal("17.7000")
        self.restaurant.longitude = Decimal("83.2200")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        partner = User.objects.create_user(
            username="online_partner",
            email="online_partner@example.com",
            password="StrongPass123!",
            role="delivery_partner",
        )
        DeliveryPartnerProfile.objects.create(
            user=partner,
            is_online=True,
            latitude=Decimal("17.7000"),
            longitude=Decimal("83.2200"),
            location_updated_at=timezone.now(),
        )
        client = APIClient()
        client.force_authenticate(user=self.owner)

        self.assertEqual(
            client.post(f"/api/restaurant/orders/{order.pk}/accept/", {}, format="json").status_code,
            200,
        )
        self.assertEqual(
            client.post(f"/api/restaurant/orders/{order.pk}/preparing/", {}, format="json").status_code,
            200,
        )
        response = client.post(
            f"/api/restaurant/orders/{order.pk}/ready/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        assignment = DeliveryAssignment.objects.get(order=order)
        self.assertEqual(assignment.partner, partner)
        self.assertEqual(assignment.status, "assigned")
        self.assertTrue(partner.notifications.filter(category="delivery").exists())
        self.assertTrue(self.user.notifications.filter(category="order").exists())
