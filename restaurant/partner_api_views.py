from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Review as CustomerReview
from notifications.models import Notification
from orders.models import Order, OrderItem
from orders.services import OrderTransitionError, transition_restaurant_order

from .models import (
    MenuCategory,
    MenuItem,
    Restaurant,
    RestaurantDocument,
    RestaurantEarning,
    RestaurantOffer,
    RestaurantTiming,
    Settlement,
)
from .serializers import (
    MenuCategorySerializer,
    MenuItemSerializer,
    MenuItemWriteSerializer,
    NotificationSerializer,
    PartnerOrderSerializer,
    RestaurantDocumentSerializer,
    RestaurantEarningSerializer,
    RestaurantOfferSerializer,
    RestaurantOfferWriteSerializer,
    RestaurantProfileUpdateSerializer,
    RestaurantTimingBulkSerializer,
    RestaurantTimingSerializer,
    ReviewReplySerializer,
    ReviewSerializer,
    SettlementSerializer,
)
from .services import earnings_summary, payments_summary, restaurant_analytics


# ---------------------------------------------------------------------------
# Shared helpers — every partner route resolves the restaurant of the signed-in
# owner and never trusts a client-posted restaurant_id.
# ---------------------------------------------------------------------------

def get_owned_restaurant_or_403(user):
    """Return the restaurant belonging to this restaurant_owner, or None."""
    if getattr(user, "role", None) != "restaurant_owner":
        return None
    return Restaurant.objects.filter(owner=user).select_related("owner").first()


def partner_context(request, restaurant):
    return {"request": request, "restaurant": restaurant}


def build_order_payload(order):
    assignment = getattr(order, "delivery_assignment", None)
    partner_name = None
    partner_phone = None
    partner_id = None
    delivery_status = "waiting"
    delivery_label = "Waiting for delivery partner"
    pickup_time = None
    delivery_time = None
    if assignment:
        partner_id = assignment.partner_id
        partner_name = assignment.partner.get_full_name() or assignment.partner.username
        partner_phone = getattr(getattr(assignment.partner, "delivery_profile", None), "address", "")
        delivery_status = assignment.status
        delivery_label = assignment.get_status_display()
        pickup_time = assignment.pickup_time
        delivery_time = assignment.delivery_time
    delivery_payload = {
        "status": delivery_status,
        "status_label": delivery_label,
        "partner_id": partner_id,
        "partner_name": partner_name,
        "partner_phone": partner_phone,
        "pickup_time": pickup_time,
        "delivery_time": delivery_time,
    }
    items = []
    for line in order.items.all().select_related("menu_item"):
        food_type = getattr(line.menu_item, "food_type", "")
        items.append({
            "id": line.pk,
            "menu_item_id": line.menu_item_id,
            "name": line.name,
            "food_type": food_type,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "subtotal": line.subtotal,
        })
    return {
        "id": order.pk,
        "code": order.code,
        "customer_name": order.customer_display_name,
        "customer_phone": order.customer_phone,
        "delivery_address": order.delivery_address,
        "items": items,
        "subtotal": order.subtotal,
        "delivery_fee": order.delivery_fee,
        "tax_amount": order.tax_amount,
        "discount_amount": order.discount_amount,
        "total_price": order.total_price,
        "status": order.status,
        "status_display": order.get_status_display(),
        "payment_status": order.payment_status,
        "rejection_reason": order.rejection_reason or "",
        "rejection_note": order.rejection_note or "",
        "estimated_preparation_minutes": order.estimated_preparation_minutes,
        "delivery": delivery_payload,
        "accepted_at": order.accepted_at,
        "preparing_at": order.preparing_at,
        "ready_at": order.ready_at,
        "picked_up_at": order.picked_up_at,
        "delivered_at": order.delivered_at,
        "created_at": order.created_at,
    }


class PartnerAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.restaurant = get_owned_restaurant_or_403(request.user)
        if self.restaurant is None:
            raise PermissionDenied("Restaurant owner account required.")


