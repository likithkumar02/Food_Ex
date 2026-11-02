from django.urls import path

from location.api_views import DeliveryLocationUpdateAPIView
from .api_views import (
    AdvanceDeliveryAPIView,
    DeliveryAssignmentActionAPIView,
    DeliveryAvailabilityAPIView,
    DeliveryDashboardAPIView,
    DeliveryHistoryAPIView,
    DeliveryLocationAPIView,
    DeliveryRequestListAPIView,
)


urlpatterns = [
    path("dashboard/", DeliveryDashboardAPIView.as_view(), name="api_delivery_dashboard"),
    path("online/", DeliveryAvailabilityAPIView.as_view(), {"online": True}, name="api_delivery_online"),
    path("offline/", DeliveryAvailabilityAPIView.as_view(), {"online": False}, name="api_delivery_offline"),
    path("requests/", DeliveryRequestListAPIView.as_view(), name="api_delivery_requests"),
    path("requests/<int:assignment_id>/accept/", DeliveryAssignmentActionAPIView.as_view(), {"action": "accept"}, name="api_delivery_accept"),
    path("requests/<int:assignment_id>/reject/", DeliveryAssignmentActionAPIView.as_view(), {"action": "reject"}, name="api_delivery_reject"),
    path("<int:assignment_id>/arrived-at-pickup/", AdvanceDeliveryAPIView.as_view(), {"new_status": "arrived_at_pickup"}, name="api_delivery_arrived_at_pickup"),
    path("<int:assignment_id>/pickup/", AdvanceDeliveryAPIView.as_view(), {"new_status": "picked_up"}, name="api_delivery_pickup"),
    path("<int:assignment_id>/out-for-delivery/", AdvanceDeliveryAPIView.as_view(), {"new_status": "on_the_way"}, name="api_delivery_out_for_delivery"),
    path("<int:assignment_id>/complete/", AdvanceDeliveryAPIView.as_view(), {"new_status": "delivered"}, name="api_delivery_complete"),
    path("location/", DeliveryLocationAPIView.as_view(), name="api_delivery_location"),
    path("location/update/", DeliveryLocationUpdateAPIView.as_view(), name="api_delivery_location_update"),
    path("history/", DeliveryHistoryAPIView.as_view(), name="api_delivery_history"),
]