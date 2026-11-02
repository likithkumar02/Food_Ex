from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Review as CustomerReview
from restaurant.models import PlatformSetting, Restaurant


PERCENT_CLAMP = (Decimal("0"), Decimal("90"))


def _clamp(value: Decimal, bounds) -> Decimal:
    low, high = bounds
    if value < low:
        return low
    if value > high:
        return high
    return value


class AdminForbidden(Response):
    def __init__(self, detail="Admin account required."):
        super().__init__({"detail": detail}, status=status.HTTP_403_FORBIDDEN)


class AdminAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) != "admin":
            return AdminForbidden()
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# 1. Restaurants — list / approve / reject / suspend / commission
# ---------------------------------------------------------------------------

class AdminRestaurantListAPIView(AdminAPIView):
    VALID_STATUS = {"pending", "approved", "rejected", "suspended"}

    def get(self, request):
        status_filter = request.query_params.get("status", "").strip()
        query = request.query_params.get("q", "").strip()
        qs = Restaurant.objects.select_related("owner").order_by("-created_at")
        if status_filter and status_filter != "all":
            if status_filter in self.VALID_STATUS:
                qs = qs.filter(status=status_filter)
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(city__icontains=query)
                | Q(fssai_license_no__icontains=query)
            )
        rows = []
        for r in qs[:200]:
            rows.append({
                "id": r.id,
                "name": r.name,
                "cuisine": r.cuisine,
                "restaurant_type": r.restaurant_type,
                "city": r.city,
                "status": r.status,
                "status_label": r.get_status_display(),
                "is_active": r.is_active,
                "owner_id": r.owner_id,
                "owner_name": r.owner.get_full_name() or r.owner.username,
                "owner_email": r.owner.email,
                "fssai_license_no": r.fssai_license_no or "",
                "commission_percent": float(r.commission_percent) if r.commission_percent is not None else None,
                "commission_rate": float(r.commission_rate),
                "is_open": r.is_open,
                "submitted_at": r.created_at,
                "reviewed_at": r.reviewed_at,
                "status_reason": r.status_reason or "",
            })
        return Response({"count": len(rows), "items": rows})