# ---------------------------------------------------------------------------
# 1. Dashboard
# ---------------------------------------------------------------------------

class PartnerDashboardAPIView(PartnerAPIView):
    def get(self, request):
        restaurant = self.restaurant
        today = timezone.localdate()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        def count_between(queryset, start_date):
            start = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
            return queryset.filter(created_at__gte=start).count()

        def sum_between(queryset, start_date, field):
            start = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
            result = queryset.filter(created_at__gte=start).aggregate(total=Sum(field))["total"]
            return result or Decimal("0.00")

        orders_qs = Order.objects.filter(restaurant=restaurant)
        menu_items_qs = MenuItem.objects.filter(restaurant=restaurant)

        stats = {
            "today_orders": count_between(orders_qs, today),
            "today_pending": orders_qs.filter(created_at__gte=today_start, status="placed").count(),
            "today_preparing": orders_qs.filter(created_at__gte=today_start, status="preparing").count(),
            "today_completed": orders_qs.filter(created_at__gte=today_start, status="delivered").count(),
            "today_cancelled": orders_qs.filter(
                created_at__gte=today_start, status__in=("cancelled", "rejected")
            ).count(),
            "today_revenue": sum_between(
                orders_qs.exclude(status__in=("rejected", "cancelled")), today, "total_price"
            ),
            "week_revenue": sum_between(
                orders_qs.exclude(status__in=("rejected", "cancelled")), week_start, "total_price"
            ),
            "month_revenue": sum_between(
                orders_qs.exclude(status__in=("rejected", "cancelled")), month_start, "total_price"
            ),
            "total_menu_items": menu_items_qs.count(),
            "active_menu_items": menu_items_qs.filter(is_available=True).count(),
            "out_of_stock_items": menu_items_qs.filter(is_available=False).count(),
            "status_breakdown": [
                {"status": s, "label": l, "count": orders_qs.filter(status=s).count()}
                for s, l in Order.STATUS_CHOICES
            ],
        }
        analytics = restaurant_analytics(restaurant, days=30)
        earnings = earnings_summary(restaurant, today=today)
        latest_orders = orders_qs.select_related("restaurant").order_by("-created_at")[:6]
        latest_order_payloads = [build_order_payload(o) for o in latest_orders]

        return Response({
            "restaurant_id": restaurant.id,
            "restaurant_name": restaurant.name,
            "restaurant_status": restaurant.status,
            "is_open": restaurant.is_open,
            "stats": stats,
            "earnings": earnings,
            "analytics": {
                "daily": analytics["daily"],
                "top_items": analytics["top_items"],
                "average_rating": analytics["average_rating"],
                "average_order_value": analytics["average_order_value"],
            },
            "latest_orders": latest_order_payloads,
        })


# ---------------------------------------------------------------------------
# 2. Profile
# ---------------------------------------------------------------------------

