from django.urls import path

from .api_views import NotificationListAPIView, NotificationReadAPIView


urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="api_notifications"),
    path("<int:notification_id>/read/", NotificationReadAPIView.as_view(), name="api_notification_read"),
]