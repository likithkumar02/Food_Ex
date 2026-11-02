from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject

User = get_user_model()

DELIVERY_PREFIXES = (
    "/delivery/",
    "/dashboard/delivery/",
    "/api/delivery/",
    "/location/delivery/",
)

CUSTOMER_PREFIXES = (
    "/customer/",
    "/dashboard/customer/",
    "/orders/",
    "/payments/",
    "/checkout/",
    "/restaurants/",
    "/profile/",
    "/location/customer/",
    "/api/customer/",
    "/api/orders/",
    "/api/payments/",
)

RESTAURANT_PREFIXES = (
    "/restaurant/",
    "/restaurant-partner/",
    "/dashboard/restaurant/",
    "/orders/restaurant/",
    "/api/restaurant/",
    "/api/restaurants/",
    "/location/restaurant/",
)


def _resolve_role_user(request, role):
    cache_attr = f"_cached_{role}_user"
    if hasattr(request, cache_attr):
        return getattr(request, cache_attr)

    session = getattr(request, "session", None)
    user = None
    if session is not None:
        user_id = session.get(f"_{role}_user_id")
        if user_id:
            try:
                user = User.objects.filter(pk=user_id, role=role).first()
            except Exception:
                user = None

    if user is None:
        std_user = getattr(request, "_standard_user", None)
        if (
            std_user is not None
            and std_user.is_authenticated
            and getattr(std_user, "role", None) == role
        ):
            user = std_user

    resolved = user if user is not None else AnonymousUser()
    setattr(request, cache_attr, resolved)
    return resolved


class RoleSessionMiddleware:
    """
    Provides independent session management for Customers and Delivery Partners.
    Allows both accounts to stay logged in simultaneously in different tabs/portals
    without conflicting or overwriting each other.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Cache standard user from AuthenticationMiddleware
        request._standard_user = getattr(request, "user", AnonymousUser())

        # Attach role-specific users
        request.customer_user = SimpleLazyObject(lambda: _resolve_role_user(request, "customer"))
        request.delivery_user = SimpleLazyObject(lambda: _resolve_role_user(request, "delivery_partner"))
        request.restaurant_user = SimpleLazyObject(lambda: _resolve_role_user(request, "restaurant_owner"))

        path = request.path

        # Context-aware request.user assignment
        if any(path.startswith(prefix) for prefix in DELIVERY_PREFIXES):
            if request.delivery_user.is_authenticated:
                request.user = request.delivery_user
            else:
                request.user = AnonymousUser()

        elif any(path.startswith(prefix) for prefix in RESTAURANT_PREFIXES):
            if request.restaurant_user.is_authenticated:
                request.user = request.restaurant_user
            elif (request.customer_user.is_authenticated or request.delivery_user.is_authenticated) and not request.restaurant_user.is_authenticated:
                request.user = AnonymousUser()

        elif any(path.startswith(prefix) for prefix in CUSTOMER_PREFIXES) or path == "/":
            if request.customer_user.is_authenticated:
                request.user = request.customer_user
            elif request.delivery_user.is_authenticated and not request.customer_user.is_authenticated:
                # Delivery partner visiting customer storefront is an anonymous guest on customer site
                request.user = AnonymousUser()
            # Otherwise keep standard user if present

        elif path.startswith("/notifications/"):
            portal_param = request.GET.get("portal", "")
            referer = request.META.get("HTTP_REFERER", "")
            if portal_param == "delivery" or "/delivery/" in referer:
                if request.delivery_user.is_authenticated:
                    request.user = request.delivery_user
            elif request.customer_user.is_authenticated:
                request.user = request.customer_user
            elif request.delivery_user.is_authenticated:
                request.user = request.delivery_user

        else:
            # Generic pages like /settings/, /about/, etc.
            portal_param = request.GET.get("portal", "")
            referer = request.META.get("HTTP_REFERER", "")
            standard_user = request._standard_user
            if (
                portal_param == "delivery" or "/delivery/" in referer
            ) and request.delivery_user.is_authenticated:
                request.user = request.delivery_user
            elif (
                standard_user.is_authenticated
                and getattr(standard_user, "role", None) == "customer"
                and request.customer_user.is_authenticated
            ):
                request.user = request.customer_user
            elif (
                standard_user.is_authenticated
                and getattr(standard_user, "role", None) == "delivery_partner"
                and request.delivery_user.is_authenticated
            ):
                request.user = request.delivery_user
            elif (
                standard_user.is_authenticated
                and getattr(standard_user, "role", None) == "restaurant_owner"
                and request.restaurant_user.is_authenticated
            ):
                request.user = request.restaurant_user
            elif request.customer_user.is_authenticated:
                request.user = request.customer_user
            elif request.delivery_user.is_authenticated:
                request.user = request.delivery_user
            elif request.restaurant_user.is_authenticated:
                request.user = request.restaurant_user

        return self.get_response(request)
