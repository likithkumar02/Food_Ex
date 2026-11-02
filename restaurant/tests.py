from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import MenuItem, Restaurant

User = get_user_model()


class RestaurantModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="restaurantowner",
            email="owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Spice Route",
            cuisine_type="Indian",
            description="Fresh Indian meals.",
            address="Main Street",
            phone="9876543210",
            status="approved",
            is_active=True,
        )

    def test_restaurant_can_be_created(self):
        self.assertEqual(self.restaurant.name, "Spice Route")
        self.assertTrue(Restaurant.objects.filter(pk=self.restaurant.pk).exists())

    def test_menu_item_can_be_created(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Classic Burger",
            description="Juicy grilled burger.",
            price=Decimal("180.00"),
            category="Main Course",
        )
        self.assertEqual(item.restaurant, self.restaurant)
        self.assertEqual(item.price, Decimal("180.00"))

    def test_bank_account_number_is_encrypted_in_database(self):
        account_number = "1234567890123456"
        self.restaurant.bank_account_number = account_number
        self.restaurant.save(update_fields=["bank_account_number"])

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT bank_account_number FROM restaurant_restaurant WHERE id = %s",
                [self.restaurant.pk],
            )
            stored_value = cursor.fetchone()[0]

        self.assertNotIn(account_number, stored_value)
        self.assertTrue(stored_value.startswith("fernet:v1:"))
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.bank_account_number, account_number)

    def test_admin_approval_activates_restaurant(self):
        from restaurant.admin import approve_restaurants

        self.restaurant.status = "pending"
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=["status", "is_active"])

        approve_restaurants(None, None, Restaurant.objects.filter(pk=self.restaurant.pk))

        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.status, "approved")
        self.assertTrue(self.restaurant.is_active)

    def test_pending_owner_dashboard_hides_operations(self):
        self.restaurant.status = "pending"
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=["status", "is_active"])
        self.client.force_login(self.owner)

        response = self.client.get(reverse("restaurant_dashboard"))

        self.assertContains(response, "under verification")
        self.assertNotContains(response, "Review orders")

    def test_restaurant_list_page_loads(self):
        response = self.client.get(reverse("restaurant_list"))
        self.assertRedirects(response, reverse("customer_portal"))

        response = self.client.get(reverse("customer_portal"))
        self.assertEqual(response.status_code, 200)

    def test_restaurant_list_redirect_preserves_search_and_location(self):
        response = self.client.get(
            reverse("restaurant_list"),
            {"q": "Spice", "city": "Visakhapatnam", "state": "Andhra Pradesh"},
        )
        self.assertRedirects(
            response,
            reverse("customer_portal") + "?q=Spice&city=Visakhapatnam&state=Andhra+Pradesh",
        )

    def test_restaurant_dashboard_redirects_guests_to_owner_login(self):
        response = self.client.get(reverse("restaurant_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('restaurant_login')}?next={reverse('restaurant_dashboard')}",
        )

    def test_customer_header_search_submits_to_customer_portal(self):
        response = self.client.get(reverse("customer_portal"), {"q": "Spice"})
        self.assertContains(response, '<form class="customer-search-box"', html=False)
        self.assertContains(response, 'action="/customer/"', html=False)
        self.assertContains(response, 'value="Spice"', html=False)

    def test_customer_list_welcomes_authenticated_customer_by_name(self):
        customer = User.objects.create_user(
            username="rahul_customer",
            email="rahul@example.com",
            password="A-secure-test-password-42!",
            role="customer",
            first_name="Rahul",
        )
        self.client.force_login(customer)

        response = self.client.get(reverse("customer_portal"))

        self.assertContains(response, "WELCOME BACK")
        self.assertContains(response, "Welcome, Rahul!")
        self.assertContains(response, "Discover local favorites and popular cuisines.")

    def test_guest_can_view_restaurant_menu_images_and_prices(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Paneer Bowl",
            description="A fresh bowl.",
            price=Decimal("220.00"),
            category="Main Course",
            image="menu/paneer-bowl.jpg",
        )

        response = self.client.get(reverse("restaurant_detail", args=[self.restaurant.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, item.name)
        self.assertContains(response, "₹220.00")
        self.assertContains(response, item.image.url)

    def test_pending_restaurant_is_hidden_even_if_marked_active(self):
        self.restaurant.status = "pending"
        self.restaurant.is_active = True
        self.restaurant.save(update_fields=["status", "is_active"])

        customer_response = self.client.get(reverse("customer_portal"))
        self.assertNotContains(customer_response, self.restaurant.name)

        detail_response = self.client.get(
            reverse("restaurant_detail", args=[self.restaurant.pk])
        )
        self.assertEqual(detail_response.status_code, 404)

        api_response = APIClient().get("/api/restaurants/")
        self.assertNotIn(self.restaurant.name, [restaurant["name"] for restaurant in api_response.data])

    def test_restaurant_search_matches_location(self):
        response = self.client.get(reverse("customer_portal"), {"q": "Main Street"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.restaurant.name)

    def test_restaurant_list_filters_by_state_and_city(self):
        matching = Restaurant.objects.create(
            owner=self.owner,
            name="Sea Breeze",
            cuisine_type="Seafood",
            description="Coastal favorites.",
            address="Beach Road, Visakhapatnam, Andhra Pradesh",
            phone="9876543211",
            status="approved",
            is_active=True,
        )
        other = Restaurant.objects.create(
            owner=self.owner,
            name="Biryani House",
            cuisine_type="Indian",
            description="Classic biryani.",
            address="MG Road, Bengaluru, Karnataka",
            phone="9876543212",
            status="approved",
            is_active=True,
        )

        response = self.client.get(reverse("customer_portal"), {"state": "Andhra Pradesh"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.name)
        self.assertNotContains(response, other.name)

        city_response = self.client.get(reverse("customer_portal"), {"city": "Visakhapatnam"})
        self.assertContains(city_response, matching.name)
        self.assertNotContains(city_response, other.name)

        area_response = self.client.get(
            reverse("customer_portal"),
            {"area": "Beach Road", "city": "Visakhapatnam", "state": "Andhra Pradesh"},
        )
        self.assertContains(area_response, matching.name)
        self.assertNotContains(area_response, other.name)

    def test_homepage_shows_all_approved_restaurants_then_filters_by_state(self):
        matching = Restaurant.objects.create(
            owner=self.owner,
            name="Andhra Kitchen",
            cuisine_type="Indian",
            description="Local meals.",
            address="Beach Road",
            city="Visakhapatnam",
            state="Andhra Pradesh",
            phone="9876543211",
            status="approved",
            is_active=True,
        )
        other = Restaurant.objects.create(
            owner=self.owner,
            name="Karnataka Kitchen",
            cuisine_type="Indian",
            description="Local meals.",
            address="MG Road",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543212",
            status="approved",
            is_active=True,
        )
        andhra_dish = MenuItem.objects.create(
            restaurant=matching,
            name="Andhra Meals",
            price=Decimal("150.00"),
            category="Meals",
        )
        karnataka_dish = MenuItem.objects.create(
            restaurant=other,
            name="Karnataka Meals",
            price=Decimal("160.00"),
            category="Meals",
        )

        initial_response = self.client.get(reverse("home"))
        self.assertContains(initial_response, matching.name)
        self.assertContains(initial_response, other.name)
        self.assertContains(initial_response, andhra_dish.name)
        self.assertContains(initial_response, karnataka_dish.name)
        self.assertEqual(initial_response.context["restaurant_count"], 3)

        state_response = self.client.get(reverse("home"), {"state": "Andhra Pradesh"})
        self.assertContains(state_response, matching.name)
        self.assertNotContains(state_response, other.name)
        self.assertContains(state_response, andhra_dish.name)
        self.assertNotContains(state_response, karnataka_dish.name)
        self.assertEqual(state_response.context["restaurant_count"], 1)

    def test_customer_pages_do_not_render_gps_controls(self):
        homepage = self.client.get(reverse("home"))
        customer_list = self.client.get(reverse("customer_portal"))

        self.assertNotContains(homepage, "customerLocationBox")
        self.assertNotContains(customer_list, "customerLocationBox")
        self.assertNotContains(homepage, "Use my current location")
        self.assertNotContains(customer_list, "Use my current location")

    def test_customer_dashboard_filters_approved_restaurants_by_state(self):
        matching = Restaurant.objects.create(
            owner=self.owner,
            name="Andhra Dashboard Kitchen",
            cuisine_type="Indian",
            description="Local meals.",
            address="Beach Road",
            city="Visakhapatnam",
            state="Andhra Pradesh",
            phone="9876543211",
            status="approved",
            is_active=True,
        )
        other = Restaurant.objects.create(
            owner=self.owner,
            name="Karnataka Dashboard Kitchen",
            cuisine_type="Indian",
            description="Local meals.",
            address="MG Road",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543212",
            status="approved",
            is_active=True,
        )
        customer = User.objects.create_user(
            username="dashboard_customer",
            email="dashboard_customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(customer)

        response = self.client.get(
            reverse("customer_dashboard"),
            {"state": "Andhra Pradesh"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.name)
        self.assertNotContains(response, other.name)
        self.assertContains(response, "Restaurants in Andhra Pradesh")

    def test_homepage_offers_all_restaurants_when_selected_state_has_no_matches(self):
        response = self.client.get(reverse("home"), {"state": "Andhra Pradesh"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No approved restaurants in Andhra Pradesh yet.")
        self.assertContains(response, 'href="/customer/"', html=False)
        self.assertContains(response, "Browse all available restaurants")

    def test_customer_listing_offers_all_restaurants_when_selected_state_has_no_matches(self):
        response = self.client.get(
            reverse("customer_portal"),
            {"state": "Andhra Pradesh"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No approved restaurants in Andhra Pradesh yet")
        self.assertContains(response, 'href="/customer/"', html=False)
        self.assertContains(response, "Browse all available restaurants")

    def test_location_filter_uses_structured_fields_and_falls_back_to_state(self):
        matching = Restaurant.objects.create(
            owner=self.owner,
            name="Madhurawada Kitchen",
            cuisine_type="Indian",
            description="Local meals.",
            address="Block 14",
            city="Madhurawada",
            state="Andhra Pradesh",
            phone="9876543211",
            status="approved",
            is_active=True,
        )
        other = Restaurant.objects.create(
            owner=self.owner,
            name="Bengaluru Kitchen",
            cuisine_type="Indian",
            description="Local meals.",
            address="MG Road",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543212",
            status="approved",
            is_active=True,
        )
        same_state = Restaurant.objects.create(
            owner=self.owner,
            name="Visakhapatnam Curry House",
            cuisine_type="Indian",
            description="Coastal meals.",
            address="Beach Road",
            city="Visakhapatnam",
            state="Andhra Pradesh",
            phone="9876543213",
            status="approved",
            is_active=True,
        )

        exact_city_response = self.client.get(
            reverse("customer_portal"),
            {"city": "Madhurawada", "state": "Andhra Pradesh"},
        )
        self.assertContains(exact_city_response, matching.name)
        self.assertNotContains(exact_city_response, other.name)

        state_fallback_response = self.client.get(
            reverse("customer_portal"),
            {"city": "Old Paradesipalem", "state": "Andhra Pradesh"},
        )
        self.assertContains(state_fallback_response, matching.name)
        self.assertContains(state_fallback_response, same_state.name)
        self.assertNotContains(state_fallback_response, other.name)

    def test_public_restaurant_api_returns_menu_data(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Masala Dosa",
            description="Crisp dosa.",
            price=Decimal("120.00"),
            category="South Indian",
        )
        client = APIClient()
        response = client.get(f"/api/restaurants/{self.restaurant.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["menu_items"][0]["id"], item.pk)

    def test_restaurant_menu_api_is_scoped_to_its_owner(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Masala Dosa",
            description="Crisp dosa.",
            price=Decimal("120.00"),
            category="South Indian",
        )
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.patch(
            f"/api/restaurants/manage/menu/{item.pk}/",
            {"price": "125.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        other_owner = User.objects.create_user(
            username="other_owner",
            email="other@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        client.force_authenticate(user=other_owner)
        response = client.patch(
            f"/api/restaurants/manage/menu/{item.pk}/",
            {"price": "1.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_restaurant_owner_can_manage_menu(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("restaurant_management"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("restaurant_management"),
            {
                "action": "add_menu_item",
                "name": "Butter Chicken",
                "description": "Rich tomato gravy.",
                "price": "299.00",
                "category": "Main Course",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            MenuItem.objects.filter(
                restaurant=self.restaurant,
                name="Butter Chicken",
            ).exists()
        )

    def test_pending_restaurant_owner_sees_customer_visibility_notice(self):
        self.restaurant.status = "pending"
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=["status", "is_active"])
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Chicken Biryani",
            price=Decimal("130.00"),
            category="Biryani",
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("restaurant_management"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not visible to customers.")
        self.assertContains(response, "waiting for admin approval")
        self.assertContains(response, "after approval")
        self.assertContains(response, item.name)

    def test_restaurant_owner_can_update_store_details(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("restaurant_management"),
            {
                "action": "update_restaurant",
                "name": "Spice Route Kitchen",
                "restaurant_type": "both",
                "cuisine_type": "South Indian",
                "description": "Fresh coastal meals.",
                "address": "42 Beach Road, Visakhapatnam",
                "phone": "9876543219",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.name, "Spice Route Kitchen")
        self.assertEqual(self.restaurant.cuisine_type, "South Indian")
        self.assertEqual(self.restaurant.address, "42 Beach Road, Visakhapatnam")
        self.assertEqual(self.restaurant.phone, "9876543219")

    def test_owner_dashboard_shows_store_and_menu_details(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Paneer Bowl",
            description="A fresh bowl.",
            price=Decimal("220.00"),
            category="Main Course",
            image="menu/paneer-bowl.jpg",
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("restaurant_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.restaurant.name)
        self.assertContains(response, self.restaurant.address)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Orders")
        self.assertContains(response, "Menu")
        self.assertContains(response, "Owner dashboard")
        self.assertContains(response, "Log out")
        self.assertContains(response, item.name)
        self.assertContains(response, "₹220.00")
        self.assertContains(response, item.image.url)

    def test_owner_dashboard_links_to_location_settings(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("restaurant_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("location_restaurant"))
        self.assertContains(response, "Location Settings")

        # Dedicated location page contains the interactive GPS map and controls
        loc_res = self.client.get(reverse("location_restaurant"))
        self.assertEqual(loc_res.status_code, 200)
        self.assertContains(loc_res, "Restaurant GPS Location")
        self.assertContains(loc_res, "Use My Current Location")
        self.assertContains(loc_res, "restaurantMap")

    def test_restaurant_location_update_api_get_and_post(self):
        api_client = APIClient()
        api_client.force_authenticate(user=self.owner)

        # 1. GET current location
        get_res = api_client.get(reverse("api_location_restaurant_update"))
        self.assertEqual(get_res.status_code, 200)
        self.assertTrue(get_res.data["success"])
        self.assertEqual(get_res.data["name"], self.restaurant.name)

        # 2. POST new location
        post_res = api_client.post(
            reverse("api_location_restaurant_update"),
            {
                "latitude": "17.6868",
                "longitude": "83.2185",
                "address": "42 Beach Road, Visakhapatnam",
                "address_line": "Opposite Beach Park",
                "area": "Beach Road",
                "city": "Visakhapatnam",
                "district": "Visakhapatnam",
                "state": "Andhra Pradesh",
                "pincode": "530002",
            },
            format="json",
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.data["success"])
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.latitude, Decimal("17.6868"))
        self.assertEqual(self.restaurant.longitude, Decimal("83.2185"))
        self.assertEqual(self.restaurant.address, "42 Beach Road, Visakhapatnam")
        self.assertEqual(self.restaurant.city, "Visakhapatnam")
        self.assertEqual(self.restaurant.state, "Andhra Pradesh")
        self.assertIsNotNone(self.restaurant.location_updated_at)

    def test_restaurant_location_update_api_permission_denied_for_customer(self):
        customer = User.objects.create_user(
            username="testcustomer",
            email="cust@example.com",
            password="StrongPass123!",
            role="customer",
        )
        api_client = APIClient()
        api_client.force_authenticate(user=customer)

        response = api_client.post(
            reverse("api_location_restaurant_update"),
            {"latitude": 17.6868, "longitude": 83.2185},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_restaurant_location_update_api_invalid_coords(self):
        api_client = APIClient()
        api_client.force_authenticate(user=self.owner)

        response = api_client.post(
            reverse("api_location_restaurant_update"),
            {"latitude": 195.0, "longitude": 83.2185},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])

    def test_nearby_discovery_uses_saved_restaurant_coordinates(self):
        from location.services import get_nearby_restaurants

        self.restaurant.latitude = Decimal("17.6868")
        self.restaurant.longitude = Decimal("83.2185")
        self.restaurant.save(update_fields=["latitude", "longitude"])

        # Customer at 17.6900, 83.2200 (less than 1 km away)
        nearby = get_nearby_restaurants(latitude=17.6900, longitude=83.2200, radius_km=5.0)
        restaurant_ids = [r["id"] for r in nearby]
        self.assertIn(self.restaurant.id, restaurant_ids)
        item = next(r for r in nearby if r["id"] == self.restaurant.id)
        self.assertIsNotNone(item["distance"])
        self.assertLess(item["distance"], 1.0)

    def test_restaurant_account_settings_view_authenticated(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("restaurant_account_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.owner.username)
        self.assertContains(response, self.owner.email)
        self.assertContains(response, self.restaurant.name)
        self.assertContains(response, "Edit Profile")
        self.assertContains(response, reverse("location_restaurant"))

    def test_restaurant_account_settings_unauthenticated_redirects(self):
        response = self.client.get(reverse("restaurant_account_settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_restaurant_account_settings_non_owner_forbidden(self):
        customer = User.objects.create_user(
            username="other_customer",
            email="other@example.com",
            password="secretpassword123",
            role="customer",
        )
        self.client.force_login(customer)
        response = self.client.get(reverse("restaurant_account_settings"))
        # role_required decorator redirects or returns 403
        self.assertIn(response.status_code, [302, 403])

    def test_restaurant_account_settings_post_updates_db(self):
        self.client.force_login(self.owner)
        payload = {
            "first_name": "Vikram",
            "last_name": "Reddy",
            "email": "vikram_owner@example.com",
            "mobile_number": "9876543210",
            "restaurant_name": "Royal Andhra Spice",
            "restaurant_type": "non_veg",
            "cuisine_type": "South Indian",
            "phone": "9876543210",
            "address": "45 Coastal Boulevard",
            "city": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "pincode": "530002",
            "description": "Authentic Andhra curries and biryanis.",
        }
        response = self.client.post(reverse("restaurant_account_settings"), payload)
        self.assertRedirects(response, reverse("restaurant_account_settings"))

        self.owner.refresh_from_db()
        self.restaurant.refresh_from_db()

        self.assertEqual(self.owner.first_name, "Vikram")
        self.assertEqual(self.owner.last_name, "Reddy")
        self.assertEqual(self.owner.email, "vikram_owner@example.com")
        self.assertEqual(self.restaurant.name, "Royal Andhra Spice")
        self.assertEqual(self.restaurant.city, "Visakhapatnam")
        self.assertEqual(self.restaurant.pincode, "530002")

        # GET request after update displays updated details
        get_res = self.client.get(reverse("restaurant_account_settings"))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, "Royal Andhra Spice")
        self.assertContains(get_res, "Visakhapatnam")

    def test_settings_url_redirects_restaurant_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("settings"))
        self.assertRedirects(response, reverse("restaurant_account_settings"))

    def test_settings_url_keeps_customer(self):
        customer = User.objects.create_user(
            username="cust_settings_test",
            email="cust_test@example.com",
            password="secretpassword123",
            role="customer",
        )
        self.client.force_login(customer)
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account settings")


