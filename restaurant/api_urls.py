from django.urls import path

from location.api_views import NearbyRestaurantsAPIView
from .api_views import (
    RestaurantDetailAPIView,
    RestaurantListAPIView,
    RestaurantMenuAPIView,
    RestaurantMenuItemManageAPIView,
    RestaurantMenuManageAPIView,
)
from .partner_api_views import (
    PartnerCategoryDetailAPIView,
    PartnerCategoryListAPIView,
    PartnerDashboardAPIView,
    PartnerDocumentListAPIView,
    PartnerEarningsAPIView,
    PartnerMenuDetailAPIView,
    PartnerMenuListAPIView,
    PartnerNotificationListAPIView,
    PartnerNotificationReadAPIView,
    PartnerOfferDetailAPIView,
    PartnerOfferListAPIView,
    PartnerOrderActionAPIView,
    PartnerOrderDetailAPIView,
    PartnerOrderListAPIView,
    PartnerPaymentsAPIView,
    PartnerProfileAPIView,
    PartnerProfileToggleOpenAPIView,
    PartnerReviewListAPIView,
    PartnerReviewReplyAPIView,
    PartnerTimingBulkAPIView,
    PartnerTimingListAPIView,
)


urlpatterns = [
    path("", RestaurantListAPIView.as_view(), name="api_restaurant_list"),
    path("nearby/", NearbyRestaurantsAPIView.as_view(), name="api_restaurant_nearby"),
    path("manage/menu/", RestaurantMenuManageAPIView.as_view(), name="api_restaurant_menu_manage"),
    path("manage/menu/<int:item_id>/", RestaurantMenuItemManageAPIView.as_view(), name="api_restaurant_menu_item"),
    path("<int:restaurant_id>/", RestaurantDetailAPIView.as_view(), name="api_restaurant_detail"),
    path("<int:restaurant_id>/menu/", RestaurantMenuAPIView.as_view(), name="api_restaurant_menu"),

    path("partner/dashboard/", PartnerDashboardAPIView.as_view(), name="api_partner_dashboard"),

    path("partner/profile/", PartnerProfileAPIView.as_view(), name="api_partner_profile"),
    path("partner/profile/toggle-open/", PartnerProfileToggleOpenAPIView.as_view(), name="api_partner_toggle_open"),

    path("partner/categories/", PartnerCategoryListAPIView.as_view(), name="api_partner_category_list"),
    path("partner/categories/<int:category_id>/", PartnerCategoryDetailAPIView.as_view(), name="api_partner_category_detail"),

    path("partner/menu/", PartnerMenuListAPIView.as_view(), name="api_partner_menu_list"),
    path("partner/menu/<int:item_id>/", PartnerMenuDetailAPIView.as_view(), name="api_partner_menu_detail"),

    path("partner/timings/", PartnerTimingListAPIView.as_view(), name="api_partner_timings_list"),
    path("partner/timings/bulk/", PartnerTimingBulkAPIView.as_view(), name="api_partner_timings_bulk"),

    path("partner/documents/", PartnerDocumentListAPIView.as_view(), name="api_partner_documents"),

    path("partner/orders/", PartnerOrderListAPIView.as_view(), name="api_partner_order_list"),
    path("partner/orders/<int:order_id>/", PartnerOrderDetailAPIView.as_view(), name="api_partner_order_detail"),
    path("partner/orders/<int:order_id>/<str:action>/", PartnerOrderActionAPIView.as_view(), name="api_partner_order_action"),

    path("partner/offers/", PartnerOfferListAPIView.as_view(), name="api_partner_offer_list"),
    path("partner/offers/<int:offer_id>/", PartnerOfferDetailAPIView.as_view(), name="api_partner_offer_detail"),

    path("partner/reviews/", PartnerReviewListAPIView.as_view(), name="api_partner_review_list"),
    path("partner/reviews/<int:review_id>/reply/", PartnerReviewReplyAPIView.as_view(), name="api_partner_review_reply"),

    path("partner/earnings/", PartnerEarningsAPIView.as_view(), name="api_partner_earnings"),
    path("partner/payments/", PartnerPaymentsAPIView.as_view(), name="api_partner_payments"),

    path("partner/notifications/", PartnerNotificationListAPIView.as_view(), name="api_partner_notifications"),
    path("partner/notifications/<int:notification_id>/read/", PartnerNotificationReadAPIView.as_view(), name="api_partner_notification_read"),
]
