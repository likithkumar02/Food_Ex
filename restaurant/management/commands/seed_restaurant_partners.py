import csv
import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from restaurant.models import MenuItem, Restaurant


PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_"

RESTAURANT_SPECS = [
    {
        "name": "Dum House Biryani",
        "cuisine_type": "Biryani",
        "city": "Visakhapatnam",
        "state": "Andhra Pradesh",
        "area": "Beach Road",
        "food": [
            ("Chicken Dum Biryani", "Biryani", "279.00", "non_veg"),
            ("Hyderabadi Special Biryani", "Biryani", "329.00", "non_veg"),
            ("Chicken 65 Biryani", "Biryani", "309.00", "non_veg"),
            ("Mutton Dum Biryani", "Biryani", "379.00", "non_veg"),
            ("Paneer Tikka Biryani", "Biryani", "259.00", "veg"),
            ("Egg Biryani", "Biryani", "229.00", "egg"),
            ("Andhra Chicken Fry Biryani", "Biryani", "319.00", "non_veg"),
            ("Family Pack Chicken Biryani", "Biryani", "699.00", "non_veg"),
            ("Mirchi Ka Salan", "Sides", "89.00", "veg"),
            ("Double Ka Meetha", "Dessert", "99.00", "veg"),
        ],
    },
    {
        "name": "Scoop & Swirl Creamery",
        "cuisine_type": "Desserts",
        "city": "Bengaluru",
        "state": "Karnataka",
        "area": "Indiranagar",
        "food": [
            ("Madagascar Vanilla Scoop", "Ice Cream", "89.00", "veg"),
            ("Belgian Chocolate Scoop", "Ice Cream", "99.00", "veg"),
            ("Mango Sorbet", "Sorbet", "109.00", "veg"),
            ("Strawberry Cheesecake Sundae", "Sundaes", "189.00", "veg"),
            ("Brownie Fudge Sundae", "Sundaes", "199.00", "veg"),
            ("Salted Caramel Gelato", "Gelato", "129.00", "veg"),
            ("Pistachio Kulfi", "Kulfi", "119.00", "veg"),
            ("Tender Coconut Ice Cream", "Ice Cream", "119.00", "veg"),
            ("Chocolate Waffle", "Waffles", "179.00", "veg"),
            ("Cookie Dough Milkshake", "Shakes", "169.00", "veg"),
        ],
    },
    {
        "name": "Coastal Curry House",
        "cuisine_type": "South Indian",
        "city": "Hyderabad",
        "state": "Telangana",
        "area": "Jubilee Hills",
        "food": [
            ("Andhra Chicken Curry", "Chicken Curries", "269.00", "non_veg"),
            ("Butter Chicken Masala", "Chicken Curries", "289.00", "non_veg"),
            ("Gongura Chicken", "Chicken Curries", "299.00", "non_veg"),
            ("Pepper Chicken Curry", "Chicken Curries", "279.00", "non_veg"),
            ("Coastal Fish Pulusu", "Seafood Curries", "319.00", "non_veg"),
            ("Prawn Coconut Curry", "Seafood Curries", "349.00", "non_veg"),
            ("Paneer Butter Masala", "Vegetarian Curries", "239.00", "veg"),
            ("Mushroom Pepper Fry", "Vegetarian Curries", "219.00", "veg"),
            ("Steamed Basmati Rice", "Rice & Breads", "99.00", "veg"),
            ("Garlic Butter Naan", "Rice & Breads", "59.00", "veg"),
        ],
    },
    {
        "name": "Madras Tiffin Room",
        "cuisine_type": "South Indian",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "area": "Mylapore",
        "food": [
            ("Ghee Podi Idli", "Breakfast", "119.00", "veg"),
            ("Crispy Masala Dosa", "Dosa", "149.00", "veg"),
            ("Mysore Masala Dosa", "Dosa", "169.00", "veg"),
            ("Rava Onion Dosa", "Dosa", "159.00", "veg"),
            ("Medu Vada with Sambar", "Breakfast", "109.00", "veg"),
            ("Mini South Indian Meals", "Meals", "199.00", "veg"),
            ("Kara Kuzhambu Rice", "Rice", "179.00", "veg"),
            ("Curd Rice with Pickle", "Rice", "139.00", "veg"),
            ("Filter Coffee", "Drinks", "59.00", "veg"),
            ("Badam Halwa", "Dessert", "99.00", "veg"),
        ],
    },
    {
        "name": "Mumbai Street Kitchen",
        "cuisine_type": "Fast Food",
        "city": "Mumbai",
        "state": "Maharashtra",
        "area": "Bandra West",
        "food": [
            ("Classic Vada Pav", "Street Food", "59.00", "veg"),
            ("Cheese Masala Pav", "Street Food", "99.00", "veg"),
            ("Mumbai Pav Bhaji", "Street Food", "169.00", "veg"),
            ("Tawa Pulao", "Rice", "179.00", "veg"),
            ("Chicken Kathi Roll", "Rolls", "189.00", "non_veg"),
            ("Paneer Frankie", "Rolls", "159.00", "veg"),
            ("Crispy Chicken Popcorn", "Snacks", "199.00", "non_veg"),
            ("Bombay Grilled Sandwich", "Sandwiches", "149.00", "veg"),
            ("Masala Chai", "Drinks", "49.00", "veg"),
            ("Kulfi Falooda", "Dessert", "129.00", "veg"),
        ],
    },
    {
        "name": "Malabar Coast Kitchen",
        "cuisine_type": "Indian",
        "city": "Kochi",
        "state": "Kerala",
        "area": "Fort Kochi",
        "food": [
            ("Malabar Chicken Biryani", "Biryani", "289.00", "non_veg"),
            ("Kerala Fish Curry", "Seafood", "299.00", "non_veg"),
            ("Appam with Stew", "Kerala Specials", "199.00", "non_veg"),
            ("Beef Ularthiyathu", "Kerala Specials", "329.00", "non_veg"),
            ("Prawn Roast", "Seafood", "349.00", "non_veg"),
            ("Vegetable Ishtu", "Kerala Specials", "189.00", "veg"),
            ("Kerala Parotta (2 pc)", "Breads", "69.00", "veg"),
            ("Kappa and Meen Curry", "Kerala Specials", "279.00", "non_veg"),
            ("Puttu with Kadala Curry", "Breakfast", "159.00", "veg"),
            ("Palada Payasam", "Dessert", "99.00", "veg"),
        ],
    },
    {
        "name": "Ahmedabad Spice Trail",
        "cuisine_type": "Indian",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "area": "Navrangpura",
        "food": [
            ("Gujarati Unlimited Thali", "Thalis", "269.00", "veg"),
            ("Kathiyawadi Sev Tameta", "Gujarati Specials", "189.00", "veg"),
            ("Undhiyu with Puri", "Gujarati Specials", "229.00", "veg"),
            ("Dal Dhokli", "Gujarati Specials", "179.00", "veg"),
            ("Handvo Slice", "Snacks", "99.00", "veg"),
            ("Khaman Dhokla", "Snacks", "89.00", "veg"),
            ("Paneer Tikka Masala", "Curries", "249.00", "veg"),
            ("Masala Khichdi Kadhi", "Rice", "169.00", "veg"),
            ("Jalebi and Fafda", "Sweets", "119.00", "veg"),
            ("Mango Shrikhand", "Dessert", "109.00", "veg"),
        ],
    },
    {
        "name": "Pink City Tandoor",
        "cuisine_type": "North Indian",
        "city": "Jaipur",
        "state": "Rajasthan",
        "area": "C-Scheme",
        "food": [
            ("Laal Maas", "Rajasthani Specials", "349.00", "non_veg"),
            ("Dal Baati Churma", "Rajasthani Specials", "279.00", "veg"),
            ("Ker Sangri", "Rajasthani Specials", "229.00", "veg"),
            ("Chicken Tikka", "Tandoor", "269.00", "non_veg"),
            ("Paneer Tikka", "Tandoor", "239.00", "veg"),
            ("Tandoori Chicken Half", "Tandoor", "329.00", "non_veg"),
            ("Garlic Naan", "Breads", "69.00", "veg"),
            ("Mutton Seekh Kebab", "Tandoor", "319.00", "non_veg"),
            ("Gatte ki Sabzi", "Curries", "199.00", "veg"),
            ("Ghewar", "Dessert", "149.00", "veg"),
        ],
    },
    {
        "name": "Capital Wok & Grill",
        "cuisine_type": "Chinese",
        "city": "New Delhi",
        "state": "Delhi",
        "area": "Connaught Place",
        "food": [
            ("Chilli Chicken", "Indo-Chinese", "249.00", "non_veg"),
            ("Veg Hakka Noodles", "Noodles", "189.00", "veg"),
            ("Chicken Schezwan Noodles", "Noodles", "229.00", "non_veg"),
            ("Crispy Honey Chilli Potato", "Starters", "179.00", "veg"),
            ("Dragon Paneer", "Starters", "219.00", "veg"),
            ("Chicken Manchurian", "Indo-Chinese", "259.00", "non_veg"),
            ("Schezwan Fried Rice", "Rice", "199.00", "veg"),
            ("Chicken Momos (8 pc)", "Momos", "199.00", "non_veg"),
            ("Veg Spring Rolls", "Starters", "169.00", "veg"),
            ("Choco Lava Cake", "Dessert", "109.00", "veg"),
        ],
    },
    {
        "name": "Kolkata Sweet & Savoury",
        "cuisine_type": "Indian",
        "city": "Kolkata",
        "state": "West Bengal",
        "area": "Park Street",
        "food": [
            ("Kolkata Chicken Biryani", "Biryani", "279.00", "non_veg"),
            ("Kosha Mangsho", "Bengali Specials", "329.00", "non_veg"),
            ("Shorshe Ilish", "Seafood", "399.00", "non_veg"),
            ("Chicken Chaap", "Bengali Specials", "299.00", "non_veg"),
            ("Aloo Posto with Rice", "Bengali Specials", "199.00", "veg"),
            ("Kathi Roll Chicken", "Rolls", "189.00", "non_veg"),
            ("Fish Fry", "Starters", "229.00", "non_veg"),
            ("Radhaballavi with Aloor Dum", "Breakfast", "169.00", "veg"),
            ("Mishti Doi", "Dessert", "89.00", "veg"),
            ("Nolen Gur Rosogolla", "Sweets", "99.00", "veg"),
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Create ten synthetic restaurant-partner demo accounts with ten menu "
        "items each, and save generated passwords to a local credentials file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--credentials-file",
            default=str(settings.BASE_DIR / ".restaurant_partner_demo_credentials.csv"),
            help="Local CSV path for generated credentials (default: Git-ignored file in project root).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        credentials_path = str(options["credentials_file"])
        credentials = []

        with transaction.atomic():
            for index, spec in enumerate(RESTAURANT_SPECS, start=1):
                username = f"foodex_partner_{index:02d}"
                email = f"{username}@example.test"
                password = "".join(
                    secrets.choice(PASSWORD_ALPHABET) for _ in range(24)
                )
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "first_name": spec["name"].split()[0],
                        "last_name": "Partner",
                        "role": "restaurant_owner",
                        "is_active": True,
                    },
                )
                if user.role != "restaurant_owner":
                    raise CommandError(
                        f"Cannot seed {username}: that username belongs to a non-partner account."
                    )
                if user.email != email:
                    raise CommandError(
                        f"Cannot seed {username}: the account already uses another email address."
                    )
                user.first_name = spec["name"].split()[0]
                user.last_name = "Partner"
                user.is_active = True
                user.set_password(password)
                user.save(update_fields=[
                    "password", "first_name", "last_name", "is_active",
                ])

                restaurant = Restaurant.objects.filter(owner=user).first()
                if restaurant and restaurant.name != spec["name"]:
                    raise CommandError(
                        f"Cannot seed {username}: the partner already owns a different restaurant."
                    )
                restaurant, _ = Restaurant.objects.update_or_create(
                    owner=user,
                    defaults={
                        "name": spec["name"],
                        "cuisine_type": spec["cuisine_type"],
                        "restaurant_type": "both",
                        "description": (
                            f"Demo menu featuring {spec['cuisine_type'].lower()} "
                            f"favorites in {spec['city']}."
                        ),
                        "address": f"{spec['area']}, {spec['city']}",
                        "area": spec["area"],
                        "city": spec["city"],
                        "state": spec["state"],
                        "phone": f"+911100000{index:03d}",
                        "status": "approved",
                        "is_active": True,
                    },
                )
                for name, category, price, food_type in spec["food"]:
                    MenuItem.objects.update_or_create(
                        restaurant=restaurant,
                        name=name,
                        defaults={
                            "category": category,
                            "description": f"Freshly prepared {name.lower()}, made to order.",
                            "price": price,
                            "food_type": food_type,
                            "is_available": True,
                        },
                    )

                credentials.append({
                    "restaurant": restaurant.name,
                    "username": username,
                    "email": email,
                    "password": password,
                    "state": spec["state"],
                })

        try:
            with open(credentials_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["restaurant", "username", "email", "password", "state"],
                )
                writer.writeheader()
                writer.writerows(credentials)
        except OSError as error:
            raise CommandError(
                f"Demo accounts were created, but credentials could not be written "
                f"to {credentials_path}: {error}"
            ) from error

        self.stdout.write(self.style.SUCCESS(
            "Created 10 demo restaurant accounts and 100 menu items."
        ))
        self.stdout.write(f"Credentials saved locally to: {credentials_path}")
