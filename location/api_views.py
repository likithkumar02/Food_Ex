from decimal import Decimal
from datetime import timedelta
import math
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or getattr(request.user, "role", "") == "admin"))
from customer.models import CustomerAddress, CustomerProfile
from delivery.models import DeliveryAssignment, DeliveryLocation, DeliveryPartnerProfile
from orders.models import Order, OrderStatusEvent
from restaurant.models import Restaurant

from .models import LocationSetting
from .services import (
    calculate_distance,
    calculate_eta,
    check_restaurant_geofence,
    get_nearby_restaurants,
    get_road_route,
    reverse_geocode,
    validate_coordinates,
)


class CustomerLocationUpdateAPIView(APIView):
    """Update authenticated customer's current GPS location."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "customer" and not request.user.is_staff:
            return Response({"success": False, "message": "Only customers can update customer location."}, status=403)

        raw_lat = request.data.get("latitude")
        raw_lon = request.data.get("longitude")
        accuracy = request.data.get("accuracy")
        if accuracy not in (None, ""):
            try:
                accuracy = float(accuracy)
            except (TypeError, ValueError):
                return Response(
                    {"success": False, "message": "Accuracy must be a non-negative number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not math.isfinite(accuracy) or accuracy < 0:
                return Response(
                    {"success": False, "message": "Accuracy must be a non-negative number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        valid, lat, lon = validate_coordinates(raw_lat, raw_lon)
        if not valid:
            return Response(
                {"success": False, "message": "Invalid latitude or longitude coordinates."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        profile.latitude = lat
        profile.longitude = lon
        profile.accuracy = accuracy
        profile.location_updated_at = timezone.now()

        # If customer requested reverse geocoding to auto-fill address
        if request.data.get("reverse_geocode", False):
            geo = reverse_geocode(lat, lon)
            if geo:
                if geo.get("address_line"):
                    profile.address_line = geo["address_line"]
                if geo.get("area"):
                    profile.area = geo["area"]
                if geo.get("address"):
                    profile.address = geo["address"]
                if geo.get("city"):
                    profile.city = geo["city"]
                if geo.get("district"):
                    profile.district = geo["district"]
                if geo.get("state"):
                    profile.state = geo["state"]
                if geo.get("pincode"):
                    profile.pincode = geo["pincode"]

        profile.save()

        return Response({
            "success": True,
            "message": "Location updated successfully",
            "latitude": float(lat),
            "longitude": float(lon),
            "address": profile.address,
            "area": profile.area,
            "city": profile.city,
            "district": profile.district,
            "state": profile.state,
            "pincode": profile.pincode,
            "accuracy": profile.accuracy,
            "location_updated_at": profile.location_updated_at.isoformat(),
        })


class CustomerSavedAddressesAPIView(APIView):
    """List or create saved addresses for the customer."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = CustomerAddress.objects.filter(user=request.user)
        data = [
            {
                "id": a.id,
                "name": a.name,
                "address": a.address,
                "address_line": a.address_line,
                "area": a.area,
                "city": a.city,
                "district": a.district,
                "state": a.state,
                "pincode": a.pincode,
                "latitude": float(a.latitude) if a.latitude else None,
                "longitude": float(a.longitude) if a.longitude else None,
                "is_default": a.is_default,
            }
            for a in addresses
        ]
        return Response({"addresses": data})

    def post(self, request):
        name = request.data.get("name", "Home").strip() or "Home"
        address = request.data.get("address", "").strip()
        address_line = request.data.get("address_line", "").strip()
        area = request.data.get("area", "").strip()
        city = request.data.get("city", "").strip()
        district = request.data.get("district", "").strip()
        state = request.data.get("state", "").strip()
        pincode = request.data.get("pincode", "").strip()
        is_default = bool(request.data.get("is_default", False))

        raw_lat = request.data.get("latitude")
        raw_lon = request.data.get("longitude")
        valid, lat, lon = validate_coordinates(raw_lat, raw_lon)
        if (raw_lat not in (None, "") or raw_lon not in (None, "")) and not valid:
            return Response(
                {"success": False, "message": "Provide a valid latitude and longitude pair."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not address and not (valid and lat is not None and lon is not None):
            return Response(
                {"success": False, "message": "Address text or coordinates are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not address and valid and lat is not None and lon is not None:
            geo = reverse_geocode(lat, lon)
            if geo:
                address = geo.get("address", f"{lat}, {lon}")
                city = city or geo.get("city", "")
                area = area or geo.get("area", "")
                district = district or geo.get("district", "")
                state = state or geo.get("state", "")
                pincode = pincode or geo.get("pincode", "")

        if is_default:
            CustomerAddress.objects.filter(user=request.user).update(is_default=False)

        addr = CustomerAddress.objects.create(
            user=request.user,
            name=name,
            address=address,
            address_line=address_line,
            area=area,
            city=city,
            district=district,
            state=state,
            pincode=pincode,
            latitude=lat if valid else None,
            longitude=lon if valid else None,
            is_default=is_default,
        )

        return Response({
            "success": True,
            "address": {
                "id": addr.id,
                "name": addr.name,
                "address": addr.address,
                "area": addr.area,
                "city": addr.city,
                "district": addr.district,
                "state": addr.state,
                "pincode": addr.pincode,
                "latitude": float(addr.latitude) if addr.latitude else None,
                "longitude": float(addr.longitude) if addr.longitude else None,
                "is_default": addr.is_default,
            }
        }, status=status.HTTP_201_CREATED)


class CustomerAddressDetailAPIView(APIView):
    """Delete or update a saved address."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, address_id):
        address = get_object_or_404(
            CustomerAddress,
            pk=address_id,
            user=request.user,
        )
        text_fields = (
            "name",
            "address",
            "address_line",
            "area",
            "city",
            "district",
            "state",
            "pincode",
        )
        for field_name in text_fields:
            if field_name in request.data:
                value = request.data.get(field_name)
                if not isinstance(value, str):
                    return Response(
                        {"success": False, "message": f"{field_name} must be text."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                setattr(address, field_name, value.strip())

        has_lat = "latitude" in request.data
        has_lon = "longitude" in request.data
        if has_lat != has_lon:
            return Response(
                {"success": False, "message": "Provide both latitude and longitude."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if has_lat:
            valid, lat, lon = validate_coordinates(
                request.data.get("latitude"),
                request.data.get("longitude"),
            )
            if not valid:
                return Response(
                    {"success": False, "message": "Valid coordinates are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            address.latitude = lat
            address.longitude = lon

        if request.data.get("is_default") is True:
            CustomerAddress.objects.filter(user=request.user).exclude(
                pk=address.pk
            ).update(is_default=False)
            address.is_default = True
        elif request.data.get("is_default") is False:
            address.is_default = False

        address.save()
        return Response({
            "success": True,
            "address": {
                "id": address.pk,
                "name": address.name,
                "address": address.address,
                "address_line": address.address_line,
                "area": address.area,
                "city": address.city,
                "district": address.district,
                "state": address.state,
                "pincode": address.pincode,
                "latitude": float(address.latitude) if address.latitude is not None else None,
                "longitude": float(address.longitude) if address.longitude is not None else None,
                "is_default": address.is_default,
            },
        })

    def delete(self, request, address_id):
        addr = get_object_or_404(CustomerAddress, pk=address_id, user=request.user)
        addr.delete()
        return Response({"success": True, "message": "Address deleted."})


class RestaurantLocationUpdateAPIView(APIView):
    """Set restaurant coordinates and location details by restaurant owner."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "restaurant_owner" and not request.user.is_staff:
            return Response({"success": False, "message": "Restaurant owner account required."}, status=403)

        restaurant = Restaurant.objects.filter(owner=request.user).first()
        if request.user.is_staff and request.query_params.get("restaurant_id"):
            restaurant = get_object_or_404(Restaurant, pk=request.query_params.get("restaurant_id"))

        if not restaurant:
            return Response({"success": False, "message": "No restaurant found for this account."}, status=404)

        return Response({
            "success": True,
            "restaurant_id": restaurant.id,
            "name": restaurant.name,
            "latitude": float(restaurant.latitude) if restaurant.latitude is not None else None,
            "longitude": float(restaurant.longitude) if restaurant.longitude is not None else None,
            "address": restaurant.address,
            "address_line": restaurant.address_line,
            "area": restaurant.area,
            "city": restaurant.city,
            "district": restaurant.district,
            "state": restaurant.state,
            "pincode": restaurant.pincode,
            "location_updated_at": restaurant.location_updated_at.isoformat() if restaurant.location_updated_at else None,
        })

    def post(self, request):
        if request.user.role != "restaurant_owner" and not request.user.is_staff:
            return Response({"success": False, "message": "Restaurant owner account required."}, status=403)

        restaurant = Restaurant.objects.filter(owner=request.user).first()
        if not restaurant and not request.user.is_staff:
            return Response({"success": False, "message": "No restaurant found for this account."}, status=404)

        if request.user.is_staff and request.data.get("restaurant_id"):
            restaurant = get_object_or_404(Restaurant, pk=request.data.get("restaurant_id"))
        elif request.user.is_staff and not restaurant:
            return Response(
                {"success": False, "message": "Provide a restaurant_id for an admin location update."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid, lat, lon = validate_coordinates(request.data.get("latitude"), request.data.get("longitude"))
        if not valid:
            return Response({"success": False, "message": "Valid latitude and longitude are required."}, status=400)

        restaurant.latitude = lat
        restaurant.longitude = lon
        restaurant.location_updated_at = timezone.now()

        if request.data.get("address"):
            restaurant.address = request.data.get("address").strip()
        if request.data.get("address_line"):
            restaurant.address_line = request.data.get("address_line").strip()
        if request.data.get("area"):
            restaurant.area = request.data.get("area").strip()
        if request.data.get("city"):
            restaurant.city = request.data.get("city").strip()
        if request.data.get("district"):
            restaurant.district = request.data.get("district").strip()
        if request.data.get("state"):
            restaurant.state = request.data.get("state").strip()
        if request.data.get("pincode"):
            restaurant.pincode = request.data.get("pincode").strip()

        # If address is still blank and reverse_geocode was requested
        if not restaurant.address or request.data.get("reverse_geocode", False):
            geo = reverse_geocode(lat, lon)
            if geo:
                if not restaurant.address:
                    restaurant.address = geo.get("address", f"{lat}, {lon}")
                if not restaurant.city and geo.get("city"):
                    restaurant.city = geo["city"]
                if not restaurant.state and geo.get("state"):
                    restaurant.state = geo["state"]
                if not restaurant.pincode and geo.get("pincode"):
                    restaurant.pincode = geo["pincode"]
                if not restaurant.district and geo.get("district"):
                    restaurant.district = geo["district"]
                if not restaurant.area and geo.get("area"):
                    restaurant.area = geo["area"]

        restaurant.save()

        return Response({
            "success": True,
            "message": "Restaurant location updated successfully",
            "restaurant_id": restaurant.id,
            "latitude": float(lat),
            "longitude": float(lon),
            "address": restaurant.address,
            "address_line": restaurant.address_line,
            "area": restaurant.area,
            "city": restaurant.city,
            "district": restaurant.district,
            "state": restaurant.state,
            "pincode": restaurant.pincode,
            "location_updated_at": restaurant.location_updated_at.isoformat() if restaurant.location_updated_at else None,
        })


class DeliveryLocationUpdateAPIView(APIView):
    """
    Receive live GPS coordinates from delivery partner.
    Supports throttled writes to prevent excessive DB rows.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "delivery_partner" and not request.user.is_staff:
            return Response({"success": False, "message": "Delivery partner account required."}, status=403)

        valid, lat, lon = validate_coordinates(request.data.get("latitude"), request.data.get("longitude"))
        if not valid:
            return Response({"success": False, "message": "Valid coordinates are required."}, status=400)

        measurements = {}
        for name in ("accuracy", "speed", "heading"):
            raw_value = request.data.get(name)
            if raw_value in (None, ""):
                measurements[name] = None
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return Response(
                    {"success": False, "message": f"{name} must be a valid number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not math.isfinite(value):
                return Response(
                    {"success": False, "message": f"{name} must be a finite number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (name in ("accuracy", "speed") and value < 0) or (
                name == "heading" and not 0 <= value <= 360
            ):
                return Response(
                    {"success": False, "message": f"{name} is out of range."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            measurements[name] = value

        accuracy = measurements["accuracy"]
        speed = measurements["speed"]
        heading = measurements["heading"]

        order_id = request.data.get("order_id")
        assignment_id = request.data.get("assignment_id")
        try:
            order_id = int(order_id) if order_id not in (None, "") else None
            assignment_id = int(assignment_id) if assignment_id not in (None, "") else None
        except (TypeError, ValueError):
            return Response(
                {"success": False, "message": "Order and assignment IDs must be valid integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (order_id is not None and order_id <= 0) or (
            assignment_id is not None and assignment_id <= 0
        ):
            return Response(
                {"success": False, "message": "Order and assignment IDs must be positive."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        active_assignment = None
        target_order = None

        if assignment_id:
            assignment = DeliveryAssignment.objects.filter(pk=assignment_id).select_related("order").first()
            if assignment is None:
                return Response(
                    {"success": False, "code": "ASSIGNMENT_NOT_FOUND", "message": "Active delivery assignment not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if assignment.partner_id != request.user.id and not request.user.is_staff:
                return Response(
                    {"success": False, "code": "PERMISSION_DENIED", "message": "You are not the assigned partner for this delivery."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if order_id is not None and order_id != assignment.order_id:
                return Response(
                    {"success": False, "code": "ORDER_MISMATCH", "message": "Order does not match this delivery assignment."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if assignment.status in ("delivered", "cancelled", "rejected", "timed_out"):
                return Response(
                    {"success": False, "code": "DELIVERY_COMPLETED", "message": "Delivery assignment is already completed or inactive."},
                    status=status.HTTP_410_GONE,
                )
            if assignment.status not in ("assigned", "accepted", "arrived_at_pickup", "picked_up", "on_the_way"):
                return Response(
                    {"success": False, "code": "ASSIGNMENT_INACTIVE", "message": "Active delivery assignment not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            active_assignment = assignment
            target_order = assignment.order
        elif order_id:
            assignment = DeliveryAssignment.objects.filter(order_id=order_id).select_related("order").first()
            if assignment is None:
                if not Order.objects.filter(pk=order_id).exists():
                    return Response(
                        {"success": False, "code": "ORDER_NOT_FOUND", "message": "Order not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                return Response(
                    {"success": False, "code": "ASSIGNMENT_NOT_FOUND", "message": "Active delivery assignment not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if assignment.partner_id != request.user.id and not request.user.is_staff:
                return Response(
                    {"success": False, "code": "PERMISSION_DENIED", "message": "You are not the assigned partner for this delivery."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if assignment.status in ("delivered", "cancelled", "rejected", "timed_out"):
                return Response(
                    {"success": False, "code": "DELIVERY_COMPLETED", "message": "Delivery assignment is already completed or inactive."},
                    status=status.HTTP_410_GONE,
                )
            if assignment.status not in ("assigned", "accepted", "arrived_at_pickup", "picked_up", "on_the_way"):
                return Response(
                    {"success": False, "code": "ASSIGNMENT_INACTIVE", "message": "Active delivery assignment not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            active_assignment = assignment
            target_order = assignment.order
        else:
            active_assignment = DeliveryAssignment.objects.filter(
                partner=request.user,
                status__in=("assigned", "accepted", "arrived_at_pickup", "picked_up", "on_the_way"),
            ).select_related("order").first()
            if active_assignment:
                target_order = active_assignment.order

        profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
        now = timezone.now()

        # Update profile's current location
        profile.latitude = lat
        profile.longitude = lon
        profile.accuracy = accuracy
        profile.speed = speed
        profile.heading = heading
        profile.location_updated_at = now
        profile.save(update_fields=[
            "latitude", "longitude", "accuracy", "speed", "heading",
            "location_updated_at",
        ])

        # Throttled history creation: check setting
        setting = LocationSetting.load()
        min_sec = setting.min_update_interval_seconds
        min_m = setting.min_movement_meters

        last_loc = DeliveryLocation.objects.filter(delivery_partner=request.user).first()
        should_write_history = True

        if last_loc:
            elapsed = (now - last_loc.recorded_at).total_seconds()
            dist_km = calculate_distance(last_loc.latitude, last_loc.longitude, lat, lon)
            dist_m = (dist_km * 1000.0) if dist_km is not None else 999.0

            if elapsed < min_sec and dist_m < min_m:
                should_write_history = False

        if should_write_history and active_assignment and target_order:
            DeliveryLocation.objects.create(
                assignment=active_assignment,
                delivery_partner=request.user,
                order=target_order,
                latitude=lat,
                longitude=lon,
                accuracy=accuracy,
                speed=speed,
                heading=heading,
            )

        # Sync order's current delivery location if order exists
        if target_order:
            target_order.delivery_latitude = lat
            target_order.delivery_longitude = lon
            target_order.delivery_location_updated_at = now
            target_order.save(update_fields=[
                "delivery_latitude",
                "delivery_longitude",
                "delivery_location_updated_at",
                "updated_at",
            ])

        # Geofence check: When partner reaches restaurant within 100 meters (Phase B)
        arrived_at_pickup = False
        if active_assignment and active_assignment.status == "accepted" and target_order and target_order.restaurant:
            rest_lat = target_order.restaurant.latitude
            rest_lon = target_order.restaurant.longitude
            if rest_lat is not None and rest_lon is not None:
                if check_restaurant_geofence(lat, lon, rest_lat, rest_lon, radius_meters=100):
                    from delivery.services import advance_assignment
                    res = advance_assignment(request.user, active_assignment.pk, DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP)
                    if res is not None:
                        arrived_at_pickup = True
                        active_assignment.refresh_from_db()
                        target_order.refresh_from_db()

        if profile.is_online and profile.is_available and not active_assignment:
            from delivery.services import dispatch_ready_orders

            dispatch_ready_orders()

        return Response({
            "success": True,
            "latitude": float(lat),
            "longitude": float(lon),
            "accuracy": accuracy,
            "speed": speed,
            "heading": heading,
            "is_online": profile.is_online,
            "arrived_at_pickup": arrived_at_pickup,
            "assignment_status": active_assignment.status if active_assignment else None,
            "location_updated_at": now.isoformat(),
        })


class NearbyRestaurantsAPIView(APIView):
    """Public/customer API to discover restaurants sorted by GPS proximity."""
    permission_classes = [AllowAny]

    def get(self, request):
        raw_lat = request.query_params.get("latitude")
        raw_lon = request.query_params.get("longitude")
        radius = request.query_params.get("radius", 5.0)
        query = request.query_params.get("q")
        cuisine = request.query_params.get("cuisine")

        valid, lat, lon = validate_coordinates(raw_lat, raw_lon)
        if not valid:
            if request.user.is_authenticated and request.user.role == "customer":
                profile = CustomerProfile.objects.filter(user=request.user).first()
                if profile and profile.latitude is not None and profile.longitude is not None:
                    lat, lon = profile.latitude, profile.longitude
                else:
                    return Response(
                        {"detail": "Provide your current coordinates to find nearby restaurants."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"detail": "Valid latitude and longitude are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            radius_value = float(radius)
        except (TypeError, ValueError):
            return Response({"detail": "Radius must be a positive number."}, status=400)
        if not math.isfinite(radius_value) or radius_value <= 0 or radius_value > 20:
            return Response({"detail": "Radius must be greater than 0 and no more than 20 km."}, status=400)

        restaurants = get_nearby_restaurants(
            latitude=lat,
            longitude=lon,
            radius_km=radius_value,
            query=query,
            cuisine=cuisine,
            state=request.query_params.get("state"),
            district=request.query_params.get("district"),
            city=request.query_params.get("city"),
            area=request.query_params.get("area"),
        )

        return Response({
            "user_location": {"latitude": float(lat), "longitude": float(lon)},
            "radius_km": radius_value,
            "count": len(restaurants),
            "restaurants": restaurants,
        })


class NearbyDeliveryPartnersAPIView(APIView):
    """Return only fresh, online, available partners without contact details."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("customer", "restaurant_owner", "admin") and not request.user.is_staff:
            return Response({"detail": "An authenticated Food_Ex account is required."}, status=403)

        valid, latitude, longitude = validate_coordinates(
            request.query_params.get("latitude"),
            request.query_params.get("longitude"),
        )
        if not valid:
            return Response({"detail": "Valid latitude and longitude are required."}, status=400)

        try:
            radius_km = float(request.query_params.get("radius", 3))
        except (TypeError, ValueError):
            return Response({"detail": "Radius must be a positive number."}, status=400)
        if not math.isfinite(radius_km) or radius_km <= 0 or radius_km > 20:
            return Response({"detail": "Radius must be greater than 0 and no more than 20 km."}, status=400)

        setting = LocationSetting.load()
        fresh_after = timezone.now() - timedelta(
            seconds=setting.partner_location_max_age_seconds
        )
        active_partner_ids = DeliveryAssignment.objects.filter(
            status__in=("assigned", "accepted", "arrived_at_pickup", "picked_up", "on_the_way"),
        ).values_list("partner_id", flat=True)
        profiles = DeliveryPartnerProfile.objects.filter(
            is_online=True,
            is_available=True,
            user__role="delivery_partner",
            latitude__isnull=False,
            longitude__isnull=False,
            location_updated_at__gte=fresh_after,
        ).exclude(user_id__in=active_partner_ids).select_related("user")

        partners = []
        for profile in profiles:
            distance = calculate_distance(
                latitude,
                longitude,
                profile.latitude,
                profile.longitude,
            )
            if distance is None or distance > radius_km:
                continue
            partners.append({
                "id": profile.pk,
                "name": profile.user.get_full_name() or profile.user.username,
                "vehicle": profile.vehicle_type,
                "latitude": float(profile.latitude),
                "longitude": float(profile.longitude),
                "distance_km": distance,
                "location_updated_at": profile.location_updated_at.isoformat(),
            })

        partners.sort(key=lambda partner: (partner["distance_km"], partner["id"]))
        return Response({
            "radius_km": radius_km,
            "count": len(partners),
            "delivery_partners": partners,
        })


class OrderDeliveryLocationAPIView(APIView):
    """
    Live delivery tracking data for an active order.
    Protected: Only customer who owns order, assigned partner, or staff/admin can view.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("restaurant", "user"),
            pk=order_id,
        )

        # Check permission
        assignment = DeliveryAssignment.objects.filter(order=order).select_related("partner").first()
        is_owner = (order.user_id == request.user.id)
        is_assigned_partner = (
            assignment
            and assignment.partner_id == request.user.id
            and order.is_live
        )
        is_admin = request.user.is_staff or request.user.role == "admin"
        is_restaurant = (order.restaurant.owner_id == request.user.id)

        if not (is_owner or is_assigned_partner or is_admin or is_restaurant):
            return Response(
                {"success": False, "message": "You do not have permission to track this order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if order.status in (
            Order.STATUS_READY,
            Order.STATUS_FINDING_PARTNER,
            Order.STATUS_DELIVERY_ASSIGNED,
        ):
            from delivery.services import assign_ready_order

            assign_ready_order(order)
            order.refresh_from_db()
            assignment = DeliveryAssignment.objects.filter(
                order=order,
            ).select_related("partner").first()

        # Get latest delivery partner GPS location
        partner_profile = (
            DeliveryPartnerProfile.objects.filter(user=assignment.partner).first()
            if assignment
            else None
        )
        setting = LocationSetting.load()
        location_is_fresh = False
        location_tracking_active = bool(
            order.status in (
                Order.STATUS_DELIVERY_ASSIGNED,
                Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
                Order.STATUS_ARRIVED_AT_PICKUP,
                Order.STATUS_PICKED_UP,
                Order.STATUS_OUT_FOR_DELIVERY,
            )
            and assignment
            and assignment.partner
            and assignment.status in (
                "assigned",
                "accepted",
                "arrived_at_pickup",
                "picked_up",
                "on_the_way",
            )
        )

        partner_lat = None
        partner_lon = None
        speed = None
        heading = None
        recorded_at = None

        if location_tracking_active:
            if (
                partner_profile
                and partner_profile.latitude is not None
                and partner_profile.longitude is not None
            ):
                partner_lat = float(partner_profile.latitude)
                partner_lon = float(partner_profile.longitude)
                speed = partner_profile.speed
                heading = partner_profile.heading
                recorded_at = partner_profile.location_updated_at
                if (
                    recorded_at
                    and timezone.now() - recorded_at
                    <= timedelta(seconds=setting.partner_location_max_age_seconds)
                ):
                    location_is_fresh = True
                else:
                    location_is_fresh = False
            elif (
                order.delivery_latitude is not None
                and order.delivery_longitude is not None
            ):
                partner_lat = float(order.delivery_latitude)
                partner_lon = float(order.delivery_longitude)
                recorded_at = order.delivery_location_updated_at
                if (
                    recorded_at
                    and timezone.now() - recorded_at
                    <= timedelta(seconds=setting.partner_location_max_age_seconds)
                ):
                    location_is_fresh = True
                else:
                    location_is_fresh = False

        # Coordinates for restaurant & customer
        restaurant_latitude = order.restaurant_latitude
        restaurant_longitude = order.restaurant_longitude
        if restaurant_latitude is None:
            restaurant_latitude = order.restaurant.latitude
        if restaurant_longitude is None:
            restaurant_longitude = order.restaurant.longitude
        rest_lat = float(restaurant_latitude) if restaurant_latitude is not None else None
        rest_lon = float(restaurant_longitude) if restaurant_longitude is not None else None

        cust_lat = float(order.customer_latitude) if order.customer_latitude is not None else None
        cust_lon = float(order.customer_longitude) if order.customer_longitude is not None else None
        if cust_lat is None and order.address and order.address.latitude is not None:
            cust_lat = float(order.address.latitude)
            cust_lon = float(order.address.longitude)
        if cust_lat is None:
            cust_prof = CustomerProfile.objects.filter(user=order.user).first()
            if cust_prof and cust_prof.latitude is not None:
                cust_lat = float(cust_prof.latitude)
                cust_lon = float(cust_prof.longitude)

        # Determine delivery tracking phase & target destination
        # Flow: Delivery Partner -> Restaurant -> Customer
        assignment_status = assignment.status if assignment else None
        is_picked_up = (
            order.status in (Order.STATUS_PICKED_UP, Order.STATUS_OUT_FOR_DELIVERY)
            or assignment_status in ("picked_up", "on_the_way")
        )
        is_arrived_pickup = (
            order.status == Order.STATUS_ARRIVED_AT_PICKUP
            or assignment_status == "arrived_at_pickup"
        )
        is_partner_to_restaurant = (
            not is_picked_up
            and not is_arrived_pickup
            and bool(assignment and assignment.partner and assignment_status in ("assigned", "accepted"))
        )

        if order.status == Order.STATUS_DELIVERED or assignment_status == "delivered":
            delivery_phase = "delivered"
            phase_message = "Your order has been delivered."
            target_destination = {
                "type": "customer",
                "name": "Delivery Address",
                "latitude": cust_lat,
                "longitude": cust_lon,
                "address": order.delivery_address,
            }
        elif is_picked_up:
            delivery_phase = "to_customer"
            if order.status == Order.STATUS_PICKED_UP or assignment_status == "picked_up":
                phase_message = "Your order has been picked up and is on the way to you."
            else:
                phase_message = "Your order is on the way to you."
            target_destination = {
                "type": "customer",
                "name": "Delivery Address",
                "latitude": cust_lat,
                "longitude": cust_lon,
                "address": order.delivery_address,
            }
        elif is_arrived_pickup:
            delivery_phase = "at_restaurant"
            phase_message = "Your delivery partner has arrived at the restaurant."
            target_destination = {
                "type": "restaurant",
                "name": order.restaurant.name,
                "latitude": rest_lat,
                "longitude": rest_lon,
                "address": order.restaurant.address,
            }
        elif is_partner_to_restaurant:
            delivery_phase = "to_restaurant"
            phase_message = "Your delivery partner is on the way to the restaurant."
            target_destination = {
                "type": "restaurant",
                "name": order.restaurant.name,
                "latitude": rest_lat,
                "longitude": rest_lon,
                "address": order.restaurant.address,
            }
        else:
            delivery_phase = "preparing"
            phase_message = "Restaurant is preparing your order."
            target_destination = {
                "type": "restaurant",
                "name": order.restaurant.name,
                "latitude": rest_lat,
                "longitude": rest_lon,
                "address": order.restaurant.address,
            }

        # Calculate road route and distance based on current phase
        route_data = None
        calc_dist = None
        target_lat = target_destination.get("latitude")
        target_lon = target_destination.get("longitude")

        if partner_lat is not None and partner_lon is not None and target_lat is not None and target_lon is not None:
            # Live partner position to current target destination
            route_data = get_road_route(partner_lat, partner_lon, target_lat, target_lon)
            calc_dist = route_data["distance_km"]
        elif rest_lat is not None and rest_lon is not None and cust_lat is not None and cust_lon is not None:
            # Fallback preview route: Restaurant to Customer
            route_data = get_road_route(rest_lat, rest_lon, cust_lat, cust_lon)
            calc_dist = route_data["distance_km"]

        if is_arrived_pickup and not is_picked_up:
            calc_dist = 0.0

        eta = calculate_eta(
            calc_dist,
            prep_minutes=(
                0
                if location_tracking_active
                else order.estimated_preparation_minutes or 15
            ),
        ) if calc_dist is not None else None

        confirmed_assignment_statuses = {
            "assigned",
            "accepted",
            "arrived_at_pickup",
            "picked_up",
            "on_the_way",
            "delivered",
        }
        partner_confirmed = bool(
            assignment and assignment.status in confirmed_assignment_statuses
        )
        status_timestamps = {
            event.to_status: event.created_at.isoformat()
            for event in OrderStatusEvent.objects.filter(order=order).order_by(
                "created_at",
                "pk",
            )
        }
        status_timestamps.setdefault("placed", order.created_at.isoformat())

        return Response({
            "order_id": order.id,
            "order_code": order.code,
            "status": order.status,
            "status_display": order.get_status_display(),
            "delivery_phase": delivery_phase,
            "phase_message": phase_message,
            "target_destination": target_destination,
            "route": {
                "coordinates": route_data["coordinates"] if route_data else [],
                "distance_km": calc_dist,
                "is_road_route": route_data["is_road_route"] if route_data else False,
            } if route_data else None,
            "delivery_partner": {
                "name": (
                    assignment.partner.get_full_name() or assignment.partner.username
                    if partner_confirmed
                    else None
                ),
                "vehicle": partner_profile.vehicle_type if partner_confirmed and partner_profile else "",
                "vehicle_number": (
                    partner_profile.vehicle_number
                    if partner_confirmed and partner_profile
                    else ""
                ),
                "is_assigned": partner_confirmed,
                "status": assignment.status,
                "status_display": assignment.get_status_display(),
            } if assignment else None,
            "assignment_attempts": assignment.attempts.count() if assignment else 0,
            "status_timestamps": status_timestamps,
            "location": {
                "latitude": partner_lat,
                "longitude": partner_lon,
                "speed": speed,
                "heading": heading,
                "recorded_at": (
                    recorded_at.isoformat() if recorded_at else None
                ),
                "is_fresh": location_is_fresh,
            } if partner_lat is not None and partner_lon is not None else None,
            "restaurant": {
                "name": order.restaurant.name,
                "cuisine": order.restaurant.cuisine_type,
                "address": order.restaurant.address,
                "area": order.restaurant.area,
                "city": order.restaurant.city,
                "phone": order.restaurant.phone,
                "latitude": rest_lat,
                "longitude": rest_lon,
            },
            "customer": {
                "address": order.delivery_address,
                "latitude": cust_lat,
                "longitude": cust_lon,
            },
            "distance_km": calc_dist,
            "eta": eta["range"] if eta else None,
            "eta_minutes": eta["minutes"] if eta else None,
            "is_live": order.is_live,
        })


class OrderRouteAPIView(APIView):
    """
    Returns navigation waypoints and road route for order map rendering:
    Partner -> Target Destination (Restaurant or Customer depending on delivery phase)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(Order.objects.select_related("restaurant"), pk=order_id)

        assignment = DeliveryAssignment.objects.filter(order=order).select_related("partner").first()
        is_owner = (order.user_id == request.user.id)
        is_assigned_partner = (assignment and assignment.partner_id == request.user.id)
        is_admin = request.user.is_staff or request.user.role == "admin"
        is_restaurant = (order.restaurant.owner_id == request.user.id)

        if not (is_owner or is_assigned_partner or is_admin or is_restaurant):
            return Response({"detail": "Forbidden"}, status=403)

        points = []

        # Restaurant point
        restaurant_latitude = (
            order.restaurant.latitude
            if order.restaurant_latitude is None
            else order.restaurant_latitude
        )
        restaurant_longitude = (
            order.restaurant.longitude
            if order.restaurant_longitude is None
            else order.restaurant_longitude
        )
        rest_point = None
        if restaurant_latitude is not None and restaurant_longitude is not None:
            rest_point = {
                "type": "restaurant",
                "label": order.restaurant.name,
                "latitude": float(restaurant_latitude),
                "longitude": float(restaurant_longitude),
            }
            points.append(rest_point)

        # Partner current point
        partner_point = None
        if assignment:
            prof = DeliveryPartnerProfile.objects.filter(user=assignment.partner).first()
            if (
                prof
                and prof.latitude is not None
                and prof.longitude is not None
                and prof.location_updated_at
                and timezone.now() - prof.location_updated_at
                <= timedelta(
                    seconds=LocationSetting.load().partner_location_max_age_seconds
                )
            ):
                partner_point = {
                    "type": "delivery_partner",
                    "label": f"Partner ({assignment.partner.username})",
                    "latitude": float(prof.latitude),
                    "longitude": float(prof.longitude),
                }
                points.append(partner_point)

        # Customer delivery point
        cust_lat = order.customer_latitude
        cust_lon = order.customer_longitude
        if cust_lat is None and order.address and order.address.latitude is not None:
            cust_lat = order.address.latitude
            cust_lon = order.address.longitude
        cust_point = None
        if cust_lat is not None and cust_lon is not None:
            cust_point = {
                "type": "customer",
                "label": "Delivery Address",
                "latitude": float(cust_lat),
                "longitude": float(cust_lon),
            }
            points.append(cust_point)

        # Calculate phase-appropriate road route
        road_route = None
        is_picked_up = order.status in (Order.STATUS_PICKED_UP, Order.STATUS_OUT_FOR_DELIVERY) or (assignment and assignment.status in ("picked_up", "on_the_way"))
        if partner_point:
            target_pt = cust_point if is_picked_up else rest_point
            if target_pt:
                road_route = get_road_route(
                    partner_point["latitude"], partner_point["longitude"],
                    target_pt["latitude"], target_pt["longitude"],
                )
        elif rest_point and cust_point:
            road_route = get_road_route(
                rest_point["latitude"], rest_point["longitude"],
                cust_point["latitude"], cust_point["longitude"],
            )

        return Response({
            "order_id": order.id,
            "status": order.status,
            "points": points,
            "route_coordinates": road_route["coordinates"] if road_route else [],
            "distance_km": road_route["distance_km"] if road_route else None,
            "duration_minutes": road_route["duration_minutes"] if road_route else None,
            "is_road_route": road_route["is_road_route"] if road_route else False,
            "note": "Road route via OSRM" if (road_route and road_route["is_road_route"]) else "Visual connection path",
        })


class AdminLiveGPSAPIView(APIView):
    """Real-time data for Admin GPS dashboard."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from accounts.models import User

        freshness_cutoff = timezone.now() - timedelta(
            seconds=LocationSetting.load().partner_location_max_age_seconds
        )
        total_customers = User.objects.filter(role="customer").count()
        total_restaurants = Restaurant.objects.count()
        partner_profiles = list(
            DeliveryPartnerProfile.objects.filter(
                user__role="delivery_partner",
            ).select_related("user")
        )
        assignments = list(
            DeliveryAssignment.objects.filter(
                status__in=("assigned", "accepted", "arrived_at_pickup", "picked_up", "on_the_way"),
            ).select_related("partner")
        )
        assignment_by_partner = {assignment.partner_id: assignment for assignment in assignments}

        active_orders_qs = Order.objects.filter(
            status__in=Order.LIVE_STATUSES
        )
        order_feed_qs = Order.objects.filter(
            Q(status__in=Order.LIVE_STATUSES)
            | Q(
                status=Order.STATUS_DELIVERED,
                delivered_at__gte=timezone.now() - timedelta(hours=24),
            )
        ).select_related("restaurant", "user")
        order_assignments = DeliveryAssignment.objects.filter(
            order__in=order_feed_qs,
        ).select_related("partner")
        assignment_by_order = {assignment.order_id: assignment for assignment in order_assignments}

        # Prepare partners data
        partners_data = []
        for p in partner_profiles:
            gps_fresh = bool(
                p.latitude is not None
                and p.longitude is not None
                and p.location_updated_at
                and p.location_updated_at >= freshness_cutoff
            )
            current_assignment = assignment_by_partner.get(p.user_id)
            partner_status = (
                "offline" if not p.is_online
                else "on_delivery" if current_assignment
                else "available" if p.is_available and gps_fresh
                else "unavailable"
            )

            partners_data.append({
                "id": p.id,
                "user_id": p.user_id,
                "name": p.user.get_full_name() or p.user.username,
                "latitude": float(p.latitude) if gps_fresh else None,
                "longitude": float(p.longitude) if gps_fresh else None,
                "accuracy": p.accuracy if gps_fresh else None,
                "vehicle": p.vehicle_type,
                "is_online": p.is_online,
                "is_available": p.is_available,
                "location_updated_at": p.location_updated_at.isoformat() if p.location_updated_at else None,
                "gps_fresh": gps_fresh,
                "assigned_order_id": current_assignment.order_id if current_assignment else None,
                "status": partner_status,
            })

        # Prepare restaurants data
        restaurants_data = [
            {
                "id": r.id,
                "name": r.name,
                "cuisine": r.cuisine_type,
                "address": r.address,
                "area": r.area,
                "delivery_radius_km": float(r.delivery_radius_km),
                "latitude": float(r.latitude) if r.latitude is not None else None,
                "longitude": float(r.longitude) if r.longitude is not None else None,
                "status": r.status,
                "is_open": r.is_open,
            }
            for r in Restaurant.objects.filter(latitude__isnull=False, longitude__isnull=False)
        ]

        # Prepare active orders data
        orders_data = []
        for o in order_feed_qs:
            assign = assignment_by_order.get(o.pk)
            live_gps_fresh = bool(
                o.delivery_latitude is not None
                and o.delivery_longitude is not None
                and o.delivery_location_updated_at
                and o.delivery_location_updated_at >= freshness_cutoff
            )
            orders_data.append({
                "id": o.id,
                "code": o.code,
                "customer_name": o.user.get_full_name() or o.user.username,
                "restaurant_name": o.restaurant.name,
                "partner_name": (
                    assign.partner.get_full_name() or assign.partner.username
                    if assign and assign.partner
                    else "Unassigned"
                ),
                "delivery_status": assign.status if assign else "",
                "status": o.status,
                "status_display": o.get_status_display(),
                "customer_lat": float(o.customer_latitude) if o.customer_latitude is not None else None,
                "customer_lon": float(o.customer_longitude) if o.customer_longitude is not None else None,
                "restaurant_lat": (
                    float(o.restaurant.latitude if o.restaurant_latitude is None else o.restaurant_latitude)
                    if o.restaurant_latitude is not None or o.restaurant.latitude is not None
                    else None
                ),
                "restaurant_lon": (
                    float(o.restaurant.longitude if o.restaurant_longitude is None else o.restaurant_longitude)
                    if o.restaurant_longitude is not None or o.restaurant.longitude is not None
                    else None
                ),
                "delivery_lat": float(o.delivery_latitude) if live_gps_fresh else None,
                "delivery_lon": float(o.delivery_longitude) if live_gps_fresh else None,
                "delivery_location_updated_at": o.delivery_location_updated_at,
                "delivery_gps_fresh": live_gps_fresh,
                "distance": float(o.delivery_distance) if o.delivery_distance else None,
                "eta_minutes": o.estimated_delivery_time,
            })

        return Response({
            "metrics": {
                "total_customers": total_customers,
                "total_restaurants": total_restaurants,
                "online_partners": DeliveryPartnerProfile.objects.filter(
                    is_online=True,
                    user__role="delivery_partner",
                ).count(),
                "active_deliveries": active_orders_qs.count(),
            },
            "delivery_partners": partners_data,
            "restaurants": restaurants_data,
            "active_orders": orders_data,
        })


class DetectLocationAPIView(APIView):
    """
    Public API to detect address components (state, district, city, area)
    from GPS coordinates. Also stores to session and updates customer profile if logged in.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        raw_lat = request.query_params.get("lat") or request.query_params.get("latitude")
        raw_lon = request.query_params.get("lon") or request.query_params.get("longitude")

        valid, lat, lon = validate_coordinates(raw_lat, raw_lon)
        if not valid:
            return Response(
                {"success": False, "message": "Valid latitude and longitude are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        geo = reverse_geocode(lat, lon)
        if not geo:
            geo = {
                "address": f"{float(lat):.4f}, {float(lon):.4f}",
                "address_line": "",
                "area": "",
                "city": "",
                "district": "",
                "state": "",
                "pincode": "",
                "latitude": float(lat),
                "longitude": float(lon),
            }

        # Store in session for immediate use across storefront
        request.session["user_lat"] = str(lat)
        request.session["user_lon"] = str(lon)
        if geo.get("state"):
            request.session["user_state"] = geo["state"]
        if geo.get("district"):
            request.session["user_district"] = geo["district"]
        if geo.get("city"):
            request.session["user_city"] = geo["city"]
        if geo.get("area"):
            request.session["user_area"] = geo["area"]

        # If customer is logged in, also update their CustomerProfile
        if request.user.is_authenticated and getattr(request.user, "role", "") == "customer":
            profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
            profile.latitude = lat
            profile.longitude = lon
            profile.location_updated_at = timezone.now()
            if geo.get("address_line"):
                profile.address_line = geo["address_line"]
            if geo.get("address"):
                profile.address = geo["address"]
            if geo.get("area"):
                profile.area = geo["area"]
            if geo.get("city"):
                profile.city = geo["city"]
            if geo.get("district"):
                profile.district = geo["district"]
            if geo.get("state"):
                profile.state = geo["state"]
            if geo.get("pincode"):
                profile.pincode = geo["pincode"]
            profile.save()

        return Response({
            "success": True,
            **geo,
        })
