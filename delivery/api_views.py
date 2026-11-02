from decimal import Decimal, InvalidOperation
import math

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeliveryAssignment, DeliveryLocation, DeliveryPartnerProfile
from .services import (
    ACTIVE_ASSIGNMENT_STATUSES,
    accept_assignment,
    advance_assignment,
    dispatch_ready_orders,
    refresh_partner_offers,
    reject_assignment,
)
from location.models import LocationSetting
from location.services import calculate_distance


def is_delivery_partner(user):
    return user.role == "delivery_partner"


def assignment_payload(assignment):
    return {
        "id": assignment.pk,
        "order_id": assignment.order_id,
        "order_code": assignment.order.code,
        "status": assignment.status,
        "restaurant": assignment.order.restaurant.name,
        "pickup_address": assignment.order.restaurant.address,
        "restaurant_phone": assignment.order.restaurant.phone,
        "customer_name": (
            assignment.order.user.get_full_name()
            or assignment.order.user.username
        ),
        "customer_phone": assignment.order.customer_phone,
        "delivery_address": assignment.order.delivery_address,
        "total_price": assignment.order.total_price,
        "created_at": assignment.created_at,
    }


class DeliveryDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        refresh_partner_offers(request.user)
        profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
        assignments = DeliveryAssignment.objects.filter(partner=request.user)
        return Response({
            "online": profile.is_online,
            "available": profile.is_available,
            "location": {
                "latitude": float(profile.latitude) if profile.latitude is not None else None,
                "longitude": float(profile.longitude) if profile.longitude is not None else None,
                "accuracy": profile.accuracy,
                "speed": profile.speed,
                "heading": profile.heading,
                "updated_at": profile.location_updated_at,
            },
            "active_deliveries": assignments.filter(
                status__in=ACTIVE_ASSIGNMENT_STATUSES
            ).count(),
            "completed_deliveries": assignments.filter(status="delivered").count(),
            "requests": [
                assignment_payload(assignment)
                for assignment in assignments.filter(status="assigned").select_related(
                    "order__restaurant"
                )
            ],
        })


class DeliveryAvailabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, online):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
        profile.is_online = online
        profile.save(update_fields=["is_online"])
        if online:
            dispatch_ready_orders()
        return Response({"online": profile.is_online})


class DeliveryRequestListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        refresh_partner_offers(request.user)
        assignments = DeliveryAssignment.objects.filter(
            partner=request.user,
            status="assigned",
        ).select_related(
            "order__restaurant",
            "order__user__customer_profile",
        )
        return Response([assignment_payload(item) for item in assignments])


class DeliveryAssignmentActionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    action = None

    def post(self, request, assignment_id, action=None):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        service = accept_assignment if action == "accept" else reject_assignment
        if action == "reject":
            reason = request.data.get("reason", "")
            if not isinstance(reason, str) or len(reason) > 255:
                return Response({"detail": "Rejection reason must be 255 characters or fewer."}, status=400)
            assignment = reject_assignment(request.user, assignment_id, reason)
        else:
            assignment = service(request.user, assignment_id)
        if assignment is None:
            return Response({"detail": "Assignment is unavailable or already processed."}, status=409)
        return Response(assignment_payload(assignment))


class AdvanceDeliveryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id, new_status):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        assignment = advance_assignment(request.user, assignment_id, new_status)
        if assignment is None:
            return Response({"detail": "Invalid delivery status transition."}, status=409)
        return Response(assignment_payload(assignment))


class DeliveryLocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        try:
            assignment_id = int(request.data.get("assignment_id"))
            latitude = Decimal(str(request.data.get("latitude")))
            longitude = Decimal(str(request.data.get("longitude")))
        except (TypeError, ValueError, InvalidOperation):
            return Response({"detail": "Valid assignment_id, latitude, and longitude are required."}, status=400)
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return Response({"detail": "Coordinates are out of range."}, status=400)
        assignment = DeliveryAssignment.objects.filter(pk=assignment_id).select_related("order").first()
        if assignment is None:
            return Response(
                {"detail": "Delivery assignment not found.", "code": "ASSIGNMENT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if assignment.partner_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "You are not the assigned partner for this delivery.", "code": "PERMISSION_DENIED"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if assignment.status in ("delivered", "cancelled", "rejected", "timed_out"):
            return Response(
                {"detail": "Delivery is already completed or inactive.", "code": "DELIVERY_COMPLETED"},
                status=status.HTTP_410_GONE,
            )
        if assignment.status not in ("assigned", "accepted", "arrived_at_pickup", "picked_up", "on_the_way"):
            return Response(
                {"detail": "Active delivery assignment not found.", "code": "ASSIGNMENT_INACTIVE"},
                status=status.HTTP_404_NOT_FOUND,
            )
        metrics = {}
        for name in ("accuracy", "speed", "heading"):
            raw_value = request.data.get(name)
            if raw_value in (None, ""):
                metrics[name] = None
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return Response({"detail": f"{name} must be a number."}, status=400)
            if not math.isfinite(value) or (
                name in ("accuracy", "speed") and value < 0
            ) or (name == "heading" and not 0 <= value <= 360):
                return Response({"detail": f"{name} is out of range."}, status=400)
            metrics[name] = value

        now = timezone.now()
        profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
        profile.latitude = latitude
        profile.longitude = longitude
        profile.accuracy = metrics["accuracy"]
        profile.speed = metrics["speed"]
        profile.heading = metrics["heading"]
        profile.location_updated_at = now
        profile.save(update_fields=[
            "latitude", "longitude", "accuracy", "speed", "heading",
            "location_updated_at",
        ])

        setting = LocationSetting.load()
        last_location = DeliveryLocation.objects.filter(
            delivery_partner=request.user,
        ).first()
        should_save_history = True
        if last_location:
            elapsed = (now - last_location.recorded_at).total_seconds()
            moved_km = calculate_distance(
                last_location.latitude,
                last_location.longitude,
                latitude,
                longitude,
            )
            if (
                elapsed < setting.min_update_interval_seconds
                and moved_km is not None
                and moved_km * 1000 < setting.min_movement_meters
            ):
                should_save_history = False

        if should_save_history:
            DeliveryLocation.objects.create(
                assignment=assignment,
                delivery_partner=request.user,
                order=assignment.order,
                latitude=latitude,
                longitude=longitude,
                accuracy=metrics["accuracy"],
                speed=metrics["speed"],
                heading=metrics["heading"],
            )
        assignment.order.delivery_latitude = latitude
        assignment.order.delivery_longitude = longitude
        assignment.order.delivery_location_updated_at = now
        assignment.order.save(update_fields=[
            "delivery_latitude",
            "delivery_longitude",
            "delivery_location_updated_at",
            "updated_at",
        ])
        return Response({"success": True}, status=status.HTTP_201_CREATED)


class DeliveryHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_delivery_partner(request.user):
            return Response({"detail": "Delivery partner account required."}, status=403)
        assignments = DeliveryAssignment.objects.filter(
            partner=request.user,
        ).select_related("order__restaurant").order_by("-created_at")
        return Response([assignment_payload(item) for item in assignments])