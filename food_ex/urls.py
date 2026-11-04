from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from customer.views import customer_profile_view

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("food_Ex/", RedirectView.as_view(url="/", permanent=False)),
    path("food-ex/", RedirectView.as_view(url="/", permanent=False)),
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path(
        "accounts/",
        include(("accounts.urls", "accounts"), namespace="legacy_accounts"),
    ),
    path("api/auth/", include("accounts.api_urls")),
    path("api/admin/", include("accounts.admin_api_urls")),
    path("api/restaurants/", include("restaurant.api_urls")),
    path("api/restaurant/", include("restaurant.partner_compat_urls")),
    path("api/customer/", include("customer.api_urls")),
    path("api/", include("orders.api_urls")),
    path("api/payments/", include("payments.api_urls")),
    path("api/delivery/", include("delivery.api_urls")),
    path("api/notifications/", include("notifications.api_urls")),
    path("api/location/", include("location.api_urls")),
    path("notifications/", include("notifications.urls")),
    path("profile/", customer_profile_view, name="profile"),
    path("customer/", include("customer.urls")),
    path("orders/", include("orders.urls")),
    path("payments/", include("payments.urls")),
    path("delivery/", include("delivery.urls")),
    path("location/", include("location.urls")),
    path("", include("restaurant.urls")),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
