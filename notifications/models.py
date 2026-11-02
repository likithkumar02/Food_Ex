from django.conf import settings
from django.db import models


class Notification(models.Model):
    CATEGORY_CHOICES = [
        ("order", "Order"),
        ("payment", "Payment"),
        ("delivery", "Delivery"),
        ("account", "Account"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=500)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.title} for {self.user.username}"