from django.urls import path

from .views import (
    assign_delivery_view,
    accept_delivery_view,
    delivery_dashboard_view,
    delivery_detail_view,
    delivery_availability_view,
    reject_delivery_view,
    update_delivery_status_view,
)


urlpatterns = [
    path("dashboard/", delivery_dashboard_view, name="delivery_dashboard"),
    path("availability/", delivery_availability_view, name="delivery_availability"),
    path("assignment/<int:order_id>/", assign_delivery_view, name="assign_delivery"),
    path("detail/<int:assignment_id>/", delivery_detail_view, name="delivery_detail"),
    path("detail/<int:assignment_id>/accept/", accept_delivery_view, name="accept_delivery"),
    path("detail/<int:assignment_id>/reject/", reject_delivery_view, name="reject_delivery"),
    path(
        "update-status/<int:assignment_id>/<str:new_status>/",
        update_delivery_status_view,
        name="update_delivery_status",
    ),
]