class PartnerProfileAPIView(PartnerAPIView):
    def get(self, request):
        serializer = RestaurantProfileUpdateSerializer(
            self.restaurant, context={"request": request}
        )
        data = serializer.data
        data["commission_rate"] = float(self.restaurant.commission_rate)
        data["is_approved"] = self.restaurant.is_approved
        data["accepts_orders"] = self.restaurant.accepts_orders
        return Response(data)

    def patch(self, request):
        serializer = RestaurantProfileUpdateSerializer(
            self.restaurant, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class PartnerProfileToggleOpenAPIView(PartnerAPIView):
    def post(self, request):
        try:
            target = request.data.get("is_open")
            if target is None:
                self.restaurant.is_open = not self.restaurant.is_open
            else:
                self.restaurant.is_open = bool(target)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid is_open value."}, status=400)
        self.restaurant.save(update_fields=["is_open", "updated_at"])
        return Response({"is_open": self.restaurant.is_open})


# ---------------------------------------------------------------------------
# 3. Menu Categories CRUD
# ---------------------------------------------------------------------------

class PartnerCategoryListAPIView(PartnerAPIView):
    def get(self, request):
        categories = (
            MenuCategory.objects.filter(restaurant=self.restaurant)
            .order_by("display_order", "name")
            .annotate(_item_count=Count("items"))
        )
        data = []
        for category in categories:
            payload = MenuCategorySerializer(category).data
            payload["item_count"] = category._item_count
            data.append(payload)
        return Response(data)

    def post(self, request):
        serializer = MenuCategorySerializer(
            data=request.data, context=partner_context(request, self.restaurant)
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(restaurant=self.restaurant)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PartnerCategoryDetailAPIView(PartnerAPIView):
    def _get(self, request, category_id):
        return get_object_or_404(
            MenuCategory, pk=category_id, restaurant=self.restaurant
        )

    def get(self, request, category_id):
        return Response(MenuCategorySerializer(self._get(request, category_id)).data)

    def patch(self, request, category_id):
        category = self._get(request, category_id)
        serializer = MenuCategorySerializer(
            category,
            data=request.data,
            partial=True,
            context=partner_context(request, self.restaurant),
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, category_id):
        category = self._get(request, category_id)
        dependent = category.items.exists()
        if dependent:
            return Response(
                {"detail": "Reassign or delete menu items in this category first."},
                status=status.HTTP_409_CONFLICT,
            )
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 4. Menu Items CRUD (partner-scoped)
# ---------------------------------------------------------------------------

class PartnerMenuListAPIView(PartnerAPIView):
    def get(self, request):
        items = MenuItem.objects.filter(restaurant=self.restaurant).order_by(
            "category", "name"
        )
        return Response(MenuItemSerializer(items, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = MenuItemWriteSerializer(
            data=request.data, context=partner_context(request, self.restaurant)
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        item = serializer.save(restaurant=self.restaurant)
        return Response(
            MenuItemSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PartnerMenuDetailAPIView(PartnerAPIView):
    def _get(self, item_id):
        return get_object_or_404(MenuItem, pk=item_id, restaurant=self.restaurant)

    def get(self, request, item_id):
        return Response(
            MenuItemSerializer(self._get(item_id), context={"request": request}).data
        )

    def patch(self, request, item_id):
        item = self._get(item_id)
        serializer = MenuItemWriteSerializer(
            item,
            data=request.data,
            partial=True,
            context=partner_context(request, self.restaurant),
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(MenuItemSerializer(item, context={"request": request}).data)

    def delete(self, request, item_id):
        self._get(item_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 5. Timings — list + bulk upsert
# ---------------------------------------------------------------------------

class PartnerTimingListAPIView(PartnerAPIView):
    def get(self, request):
        timings = RestaurantTiming.objects.filter(restaurant=self.restaurant).order_by(
            "day_of_week"
        )
        existing = {t.day_of_week: t for t in timings}
        rows = []
        for day in range(7):
            if day in existing:
                rows.append(RestaurantTimingSerializer(existing[day]).data)
            else:
                rows.append({
                    "id": None,
                    "day_of_week": day,
                    "day_label": dict(RestaurantTiming.DAY_CHOICES)[day],
                    "opening_time": "09:00:00",
                    "closing_time": "23:00:00",
                    "is_closed": False,
                })
        return Response(rows)


class PartnerTimingBulkAPIView(PartnerAPIView):
    def put(self, request):
        rows = request.data if isinstance(request.data, list) else []
        serializer = RestaurantTimingBulkSerializer(data=rows)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            existing_ids = set()
            for row in serializer.validated_data:
                day = row["day_of_week"]
                timing, _ = RestaurantTiming.objects.update_or_create(
                    restaurant=self.restaurant,
                    day_of_week=day,
                    defaults={
                        "opening_time": row["opening_time"],
                        "closing_time": row["closing_time"],
                        "is_closed": row.get("is_closed", False),
                    },
                )
                existing_ids.add(timing.pk)
            RestaurantTiming.objects.filter(restaurant=self.restaurant).exclude(
                pk__in=existing_ids
            ).delete()
        return Response(RestaurantTimingSerializer(
            RestaurantTiming.objects.filter(restaurant=self.restaurant).order_by("day_of_week"),
            many=True,
        ).data)


# ---------------------------------------------------------------------------
# 6. Documents — list + upload (status read-only from admin)
# ---------------------------------------------------------------------------

class PartnerDocumentListAPIView(PartnerAPIView):
    def get(self, request):
        documents = RestaurantDocument.objects.filter(restaurant=self.restaurant).order_by(
            "-uploaded_at"
        )
        return Response(
            RestaurantDocumentSerializer(
                documents, many=True, context={"request": request}
            ).data
        )

    def post(self, request):
        serializer = RestaurantDocumentSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(restaurant=self.restaurant, status="pending")
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# 7. Orders — list / detail / actions (accept / reject / prepare / ready)
# ---------------------------------------------------------------------------

class PartnerOrderListAPIView(PartnerAPIView):
    VALID_FILTERS = {s for s, _ in Order.STATUS_CHOICES}

    def get(self, request):
        status_filter = request.query_params.get("status", "").strip()
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        qs = (
            Order.objects.filter(restaurant=self.restaurant)
            .filter(
                Q(payments__status="paid")
                | Q(payments__status="pending", payments__payment_method="cod")
            )
            .distinct()
            .order_by("-created_at")
        )
        if status_filter:
            allowed = set(status_filter.split(","))
            allowed = allowed & self.VALID_FILTERS
            if allowed:
                qs = qs.filter(status__in=allowed)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        qs = qs.select_related("restaurant", "delivery_assignment", "delivery_assignment__partner")
        qs = qs.prefetch_related("items", "items__menu_item", "payments")
        return Response([build_order_payload(o) for o in qs[:200]])


class PartnerOrderDetailAPIView(PartnerAPIView):
    def _get(self, order_id):
        return get_object_or_404(
            Order.objects.select_related("restaurant", "delivery_assignment", "delivery_assignment__partner")
            .prefetch_related("items", "items__menu_item", "payments"),
            pk=order_id,
            restaurant=self.restaurant,
        )

    def get(self, request, order_id):
        return Response(build_order_payload(self._get(order_id)))


class PartnerOrderActionAPIView(PartnerAPIView):
    ACTION_MAP = {
        "accept": Order.STATUS_ACCEPTED,
        "reject": Order.STATUS_REJECTED,
        "prepare": Order.STATUS_PREPARING,
        "preparing": Order.STATUS_PREPARING,
        "ready": Order.STATUS_READY,
    }

    def post(self, request, order_id, action):
        if action not in self.ACTION_MAP:
            return Response({"detail": "Unknown order action."}, status=400)
        new_status = self.ACTION_MAP[action]
        try:
            order = transition_restaurant_order(
                request.user,
                order_id,
                new_status,
                rejection_reason=request.data.get("rejection_reason", ""),
                rejection_note=request.data.get("rejection_note", ""),
                preparation_minutes=request.data.get("estimated_preparation_minutes"),
            )
        except OrderTransitionError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        order.refresh_from_db()
        return Response(build_order_payload(order))


# ---------------------------------------------------------------------------
# 8. Offers CRUD
# ---------------------------------------------------------------------------

class PartnerOfferListAPIView(PartnerAPIView):
    def get(self, request):
        offers = RestaurantOffer.objects.filter(restaurant=self.restaurant).order_by("-created_at")
        return Response(RestaurantOfferSerializer(offers, many=True).data)

    def post(self, request):
        serializer = RestaurantOfferWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(restaurant=self.restaurant)
        return Response(RestaurantOfferSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


class PartnerOfferDetailAPIView(PartnerAPIView):
    def _get(self, offer_id):
        return get_object_or_404(RestaurantOffer, pk=offer_id, restaurant=self.restaurant)

    def get(self, request, offer_id):
        return Response(RestaurantOfferSerializer(self._get(offer_id)).data)

    def patch(self, request, offer_id):
        offer = self._get(offer_id)
        serializer = RestaurantOfferWriteSerializer(offer, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(RestaurantOfferSerializer(offer).data)

    def delete(self, request, offer_id):
        self._get(offer_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 9. Reviews list + reply
# ---------------------------------------------------------------------------

class PartnerReviewListAPIView(PartnerAPIView):
    def get(self, request):
        reviews = (
            CustomerReview.objects.filter(restaurant=self.restaurant)
            .select_related("user", "order")
            .order_by("-created_at")
        )
        payload = []
        for review in reviews:
            payload.append({
                "id": review.id,
                "order_id": review.order_id,
                "order_code": review.order.code if review.order_id else "",
                "customer_name": review.user.get_full_name() or review.user.username,
                "rating": review.rating,
                "stars": "★" * review.rating + "☆" * (5 - review.rating),
                "comment": review.comment or "",
                "restaurant_reply": review.restaurant_reply or "",
                "replied_at": review.replied_at,
                "is_hidden": review.is_hidden,
                "created_at": review.created_at,
            })
        return Response(payload)


class PartnerReviewReplyAPIView(PartnerAPIView):
    def _get(self, review_id):
        return get_object_or_404(
            CustomerReview.objects.select_for_update(),
            pk=review_id,
            restaurant=self.restaurant,
        )

    @transaction.atomic
    def post(self, request, review_id):
        review = self._get(review_id)
        serializer = ReviewReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        review.restaurant_reply = serializer.validated_data["reply"]
        review.replied_at = timezone.now()
        review.replied_by = request.user
        review.save(update_fields=["restaurant_reply", "replied_at", "replied_by", "updated_at"])
        return Response({
            "id": review.id,
            "restaurant_reply": review.restaurant_reply,
            "replied_at": review.replied_at,
        })


# ---------------------------------------------------------------------------
# 10. Earnings — summary + paginated rows
# ---------------------------------------------------------------------------

class PartnerEarningsAPIView(PartnerAPIView):
    def get(self, request):
        today = timezone.localdate()
        summary = earnings_summary(self.restaurant, today=today)
        rows = RestaurantEarning.objects.filter(
            restaurant=self.restaurant, status__in=("pending", "settled")
        ).select_related("order").order_by("-created_at")[:100]
        return Response({
            "summary": summary,
            "rows": RestaurantEarningSerializer(rows, many=True).data,
        })


# ---------------------------------------------------------------------------
# 11. Payments / Settlements summary + list
# ---------------------------------------------------------------------------

class PartnerPaymentsAPIView(PartnerAPIView):
    def get(self, request):
        summary = payments_summary(self.restaurant)
        settlements = Settlement.objects.filter(restaurant=self.restaurant).annotate(
            _earning_count=Count("earnings_set")
        ).order_by("-created_at")
        settlement_rows = []
        for s in settlements:
            data = SettlementSerializer(s).data
            data["earning_count"] = s._earning_count
            settlement_rows.append(data)
        return Response({
            "summary": summary,
            "settlements": settlement_rows,
        })


# ---------------------------------------------------------------------------
# 12. Notifications list + mark read
# ---------------------------------------------------------------------------

class PartnerNotificationListAPIView(PartnerAPIView):
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by(
            "-created_at", "-pk"
        )[:100]
        payload = [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifications
        ]
        unread = notifications.filter(is_read=False).count()
        return Response({"unread_count": unread, "items": payload})


class PartnerNotificationReadAPIView(PartnerAPIView):
    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification, pk=notification_id, user=request.user
        )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"id": notification.id, "is_read": True})
