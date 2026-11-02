from django.urls import path
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

from .views import (
    admin_dashboard_view,
    admin_delete_user_view,
    api_forgot_password_view,
    api_login_view,
    api_password_change_view,
    api_profile_view,
    api_signup_view,
    customer_dashboard_view,
    customer_logout_view,
    dashboard_view,
    delete_account_view,
    delivery_dashboard_view,
    delivery_logout_view,
    forgot_password_view,
    login_view,
    logout_view,
    password_change_view,
    customer_portal_view,
    delivery_portal_view,
    portal_login_view,
    portal_register_view,
    register_view,
    restaurant_dashboard_view,
    restaurant_portal_view,
    settings_view,
)


urlpatterns = [
    path("customer/", customer_portal_view, name="customer_portal"),
    path(
        "restaurant/",
        RedirectView.as_view(
            pattern_name="restaurant_portal",
            permanent=False,
            query_string=True,
        ),
    ),
    path("restaurant-partner/", restaurant_portal_view, name="restaurant_portal"),
    path("delivery/", delivery_portal_view, name="delivery_portal"),
    path("customer/login/", portal_login_view, {"role": "customer"}, name="customer_login"),
    path("customer/register/", portal_register_view, {"role": "customer"}, name="customer_register"),
    path("customer/logout/", customer_logout_view, name="customer_logout"),
    path("restaurant/login/", portal_login_view, {"role": "restaurant_owner"}, name="restaurant_login"),
    path("restaurant/register/", portal_register_view, {"role": "restaurant_owner"}, name="restaurant_register"),
    path("delivery/login/", portal_login_view, {"role": "delivery_partner"}, name="delivery_login"),
    path("delivery/register/", portal_register_view, {"role": "delivery_partner"}, name="delivery_register"),
    path("delivery/logout/", delivery_logout_view, name="delivery_logout"),
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("password-change/", password_change_view, name="password_change"),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("settings/", settings_view, name="settings"),
    path("delete-account/", delete_account_view, name="delete_account"),
    path("dashboard/admin/users/<int:user_id>/delete/", admin_delete_user_view, name="admin_delete_user"),
    path("logout/", logout_view, name="logout"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("dashboard/customer/", customer_dashboard_view, name="customer_dashboard"),
    path("dashboard/restaurant/", restaurant_dashboard_view, name="restaurant_dashboard"),
    path("dashboard/delivery/", delivery_dashboard_view, name="delivery_dashboard"),
    path("dashboard/admin/", admin_dashboard_view, name="admin_dashboard"),
    path("api/signup/", api_signup_view, name="api_signup"),
    path("api/login/", api_login_view, name="api_login"),
    path("api/forgot-password/", api_forgot_password_view, name="api_forgot_password"),
    path("api/password/change/", api_password_change_view, name="api_password_change"),
    path("api/profile/", api_profile_view, name="api_profile"),
]
