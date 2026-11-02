from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_center_view(request):
    notifications = Notification.objects.filter(user=request.user)[:50]
    return render(
        request,
        "notifications/list.html",
        {"notifications": notifications},
    )


@login_required
@require_POST
def mark_notification_read_view(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        user=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect("notification_center")