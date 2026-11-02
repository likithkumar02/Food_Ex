from .models import Notification


def notify_user(user, category, title, message, link=""):
    return Notification.objects.create(
        user=user,
        category=category,
        title=title,
        message=message,
        link=link,
    )