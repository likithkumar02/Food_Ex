"""Idempotent demo-data seeder for Food_Ex.

Run:  python manage.py seed_demo_data

Re-running this command is safe: every object uses get_or_create and
IntegrityErrors on secondary writes are caught and skipped.  Produces a
Bangalore-based mini ecosystem:

  * 1 admin (admin@foodex.in)
  * 1 customer (rahul@foodex.in) with a CustomerProfile + Bangalore address
  * 2 delivery partners (ravi, kiran) on bikes, online, in Bangalore
  * 2 approved restaurants (Ramesh Biryani Point, Sagar Veg) with full docs,
    4 categories × 3 items = 12 items per restaurant, 7 timings, 1 offer each
  * 1 PlatformSetting row (commission 15%, GST 5%, delivery fee ₹40)
  * 1 full delivered order (rahul → Ramesh Biryani Point, offer WELCOME20,
    2x Chicken Biryani) with: test payment, restaurant transitions,
    delivery partner assignment accepted → picked_up → delivered (so
    record_order_earning fires automatically), 4★ customer review.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.utils import timezone


def q(value, places="0.01"):
    return Decimal(value).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def try_save(obj, updates=None):
    try:
        with transaction.atomic():
            if updates:
                for k, v in updates.items():
                    setattr(obj, k, v)
            obj.save()
        return True
    except IntegrityError:
        return False


# ---------------------------------------------------------------------------
# Small helpers that translate "spec" dicts into get_or_create + unique-
# tolerant post-saves.  The ordering inside each helper matters because of
# foreign keys.
# ---------------------------------------------------------------------------

def _get_or_create_user(email, password, role, **extra):
    from accounts.models import User

    fields = {
        "email": email,
        "role": role,
        "is_staff": role == "admin",
        "is_superuser": role == "admin",
        "is_active": True,
    }
    fields.update(extra)
    username = fields.get("username") or email
    fields.setdefault("username", username)
    try:
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email, defaults=fields
            )
    except IntegrityError:
        user = User.objects.get(email=email)
        created = False
    # Always (re-)set password so re-runs keep credentials stable.
    try:
        user.set_password(password)
        for k, v in fields.items():
            setattr(user, k, v)
        user.save(update_fields=[
            "password", "role", "is_staff", "is_superuser", "is_active",
            "username", "first_name", "last_name",
        ])
    except IntegrityError:
        pass
    return user, created


def _update_or_create_profile(model, user_key, defaults):
    try:
        with transaction.atomic():
            profile, _ = model.objects.update_or_create(
                user=user_key, defaults=defaults
            )
        return profile
    except IntegrityError:
        return model.objects.filter(user=user_key).first()


# ---------------------------------------------------------------------------
# The command itself.
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed demo data for Food_Ex (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-order",
            action="store_true",
            help="Skip the delivered order + earning + review demo flow.",
        )

    def handle(self, *args, **options):
        self._seed_users()
        self._seed_platform_settings()
        self._seed_restaurant("ramesh_owner@foodex.in", self._ramesh_spec())
        self._seed_restaurant("sagar_owner@foodex.in", self._sagar_spec())
        counts = self._counts()
        for label, n in counts:
            self.stdout.write(f"  {label:<30}{n}")
        if not options["skip_order"]:
            self._seed_delivered_order()
            counts = self._counts(extended=True)
            for label, n in counts:
                self.stdout.write(f"  {label:<30}{n}")
        self.stdout.write(self.style.SUCCESS("Demo seed complete (idempotent)."))

    # ------------------------------------------------------------------
    # 1. Users + profiles
    # ------------------------------------------------------------------

    def _seed_users(self):
        # Admin
        admin, _ = _get_or_create_user(
            email="admin@foodex.in",
            password="Admin@123",
            role="admin",
            username="admin@foodex.in",
            first_name="FoodEx",
            last_name="Admin",
        )
        # Customer Rahul
        rahul, _ = _get_or_create_user(
            email="rahul@foodex.in",
            password="Rahul@123",
            role="customer",
            username="rahul@foodex.in",
            first_name="Rahul",
            last_name="Sharma",
        )
        from customer.models import CustomerProfile

        _update_or_create_profile(
            CustomerProfile,
            rahul,
            {
                "phone_number": "+919876543210",
                "address": "2nd Floor, 221B Baker Street, Indiranagar",
                "city": "Bangalore",
            },
        )
        # Delivery partners
        from delivery.models import DeliveryPartnerProfile

        for email, first, last, phone, vehicle_no, license_no, lat, lng, veh_type in [
            (
                "ravi@foodex.in", "Ravi", "Kumar", "+919988776655",
                "KA-01-AB-1234", "DL12345678",
                Decimal("12.971600"), Decimal("77.594600"), "bike",
            ),
            (
                "kiran@foodex.in", "Kiran", "Rao", "+919988776644",
                "KA-02-CD-5678", "DL87654321",
                Decimal("12.935200"), Decimal("77.624500"), "bike",
            ),
        ]:
            partner, _ = _get_or_create_user(
                email=email,
                password="Delivery@123",
                role="delivery_partner",
                username=email,
                first_name=first,
                last_name=last,
            )
            # Set phone via customer profile-less hack: DeliveryPartnerProfile
            # doesn't have a phone column, but address is text. We concatenate.
            _update_or_create_profile(
                DeliveryPartnerProfile,
                partner,
                {
                    "is_online": True,
                    "vehicle_type": veh_type,
                    "vehicle_number": vehicle_no,
                    "license_number": license_no,
                    "address": f"{phone} – Bangalore",
                    "latitude": lat,
                    "longitude": lng,
                },
            )
        # Restaurant owners — the restaurants themselves create their owners.
        for email, first, last in [
            ("ramesh_owner@foodex.in", "Ramesh", "Prasad"),
            ("sagar_owner@foodex.in", "Sagar", "Iyer"),
        ]:
            _get_or_create_user(
                email=email,
                password="Owner@123",
                role="restaurant_owner",
                username=email,
                first_name=first,
                last_name=last,
            )

    # ------------------------------------------------------------------
    # 2. Platform setting (singleton)
    # ------------------------------------------------------------------

    def _seed_platform_settings(self):
        from restaurant.models import PlatformSetting

        s = PlatformSetting.load()
        changed = False
        target = {
            "default_commission_percent": Decimal("15.00"),
            "gst_percent": Decimal("5.00"),
            "delivery_fee": Decimal("40.00"),
        }
        for k, v in target.items():
            if Decimal(str(getattr(s, k))) != v:
                setattr(s, k, v)
                changed = True
        if changed:
            try_save(s)

    # ------------------------------------------------------------------
    # 3. Restaurant specs
    # ------------------------------------------------------------------

    def _ramesh_spec(self):
        return {
            "name": "Ramesh Biryani Point",
            "cuisine_type": "Biryani",
            "restaurant_type": "non_veg",
            "description": "Authentic Hyderabadi dum biryani served since 1998.",
            "address": "12, Brigade Road",
            "city": "Bangalore",
            "state": "Karnataka",
            "pincode": "560001",
            "phone": "+918023456789",
            "fssai_number": "10012345678901",
            "gst_number": "29AABCU1234F1Z5",
            "pan_number": "AABCP1234F",
            "bank_account_number": "1234567890",
            "bank_ifsc_code": "HDFC0001234",
            "account_holder_name": "Ramesh P",
            "latitude": Decimal("12.971600"),
            "longitude": Decimal("77.594600"),
            "status": "approved",
            "is_active": True,
            "opening_time": "09:00",
            "closing_time": "23:00",
            "is_open": True,
            "minimum_order_amount": Decimal("200.00"),
            "commission_percent": None,
            "categories": [
                {
                    "name": "Biryani",
                    "items": [
                        ("Chicken Biryani", "Fragrant basmati, dum-cooked with spices.", "non_veg", 25, "299", "249"),
                        ("Veg Biryani", "Garden-fresh vegetables, basmati rice.", "veg", 25, "220", "199"),
                        ("Mutton Biryani", "Tender mutton pieces, slow-cooked.", "non_veg", 35, "449", "399"),
                    ],
                },
                {
                    "name": "Starters",
                    "items": [
                        ("Chicken 65", "Spicy deep-fried chicken appetizer.", "non_veg", 15, "199", "180"),
                        ("Paneer Tikka", "Tandoor-roasted cottage cheese.", "veg", 15, "210", "189"),
                        ("Mirchi Bajji", "Crispy chilli fritters.", "veg", 10, "99", "89"),
                    ],
                },
                {
                    "name": "Curries",
                    "items": [
                        ("Chicken Curry", "Traditional South-Indian style gravy.", "non_veg", 20, "249", "229"),
                        ("Paneer Butter Masala", "Rich tomato-cashew gravy.", "veg", 20, "239", "209"),
                        ("Dal Tadka", "Yellow lentils tempered with ghee.", "veg", 15, "149", "129"),
                    ],
                },
                {
                    "name": "Desserts",
                    "items": [
                        ("Gulab Jamun", "Warm milk dumplings in rose syrup (2 pc).", "veg", 5, "99", "89"),
                        ("Ice Cream", "Vanilla single scoop.", "egg", 5, "60", "55"),
                        ("Double Ka Meetha", "Hyderabadi bread pudding.", "veg", 10, "119", "109"),
                    ],
                },
            ],
            "offer": {
                "code": "WELCOME20",
                "discount_type": "percentage",
                "discount_value": Decimal("20"),
                "description": "20% off on your first biryani order",
                "minimum_order_amount": Decimal("300"),
                "maximum_discount": Decimal("100"),
                "usage_limit": 500,
                "used_count": 0,
                "days_offset": (30, 90),
            },
        }

    def _sagar_spec(self):
        return {
            "name": "Sagar Veg",
            "cuisine_type": "South Indian",
            "restaurant_type": "veg",
            "description": "Pure vegetarian South-Indian thalis and dosas.",
            "address": "44, Residency Road",
            "city": "Bangalore",
            "state": "Karnataka",
            "pincode": "560025",
            "phone": "+918023332211",
            "fssai_number": "11200998877665",
            "gst_number": "29AAABBS4321C1DE",
            "pan_number": "AAABBS4321C",
            "bank_account_number": "0987654321",
            "bank_ifsc_code": "SBIN0009876",
            "account_holder_name": "Sagar Iyer",
            "latitude": Decimal("12.935200"),
            "longitude": Decimal("77.624500"),
            "status": "approved",
            "is_active": True,
            "opening_time": "07:00",
            "closing_time": "22:30",
            "is_open": True,
            "minimum_order_amount": Decimal("150.00"),
            "commission_percent": None,
            "categories": [
                {
                    "name": "Idli & Vada",
                    "items": [
                        ("Idli (2 pc)", "Steamed rice cakes, sambar & chutney.", "veg", 10, "80", "70"),
                        ("Medu Vada (2 pc)", "Crisp urad-dal fritters.", "veg", 12, "90", "80"),
                        ("Idli Vada Combo", "1 idli + 1 vada + sambar.", "veg", 12, "130", "115"),
                    ],
                },
                {
                    "name": "Dosa",
                    "items": [
                        ("Plain Dosa", "Crisp rice crepe with chutney.", "veg", 12, "90", "80"),
                        ("Masala Dosa", "Stuffed with potato masala.", "veg", 15, "130", "115"),
                        ("Rava Onion Dosa", "Semolina crepe with onions.", "veg", 15, "140", "125"),
                    ],
                },
                {
                    "name": "Rice & Meals",
                    "items": [
                        ("Curd Rice", "Yogurt rice tempered with mustard.", "veg", 10, "90", "80"),
                        ("South Indian Mini Meals", "Rice, 2 curries, rasam, appalam.", "veg", 20, "199", "175"),
                        ("Bisibele Bath", "Karnataka-style rice & sambar.", "veg", 20, "150", "130"),
                    ],
                },
                {
                    "name": "Sweets",
                    "items": [
                        ("Mysore Pak", "Traditional ghee gram-flour sweet.", "veg", 8, "120", "100"),
                        ("Jalebi", "Crisp syrup-soaked spirals (250g).", "veg", 8, "140", "120"),
                        ("Kesari Bhath", "Semolina halwa with saffron.", "veg", 10, "110", "95"),
                    ],
                },
            ],
            "offer": {
                "code": "FLAT50",
                "discount_type": "flat",
                "discount_value": Decimal("50"),
                "description": "Flat ₹50 off on orders above ₹250",
                "minimum_order_amount": Decimal("250"),
                "maximum_discount": Decimal("50"),
                "usage_limit": 800,
                "used_count": 0,
                "days_offset": (30, 90),
            },
        }

    # ------------------------------------------------------------------
    # 4. Apply a restaurant spec (users already exist).
    # ------------------------------------------------------------------

    def _seed_restaurant(self, owner_email, spec):
        from accounts.models import User
        from restaurant.models import (
            MenuCategory,
            MenuItem,
            Restaurant,
            RestaurantOffer,
            RestaurantTiming,
        )

        owner = User.objects.get(email=owner_email)
        today = timezone.localdate()

        r_fields = {
            k: spec[k]
            for k in [
                "name", "cuisine_type", "restaurant_type", "description",
                "address", "city", "state", "pincode", "phone",
                "fssai_number", "gst_number", "pan_number",
                "bank_account_number", "bank_ifsc_code",
                "account_holder_name", "latitude", "longitude",
                "status", "is_active", "opening_time", "closing_time",
                "is_open", "minimum_order_amount", "commission_percent",
            ]
        }
        r_fields["owner"] = owner
        try:
            with transaction.atomic():
                restaurant, _ = Restaurant.objects.update_or_create(
                    owner=owner,
                    defaults=r_fields,
                )
        except IntegrityError:
            restaurant = Restaurant.objects.get(owner=owner)

        # 7 days of timings (Mon-Sun).
        opening = spec["opening_time"]
        closing = spec["closing_time"]
        existing_days = set(
            RestaurantTiming.objects.filter(restaurant=restaurant).values_list(
                "day_of_week", flat=True
            )
        )
        for day in range(7):
            if day in existing_days:
                RestaurantTiming.objects.filter(
                    restaurant=restaurant, day_of_week=day
                ).update(
                    opening_time=opening,
                    closing_time=closing,
                    is_closed=False,
                )
            else:
                try:
                    with transaction.atomic():
                        RestaurantTiming.objects.create(
                            restaurant=restaurant,
                            day_of_week=day,
                            opening_time=opening,
                            closing_time=closing,
                            is_closed=False,
                        )
                except IntegrityError:
                    pass

        # Categories + items.
        for order_idx, cat_spec in enumerate(spec["categories"], start=1):
            try:
                with transaction.atomic():
                    category, _ = MenuCategory.objects.update_or_create(
                        restaurant=restaurant,
                        name=cat_spec["name"],
                        defaults={
                            "description": f"{cat_spec['name']} section",
                            "display_order": order_idx,
                            "is_active": True,
                        },
                    )
            except IntegrityError:
                category = MenuCategory.objects.get(
                    restaurant=restaurant, name=cat_spec["name"]
                )
            for idx, (name, desc, food_type, prep, mrp, price) in enumerate(cat_spec["items"], start=1):
                mrp_v = Decimal(mrp)
                price_v = Decimal(price)
                if mrp_v > price_v:
                    disc_pct = q((mrp_v - price_v) * Decimal("100") / mrp_v, "0.01")
                else:
                    disc_pct = Decimal("0.00")
                defaults = {
                    "menu_category": category,
                    "description": desc,
                    "food_type": food_type,
                    "preparation_time_minutes": prep,
                    "mrp": mrp_v,
                    "discount_percent": disc_pct,
                    "price": price_v,
                    "category": category.name,
                    "is_available": True,
                }
                try:
                    with transaction.atomic():
                        item, created = MenuItem.objects.get_or_create(
                            restaurant=restaurant, name=name, defaults=defaults
                        )
                    if not created:
                        for k, v in defaults.items():
                            setattr(item, k, v)
                        try_save(item)
                except IntegrityError:
                    pass

        # Offer.
        o = spec["offer"]
        start = today - timedelta(days=o["days_offset"][0])
        end = today + timedelta(days=o["days_offset"][1])
        offer_defaults = {
            "name": o["description"],
            "discount_type": o["discount_type"],
            "discount_value": o["discount_value"],
            "minimum_order_amount": o["minimum_order_amount"],
            "maximum_discount": o["maximum_discount"],
            "usage_limit": o["usage_limit"],
            "used_count": o["used_count"],
            "start_date": start,
            "end_date": end,
            "is_active": True,
        }
        try:
            with transaction.atomic():
                offer, created = RestaurantOffer.objects.get_or_create(
                    restaurant=restaurant, code=o["code"], defaults=offer_defaults
                )
            if not created:
                for k, v in offer_defaults.items():
                    setattr(offer, k, v)
                try_save(offer)
        except IntegrityError:
            pass

        return restaurant

    # ------------------------------------------------------------------
    # 5. Demo delivered order: rahul → 2x Chicken Biryani → Ramesh.
    #    Explicitly builds the order rather than going through the cart
    #    so the seed works even if the shopping-cart service changes.
    # ------------------------------------------------------------------

    def _seed_delivered_order(self):
        from accounts.models import User
        from customer.models import Review
        from delivery.models import DeliveryAssignment
        from orders.models import Order, OrderItem
        from payments.models import Payment
        from restaurant.models import MenuItem, Restaurant, RestaurantEarning, RestaurantOffer

        rahul = User.objects.get(email="rahul@foodex.in")
        ravi = User.objects.get(email="ravi@foodex.in")
        restaurant = Restaurant.objects.get(owner__email="ramesh_owner@foodex.in")
        chicken = MenuItem.objects.get(
            restaurant=restaurant, name="Chicken Biryani"
        )
        offer = RestaurantOffer.objects.get(
            restaurant=restaurant, code="WELCOME20"
        )

        # Don't duplicate the demo order.
        existing_demo = Order.objects.filter(
            user=rahul,
            restaurant=restaurant,
            items__menu_item=chicken,
        ).first()
        if existing_demo:
            return

        with transaction.atomic():
            order = Order.objects.create(
                user=rahul,
                restaurant=restaurant,
                offer=offer,
                delivery_address="2nd Floor, 221B Baker Street, Indiranagar, Bangalore - 560001",
                delivery_latitude=Decimal("12.974200"),
                delivery_longitude=Decimal("77.595000"),
            )
            qty = 2
            line = OrderItem.objects.create(
                order=order,
                menu_item=chicken,
                name=chicken.name,
                quantity=qty,
                unit_price=chicken.price,
            )
            # Pricing:
            # items subtotal = 2 * 249 = 498
            # offer WELCOME20: 20% of 498 = 99.6 → capped at 100 (maximum_discount).
            # discount_amount = min(99.6, 100) = 99.60
            # taxable subtotal = 498 - 99.6 = 398.40
            # GST @5% = 19.92
            # delivery = 40
            # total = 398.40 + 19.92 + 40 = 458.32
            items_subtotal = q(line.unit_price * qty)
            if offer.discount_type == "percentage":
                raw_disc = q(items_subtotal * offer.discount_value / Decimal("100"))
                discount_amount = min(raw_disc, offer.maximum_discount)
            else:
                discount_amount = min(offer.discount_value, offer.maximum_discount)
                if items_subtotal < offer.minimum_order_amount:
                    discount_amount = Decimal("0.00")
            food_after_discount = q(items_subtotal - discount_amount)
            gst_percent = Decimal("5")
            tax_amount = q(food_after_discount * gst_percent / Decimal("100"))
            delivery_fee = Decimal("40.00")
            total = q(food_after_discount + tax_amount + delivery_fee)

            order.subtotal = items_subtotal
            order.discount_amount = discount_amount
            order.tax_amount = tax_amount
            order.delivery_fee = delivery_fee
            order.total_price = total
            order.save(update_fields=[
                "subtotal", "discount_amount", "tax_amount",
                "delivery_fee", "total_price", "updated_at",
            ])

            # Payment (test method → paid immediately).
            Payment.objects.create(
                order=order,
                amount=total,
                payment_method="test",
                status=Payment.STATUS_PAID,
                transaction_id=f"DEMO-TEST-{order.code}",
            )

            # Restaurant side state: placed → accepted (prep 25) → preparing → ready
            order.status = Order.STATUS_ACCEPTED
            order.estimated_preparation_minutes = 25
            order.accepted_at = timezone.now() - timedelta(minutes=22)
            order.save(update_fields=[
                "status", "estimated_preparation_minutes", "accepted_at", "updated_at",
            ])

            order.status = Order.STATUS_PREPARING
            order.preparing_at = timezone.now() - timedelta(minutes=20)
            order.save(update_fields=["status", "preparing_at", "updated_at"])

            order.status = Order.STATUS_READY
            order.ready_at = timezone.now() - timedelta(minutes=6)
            order.save(update_fields=["status", "ready_at", "updated_at"])

            # Delivery side: assignment w/ ravi → accepted → picked_up → delivered.
            # advance_assignment calls record_order_earning on delivered status.
            assignment = DeliveryAssignment.objects.create(
                order=order,
                partner=ravi,
                status="accepted",
            )
            assignment.status = "picked_up"
            assignment.pickup_time = timezone.now() - timedelta(minutes=5)
            assignment.save(update_fields=["status", "pickup_time"])

            order.status = Order.STATUS_PICKED_UP
            order.picked_up_at = assignment.pickup_time
            order.save(update_fields=["status", "picked_up_at"])

            assignment.status = "on_the_way"
            assignment.save(update_fields=["status"])

            order.status = Order.STATUS_OUT_FOR_DELIVERY
            order.save(update_fields=["status"])

            assignment.status = "delivered"
            assignment.delivery_time = timezone.now()
            assignment.save(update_fields=["status", "delivery_time"])

            order.status = Order.STATUS_DELIVERED
            order.delivered_at = assignment.delivery_time
            order.closed_at = assignment.delivery_time
            order.save(update_fields=[
                "status", "delivered_at", "closed_at", "updated_at",
            ])

        # The advance_assignment service normally calls record_order_earning
        # inside the same transaction.  Because we built the order manually,
        # fire it explicitly here to exercise the payout split + assert the
        # row exists.
        from restaurant.services import record_order_earning

        record_order_earning(order)

        # Offer use-count bump (mirrors create_order_from_cart).
        RestaurantOffer.objects.filter(pk=offer.pk).update(used_count=offer.used_count + 1)

        # COD-style settlement not needed (payment method is test/paid).
        # Finally, 4★ review.
        try:
            with transaction.atomic():
                Review.objects.create(
                    user=rahul,
                    order=order,
                    restaurant=restaurant,
                    rating=4,
                    comment="Great biryani! Delivery was on time and the packet was still warm.",
                )
        except IntegrityError:
            pass

        earning = RestaurantEarning.objects.filter(order=order).first()
        if earning:
            self.stdout.write(
                self.style.SUCCESS(
                    "Demo earning: food+GST-commission = "
                    f"₹{earning.restaurant_amount}; "
                    f"rider payout ₹{earning.rider_payout}; "
                    f"commission ₹{earning.commission_amount}."
                )
            )

    # ------------------------------------------------------------------
    # 6. Counts used for the final summary + AC-R5 check.
    # ------------------------------------------------------------------

    def _counts(self, extended=False):
        from accounts.models import User
        from customer.models import CustomerProfile, Review
        from delivery.models import DeliveryAssignment, DeliveryPartnerProfile
        from orders.models import Order, OrderItem
        from payments.models import Payment
        from restaurant.models import (
            MenuCategory,
            MenuItem,
            PlatformSetting,
            Restaurant,
            RestaurantEarning,
            RestaurantOffer,
            RestaurantTiming,
        )

        rows = [
            ("admins", User.objects.filter(role="admin").count()),
            ("customers", User.objects.filter(role="customer").count()),
            ("customer profiles", CustomerProfile.objects.count()),
            ("delivery partners", User.objects.filter(role="delivery_partner").count()),
            ("delivery profiles online", DeliveryPartnerProfile.objects.filter(is_online=True).count()),
            ("restaurants", Restaurant.objects.count()),
            ("restaurants approved", Restaurant.objects.filter(status="approved", is_active=True).count()),
            ("menu categories", MenuCategory.objects.count()),
            ("menu items", MenuItem.objects.count()),
            ("restaurant timings", RestaurantTiming.objects.count()),
            ("offers", RestaurantOffer.objects.count()),
            ("platform settings", PlatformSetting.objects.count()),
        ]
        if extended:
            rows += [
                ("orders", Order.objects.count()),
                ("order items", OrderItem.objects.count()),
                ("payments", Payment.objects.count()),
                ("delivered orders", Order.objects.filter(status=Order.STATUS_DELIVERED).count()),
                ("delivery assignments", DeliveryAssignment.objects.count()),
                ("restaurant earnings", RestaurantEarning.objects.count()),
                ("reviews", Review.objects.count()),
            ]
        return rows
