from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


def serialize_notification(notification):
    return {
        "id": notification.pk,
        "category": notification.category,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "is_read": notification.is_read,
        "created_at": notification.created_at,
    }


class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)
        return Response({
            "unread_count": notifications.filter(is_read=False).count(),
            "results": [serialize_notification(item) for item in notifications[:50]],
        })


class NotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            pk=notification_id,
            user=request.user,
        )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(serialize_notification(notification))