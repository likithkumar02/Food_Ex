from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField("email address", unique=True)

    ROLE_CHOICES = [
        ("customer", "Customer"),
        ("restaurant_owner", "Restaurant Owner"),
        ("delivery_partner", "Delivery Partner"),
        ("admin", "Admin"),
    ]

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default="customer",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
