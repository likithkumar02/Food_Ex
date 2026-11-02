from django.urls import path

from .views import mark_notification_read_view, notification_center_view


urlpatterns = [
    path("", notification_center_view, name="notification_center"),
    path("<int:notification_id>/read/", mark_notification_read_view, name="mark_notification_read"),
]