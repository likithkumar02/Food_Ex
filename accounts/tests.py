import json
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from customer.models import CustomerProfile
from .middleware import RoleSessionMiddleware


User = get_user_model()


class UserRoleTests(TestCase):
    def test_user_roles_are_defined(self):
        roles = dict(User.ROLE_CHOICES)
        self.assertIn("customer", roles)
        self.assertIn("restaurant_owner", roles)
        self.assertIn("delivery_partner", roles)
        self.assertIn("admin", roles)

    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

    def test_user_can_register(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newcustomer",
                "email": "customer@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "first_name": "New",
                "last_name": "Customer",
                "role": "customer",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newcustomer").exists())
        self.assertEqual(User.objects.get(username="newcustomer").role, "customer")

    def test_customer_dashboard_redirect(self):
        user = User.objects.create_user(
            username="customeruser",
            email="customeruser@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("customer_dashboard"))

    def test_restaurant_order_urls_use_restaurant_session_before_customer_order_prefix(self):
        customer = User.objects.create_user(
            username="session_customer",
            email="session_customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        owner = User.objects.create_user(
            username="session_owner",
            email="session_owner@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        request = RequestFactory().get("/orders/restaurant/orders/")
        request.user = AnonymousUser()
        request.session = {
            "_customer_user_id": str(customer.pk),
            "_restaurant_owner_user_id": str(owner.pk),
        }

        resolved_user = RoleSessionMiddleware(lambda current_request: current_request.user)(request)

        self.assertEqual(resolved_user.pk, owner.pk)
        self.assertEqual(resolved_user.role, "restaurant_owner")

    def test_customer_profile_can_update_email_phone_and_address(self):
        user = User.objects.create_user(
            username="profile_editor",
            email="profile_editor@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("customer_profile"),
            {
                "first_name": "Profile",
                "last_name": "Editor",
                "email": "profile.updated@example.com",
                "phone_number": "9876504321",
                "address": "42 Beach Road, Visakhapatnam",
            },
        )

        self.assertRedirects(response, reverse("customer_profile"))
        user.refresh_from_db()
        profile = CustomerProfile.objects.get(user=user)
        self.assertEqual(user.email, "profile.updated@example.com")
        self.assertEqual(profile.phone_number, "9876504321")
        self.assertEqual(profile.address, "42 Beach Road, Visakhapatnam")

    def test_customer_header_actions_match_authentication_state(self):
        guest_response = self.client.get(reverse("customer_portal"))
        self.assertContains(guest_response, "Log in")
        self.assertContains(guest_response, "Sign up")

        customer = User.objects.create_user(
            username="header_customer",
            email="header_customer@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(customer)
        dashboard_response = self.client.get(reverse("customer_dashboard"))
        self.assertContains(dashboard_response, "Open account menu")
        self.assertContains(dashboard_response, "Settings")
        self.assertContains(dashboard_response, "Log out")
        self.assertNotContains(dashboard_response, "Sign up")
        self.assertNotContains(dashboard_response, "Log in")

    def test_customer_accounts_share_the_same_features_without_sharing_identity(self):
        customers = [
            User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password="StrongPass123!",
                first_name=first_name,
                role="customer",
            )
            for username, first_name in (
                ("customer_one", "Asha"),
                ("customer_two", "Ravi"),
            )
        ]

        for customer, other_customer in (
            (customers[0], customers[1]),
            (customers[1], customers[0]),
        ):
            with self.subTest(customer=customer.username):
                self.client.force_login(customer)
                response = self.client.get(reverse("customer_dashboard"))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"Good to see you, {customer.first_name}.")
                self.assertContains(response, "Open account menu")
                self.assertContains(response, "Settings")
                self.assertContains(response, "Delivery location")
                self.assertContains(response, "Use my current location")
                self.assertNotContains(response, other_customer.username)
                self.assertNotContains(response, "Switch to Delivery Shift")

    def test_admin_dashboard_lists_users(self):
        admin = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="StrongPass123!",
            role="admin",
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("users", response.context)
        self.assertContains(response, admin.username)

    def test_guest_customer_dashboard_shows_auth_prompt(self):
        response = self.client.get(reverse("customer_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Access your account")
        self.assertContains(response, "Log in to your account")

    def test_each_portal_entry_page_loads(self):
        for route_name in (
            "customer_portal",
            "restaurant_portal",
            "delivery_portal",
            "customer_login",
            "restaurant_login",
            "delivery_login",
            "customer_register",
            "restaurant_register",
            "delivery_register",
        ):
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

    def test_legacy_restaurant_portal_route_redirects_to_partner_route(self):
        response = self.client.get("/restaurant/?source=legacy")
        self.assertRedirects(
            response,
            reverse("restaurant_portal") + "?source=legacy",
        )

    def test_homepage_shows_customer_discovery_and_partner_portals(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find food")
        self.assertContains(response, 'href="/customer/"', html=False)
        self.assertContains(response, "RESTAURANT PARTNERS")
        self.assertContains(response, "DELIVERY PARTNERS")

    def test_portal_registration_assigns_its_fixed_role(self):
        registrations = (
            ("customer_register", "portal_customer", "customer", {}),
            (
                "restaurant_register",
                "portal_owner",
                "restaurant_owner",
                {
                    "restaurant_name": "Portal Kitchen",
                    "restaurant_type": "both",
                    "cuisine_type": "Indian",
                    "restaurant_address": "12 Main Street",
                    "city": "Visakhapatnam",
                    "state": "Andhra Pradesh",
                    "pincode": "530001",
                    "restaurant_phone": "9876543211",
                    "fssai_number": "12345678901234",
                    "bank_account_number": "1234567890123456",
                    "bank_ifsc_code": "SBIN0001234",
                    "account_holder_name": "Portal Owner",
                },
            ),
            (
                "delivery_register",
                "portal_partner",
                "delivery_partner",
                {
                    "vehicle_type": "Bicycle",
                    "vehicle_number": "BIKE-1",
                    "license_number": "LICENSE-1",
                    "address": "12 Main Street",
                },
            ),
        )
        for route_name, username, role, extra_fields in registrations:
            with self.subTest(role=role):
                self.client.logout()
                response = self.client.post(
                    reverse(route_name),
                    {
                        "username": username,
                        "email": f"{username}@example.com",
                        "password1": "UniqueFood!9472",
                        "password2": "UniqueFood!9472",
                        "first_name": "Portal",
                        "last_name": "Owner",
                        "role": "admin",
                        "phone": f"98765432{len(username):02d}",
                        **extra_fields,
                    },
                )
                self.assertEqual(response.status_code, 302)
                user = User.objects.get(username=username)
                self.assertEqual(user.role, role)
                if role == "restaurant_owner":
                    restaurant = user.restaurants.get()
                    self.assertEqual(restaurant.name, "Portal Kitchen")
                    self.assertEqual(restaurant.city, "Visakhapatnam")
                    self.assertEqual(restaurant.state, "Andhra Pradesh")
                    self.assertEqual(restaurant.status, "pending")
                    self.assertFalse(restaurant.is_active)
                    self.assertEqual(user.customer_profile.phone_number, f"98765432{len(username):02d}")
                    self.assertEqual(response.url, reverse("restaurant_dashboard"))

    def test_portal_login_rejects_an_account_from_another_role(self):
        customer = User.objects.create_user(
            username="customer_for_portal",
            email="customer_for_portal@example.com",
            password="StrongPass123!",
            role="customer",
        )
        response = self.client.post(
            reverse("restaurant_login"),
            {"email": customer.email, "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not belong to this portal")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_restaurant_partner_can_log_in_and_reaches_dashboard(self):
        owner = User.objects.create_user(
            username="restaurant_partner_login",
            email="partner_login@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )

        response = self.client.post(
            reverse("restaurant_login"),
            {"email": owner.email, "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("restaurant_dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), owner.pk)

    def test_portal_login_and_register_remain_available_across_roles(self):
        customer = User.objects.create_user(
            username="customer_portal_switch",
            email="customer_portal_switch@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(customer)

        delivery_login = self.client.get(reverse("delivery_login"))
        self.assertEqual(delivery_login.status_code, 200)
        self.assertNotContains(delivery_login, "session is active in the")

        restaurant_page = self.client.get(reverse("restaurant_portal"))
        self.assertContains(restaurant_page, "Owner log in")
        self.assertContains(restaurant_page, "Register restaurant")
        self.assertNotContains(restaurant_page, "Owner dashboard")
        self.assertEqual(self.client.get(reverse("restaurant_login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("restaurant_register")).status_code, 200)

        owner = User.objects.create_user(
            username="owner_portal_switch",
            email="owner_portal_switch@example.com",
            password="StrongPass123!",
            role="restaurant_owner",
        )
        self.client.force_login(owner)

        customer_page = self.client.get(reverse("customer_portal"))
        self.assertContains(customer_page, "Log in")
        self.assertContains(customer_page, "Sign up")
        self.assertEqual(self.client.get(reverse("customer_login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("customer_register")).status_code, 200)

    def test_customer_cannot_open_restaurant_management(self):
        customer = User.objects.create_user(
            username="customer_blocked",
            email="customer_blocked@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(customer)
        response = self.client.get(reverse("restaurant_management"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/restaurant/login/"))

    def test_password_reset_sends_a_one_time_link_without_enumerating_accounts(self):
        user = User.objects.create_user(
            username="reset_user",
            email="reset_user@example.com",
            password="StrongPass123!",
            role="customer",
        )
        response = self.client.post(
            reverse("forgot_password"),
            {"email": user.email},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(
            r"/password-reset/([^/]+)/([^/\s]+)/",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(match)
        reset_path = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": match.group(1), "token": match.group(2)},
        )
        reset_response = self.client.get(reset_path, follow=True)
        self.assertEqual(reset_response.status_code, 200)
        if reset_response.redirect_chain:
            reset_path = reset_response.redirect_chain[-1][0].replace(
                f"http://{self.client.defaults.get('SERVER_NAME', 'testserver')}",
                "",
            )
        response = self.client.post(
            reset_path,
            {
                "new_password1": "KestrelRiver!8264",
                "new_password2": "KestrelRiver!8264",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("KestrelRiver!8264"))

        response = self.client.post(
            reverse("forgot_password"),
            {"email": "unknown@example.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_authenticated_user_can_change_password_through_api(self):
        user = User.objects.create_user(
            username="password_change_user",
            email="password_change_user@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("api_password_change"),
            json.dumps({
                "old_password": "StrongPass123!",
                "new_password": "OrchidHarbor!8264",
                "confirm_password": "OrchidHarbor!8264",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("OrchidHarbor!8264"))


class JwtAuthenticationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.registration_data = {
            "name": "Mani Kumar",
            "email": "mani@example.com",
            "phone": "9876543210",
            "password": "Raven!Flame8073",
            "confirm_password": "Raven!Flame8073",
        }

    def register(self, data=None):
        return self.client.post(
            "/api/auth/register/",
            data or self.registration_data,
            format="json",
        )

    def test_registration_hashes_password_and_creates_customer_profile(self):
        response = self.register()

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="mani@example.com")
        self.assertTrue(user.check_password(self.registration_data["password"]))
        self.assertNotEqual(user.password, self.registration_data["password"])
        self.assertEqual(user.role, "customer")
        self.assertEqual(user.customer_profile.phone_number, "9876543210")

    def test_restaurant_api_registration_creates_restaurant(self):
        response = self.client.post(
            "/api/auth/restaurant/register/",
            {
                **self.registration_data,
                "restaurant_name": "Tandoor House",
                "restaurant_type": "both",
                "cuisine_type": "Indian",
                "restaurant_address": "12 Main Street",
                "city": "Visakhapatnam",
                "state": "Andhra Pradesh",
                "pincode": "530001",
                "restaurant_phone": "9876543211",
                "fssai_number": "12345678901234",
                "bank_account_number": "1234567890123456",
                "bank_ifsc_code": "SBIN0001234",
                "account_holder_name": "Tandoor House",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="mani@example.com")
        self.assertEqual(user.role, "restaurant_owner")
        restaurant = user.restaurants.get()
        self.assertEqual(restaurant.name, "Tandoor House")
        self.assertEqual(restaurant.status, "pending")
        self.assertFalse(restaurant.is_active)
        self.assertEqual(restaurant.bank_account_number, "1234567890123456")

    def test_delivery_api_registration_creates_offline_partner_profile(self):
        response = self.client.post(
            "/api/auth/delivery/register/",
            {
                **self.registration_data,
                "vehicle_type": "Bicycle",
                "vehicle_number": "BIKE-1",
                "license_number": "LICENSE-1",
                "address": "12 Main Street",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="mani@example.com")
        self.assertEqual(user.role, "delivery_partner")
        self.assertFalse(user.delivery_profile.is_online)

    def test_role_specific_login_rejects_other_roles(self):
        customer = User.objects.create_user(
            username="customer_api",
            email="customer_api@example.com",
            password="StrongPass123!",
            role="customer",
        )
        response = self.client.post(
            "/api/auth/restaurant/login/",
            {"email": customer.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_api_registration_cannot_assign_a_privileged_role(self):
        response = self.register({**self.registration_data, "role": "admin"})
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="mani@example.com")
        self.assertEqual(user.role, "customer")

    def test_registration_rejects_duplicate_email_and_phone(self):
        self.assertEqual(self.register().status_code, 201)

        duplicate_email = {**self.registration_data, "phone": "9876543211"}
        self.assertEqual(self.register(duplicate_email).status_code, 400)

        duplicate_phone = {
            **self.registration_data,
            "email": "other@example.com",
        }
        self.assertEqual(self.register(duplicate_phone).status_code, 400)

    def test_login_returns_jwt_tokens_and_profile_data(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.client.post(
            "/api/auth/login/",
            {
                "email": "mani@example.com",
                "password": self.registration_data["password"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["name"], "Mani Kumar")

    def test_profile_requires_jwt_and_can_be_updated(self):
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)

        self.assertEqual(self.register().status_code, 201)
        login_response = self.client.post(
            "/api/auth/login/",
            {
                "email": "mani@example.com",
                "password": self.registration_data["password"],
            },
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.put(
            "/api/auth/profile/",
            {
                "name": "Mani Kumar Reddy",
                "email": "mani.updated@example.com",
                "phone": "9876543212",
                "address": "Visakhapatnam",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Mani Kumar Reddy")
        self.assertEqual(response.data["email"], "mani.updated@example.com")
        self.assertEqual(response.data["phone"], "9876543212")
        self.assertEqual(response.data["address"], "Visakhapatnam")


class SeparateSessionTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="test_customer",
            email="cust@example.com",
            password="StrongPass123!",
            role="customer",
            first_name="Alice",
        )
        self.partner = User.objects.create_user(
            username="test_partner",
            email="delivery@example.com",
            password="StrongPass123!",
            role="delivery_partner",
            first_name="Bob",
        )
        from delivery.models import DeliveryPartnerProfile

        DeliveryPartnerProfile.objects.create(
            user=self.partner,
            vehicle_type="Motorcycle",
            vehicle_number="AP39-1234",
            license_number="LIC-1234",
            address="Beach Road",
        )

    def test_customer_and_delivery_sessions_coexist_independently(self):
        # 1. Customer logs in
        cust_login = self.client.post(
            reverse("customer_login"),
            {"email": self.customer.email, "password": "StrongPass123!"},
        )
        self.assertRedirects(cust_login, reverse("customer_dashboard"))

        # Customer portal recognises customer
        cust_resp = self.client.get(reverse("customer_portal"))
        self.assertContains(cust_resp, "Alice")

        # 2. In the same session, Delivery Partner logs in
        deliv_login = self.client.post(
            reverse("delivery_login"),
            {"email": self.partner.email, "password": "StrongPass123!"},
        )
        self.assertRedirects(deliv_login, reverse("delivery_dashboard"))

        # Delivery dashboard recognises delivery partner
        deliv_dash = self.client.get(reverse("delivery_dashboard"))
        self.assertEqual(deliv_dash.status_code, 200)

        # 3. Customer portal still recognises customer in the same browser session
        cust_portal_again = self.client.get(reverse("customer_portal"))
        self.assertContains(cust_portal_again, "Alice")

        # 4. Delivery partner logs out
        deliv_logout = self.client.post(reverse("delivery_logout"))
        self.assertRedirects(deliv_logout, reverse("delivery_portal"))

        # Delivery dashboard now redirects to login
        deliv_dash_after = self.client.get(reverse("delivery_dashboard"))
        self.assertEqual(deliv_dash_after.status_code, 302)

        # 5. Customer is STILL logged in
        cust_portal_third = self.client.get(reverse("customer_portal"))
        self.assertContains(cust_portal_third, "Alice")

        # 6. Customer logs out
        cust_logout = self.client.post(reverse("customer_logout"))
        self.assertRedirects(cust_logout, reverse("customer_portal"))

        cust_portal_final = self.client.get(reverse("customer_portal"))
        self.assertContains(cust_portal_final, "Log in")

    def test_delivery_portal_does_not_block_user_when_customer_session_is_active(self):
        self.client.post(
            reverse("customer_login"),
            {"email": self.customer.email, "password": "StrongPass123!"},
        )
        response = self.client.get(reverse("delivery_portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Partner log in")
        self.assertContains(response, "Join the delivery team")
        self.assertNotContains(response, "This session is signed in as another account type")


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="del_customer",
            email="del_cust@example.com",
            password="StrongPass123!",
            role="customer",
        )
        self.partner = User.objects.create_user(
            username="del_partner",
            email="del_partner@example.com",
            password="StrongPass123!",
            role="delivery_partner",
        )
        self.admin = User.objects.create_user(
            username="del_admin",
            email="del_admin@example.com",
            password="StrongPass123!",
            role="admin",
            is_staff=True,
        )

    def test_customer_can_delete_own_account(self):
        self.client.force_login(self.customer)
        response = self.client.post(reverse("delete_account"))
        self.assertRedirects(response, reverse("customer_portal"))
        self.assertFalse(User.objects.filter(username="del_customer").exists())

    def test_delivery_partner_can_delete_own_account(self):
        self.client.force_login(self.partner)
        response = self.client.post(reverse("delete_account"))
        self.assertRedirects(response, reverse("delivery_portal"))
        self.assertFalse(User.objects.filter(username="del_partner").exists())

    def test_admin_can_delete_user_from_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_delete_user", args=[self.customer.pk]))
        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertFalse(User.objects.filter(username="del_customer").exists())

    def test_admin_cannot_delete_own_account(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_delete_user", args=[self.admin.pk]))
        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertTrue(User.objects.filter(username="del_admin").exists())

    def test_delete_account_confirm_page_loads(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("delete_account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Account Confirmation")

    def test_api_delete_account(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.delete(reverse("auth_delete_account_api"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="del_customer").exists())
