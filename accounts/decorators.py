from functools import wraps

from django.contrib.auth.decorators import user_passes_test


def role_required(*roles):
    def decorator(view_func):
        login_paths = {
            "customer": "/customer/login/",
            "restaurant_owner": "/restaurant/login/",
            "delivery_partner": "/delivery/login/",
        }
        login_url = next(
            (login_paths[role] for role in roles if role in login_paths),
            "/login/",
        )
        actual_decorator = user_passes_test(
            lambda user: user.is_authenticated and user.role in roles,
            login_url=login_url,
        )
        return actual_decorator(view_func)

    return decorator
