from django.urls import path

from .api_views import ReviewCreateAPIView, RestaurantReviewListAPIView


urlpatterns = [
    path("restaurants/<int:restaurant_id>/reviews/", RestaurantReviewListAPIView.as_view(), name="api_restaurant_reviews"),
    path("restaurants/<int:restaurant_id>/reviews/create/", ReviewCreateAPIView.as_view(), name="api_create_review"),
]