class AdminRestaurantActionAPIView(AdminAPIView):
    ACTIONS = {"approve", "reject", "suspend"}

    @transaction.atomic
    def post(self, request, restaurant_id, action):
        if action not in self.ACTIONS:
            return Response({"detail": "Unknown admin action."}, status=400)
        restaurant = get_object_or_404(
            Restaurant.objects.select_for_update(), pk=restaurant_id
        )
        now = timezone.now()
        if action == "approve":
            restaurant.status = "approved"
            restaurant.is_active = True
            restaurant.status_reason = ""
            restaurant.reviewed_at = now
            restaurant.reviewed_by = request.user
            restaurant.save(update_fields=[
                "status", "is_active", "status_reason", "reviewed_at", "reviewed_by", "updated_at",
            ])
        elif action == "reject":
            reason = (request.data.get("reason") or "").strip()
            if len(reason) < 2:
                return Response(
                    {"detail": "A rejection reason (≥2 chars) is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            restaurant.status = "rejected"
            restaurant.is_active = False
            restaurant.status_reason = reason
            restaurant.reviewed_at = now
            restaurant.reviewed_by = request.user
            restaurant.save(update_fields=[
                "status", "is_active", "status_reason", "reviewed_at", "reviewed_by", "updated_at",
            ])
        else:  # suspend
            reason = (request.data.get("reason") or "").strip()
            restaurant.status = "suspended"
            restaurant.is_active = False
            restaurant.status_reason = reason
            restaurant.reviewed_at = now
            restaurant.reviewed_by = request.user
            restaurant.save(update_fields=[
                "status", "is_active", "status_reason", "reviewed_at", "reviewed_by", "updated_at",
            ])
        return Response({
            "id": restaurant.id,
            "status": restaurant.status,
            "status_label": restaurant.get_status_display(),
            "is_active": restaurant.is_active,
            "reviewed_at": restaurant.reviewed_at,
        })


class AdminRestaurantCommissionAPIView(AdminAPIView):
    @transaction.atomic
    def post(self, request, restaurant_id):
        restaurant = get_object_or_404(
            Restaurant.objects.select_for_update(), pk=restaurant_id
        )
        raw = request.data.get("commission_percent")
        if raw is None or raw == "":
            restaurant.commission_percent = None
            restaurant.save(update_fields=["commission_percent", "updated_at"])
            return Response({
                "id": restaurant.id,
                "commission_percent": None,
                "commission_rate": float(restaurant.commission_rate),
                "using_platform_default": True,
            })
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {"detail": "commission_percent must be a number or null."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        value = _clamp(value, PERCENT_CLAMP)
        restaurant.commission_percent = value
        restaurant.save(update_fields=["commission_percent", "updated_at"])
        return Response({
            "id": restaurant.id,
            "commission_percent": float(restaurant.commission_percent),
            "commission_rate": float(restaurant.commission_rate),
            "using_platform_default": False,
        })


# ---------------------------------------------------------------------------
# 2. Platform settings — GET + PATCH
# ---------------------------------------------------------------------------

class AdminPlatformSettingsAPIView(AdminAPIView):
    def get(self, request):
        s = PlatformSetting.load()
        return Response({
            "default_commission_percent": float(s.default_commission_percent),
            "gst_percent": float(s.gst_percent),
            "delivery_fee": float(s.delivery_fee),
            "updated_at": s.updated_at,
        })

    @transaction.atomic
    def patch(self, request):
        s = PlatformSetting.objects.select_for_update().get(pk=PlatformSetting.load().pk)
        fields = []
        for field_name, clamp_low, clamp_high in [
            ("default_commission_percent", 0, 90),
            ("gst_percent", 0, 100),
        ]:
            if field_name in request.data:
                try:
                    value = Decimal(str(request.data[field_name]))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {"detail": f"{field_name} must be a number."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if value < clamp_low or value > clamp_high:
                    return Response(
                        {"detail": f"{field_name} must be between {clamp_low} and {clamp_high}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                setattr(s, field_name, value)
                fields.append(field_name)
        if "delivery_fee" in request.data:
            try:
                value = Decimal(str(request.data["delivery_fee"]))
            except (InvalidOperation, TypeError, ValueError):
                return Response(
                    {"detail": "delivery_fee must be a number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if value < 0:
                return Response(
                    {"detail": "delivery_fee must be ≥ 0."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            s.delivery_fee = value
            fields.append("delivery_fee")
        if fields:
            fields.append("updated_at")
            s.save(update_fields=fields)
        return Response({
            "default_commission_percent": float(s.default_commission_percent),
            "gst_percent": float(s.gst_percent),
            "delivery_fee": float(s.delivery_fee),
            "updated_at": s.updated_at,
        })


# ---------------------------------------------------------------------------
# 3. Review moderation
# ---------------------------------------------------------------------------

class AdminReviewModerateAPIView(AdminAPIView):
    @transaction.atomic
    def post(self, request, review_id):
        review = get_object_or_404(
            CustomerReview.objects.select_for_update(), pk=review_id
        )
        if "is_hidden" not in request.data:
            return Response(
                {"detail": "is_hidden boolean is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            is_hidden = bool(request.data["is_hidden"])
        except (TypeError, ValueError):
            return Response(
                {"detail": "is_hidden must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        moderation_note = (request.data.get("moderation_note") or "").strip()[:255]
        review.is_hidden = is_hidden
        review.moderation_note = moderation_note
        review.moderated_at = timezone.now()
        review.moderated_by = request.user
        review.save(update_fields=[
            "is_hidden", "moderation_note", "moderated_at", "moderated_by", "updated_at",
        ])
        return Response({
            "id": review.id,
            "is_hidden": review.is_hidden,
            "moderation_note": review.moderation_note,
            "moderated_at": review.moderated_at,
            "moderated_by": review.moderated_by_id,
        })
