from datetime import timedelta
from decimal import Decimal
from decimal import InvalidOperation
from math import asin, cos, radians, sin, sqrt
import json
import logging
import urllib.request
import urllib.parse

from django.db.models import Avg, Q
from django.utils import timezone

from restaurant.models import Restaurant

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
AVERAGE_RIDER_SPEED_KMPH = 25.0  # City delivery speed


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth
    using the Haversine formula.

    Returns distance in kilometers rounded to 2 decimal places.
    Returns None if any coordinate is missing.
    """
    if None in (lat1, lon1, lat2, lon2):
        return None

    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (ValueError, TypeError):
        return None

    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        return None

    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2.0) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2.0) ** 2
    c = 2 * asin(sqrt(a))
    distance_km = EARTH_RADIUS_KM * c
    return round(distance_km, 2)


def calculate_eta(distance_km, prep_minutes=15):
    """
    Calculate estimated delivery time based on distance and preparation time.
    Returns a dict with total minutes and human-readable range string.
    """
    if distance_km is None:
        return {"minutes": 30, "range": "25–35 min"}

    try:
        dist = float(distance_km)
    except (ValueError, TypeError):
        return {"minutes": 30, "range": "25–35 min"}

    travel_minutes = max(5, round((dist / AVERAGE_RIDER_SPEED_KMPH) * 60))
    total_minutes = int(prep_minutes + travel_minutes)

    low_bound = max(10, total_minutes - 5)
    high_bound = total_minutes + 5

    return {
        "minutes": total_minutes,
        "travel_minutes": travel_minutes,
        "prep_minutes": prep_minutes,
        "range": f"{low_bound}–{high_bound} min",
    }


def validate_coordinates(latitude, longitude):
    """Validate latitude and longitude ranges."""
    try:
        lat = Decimal(str(latitude))
        lon = Decimal(str(longitude))
    except (InvalidOperation, TypeError, ValueError):
        return False, None, None

    if not lat.is_finite() or not lon.is_finite():
        return False, None, None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False, None, None

    return True, lat, lon


def reverse_geocode(latitude, longitude):
    """
    Perform reverse geocoding via OpenStreetMap Nominatim.
    Returns dict with address components or fallback values on network error.
    """
    valid, lat, lon = validate_coordinates(latitude, longitude)
    if not valid:
        return None

    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {"User-Agent": "Food_Ex-DeliveryApp/1.0"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                addr = payload.get("address", {})
                display_name = payload.get("display_name", "")

                road = addr.get("road") or addr.get("suburb") or addr.get("neighbourhood") or ""
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or addr.get("county") or ""
                district = addr.get("state_district") or addr.get("district") or addr.get("city_district") or addr.get("county") or ""
                area = addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter") or ""
                state = addr.get("state") or ""
                pincode = addr.get("postcode") or ""

                if not district and city:
                    district = city
                if not city and district:
                    city = district

                address_line = road or (display_name.split(",")[0] if display_name else "")

                return {
                    "address": display_name,
                    "address_line": address_line,
                    "area": area,
                    "city": city,
                    "district": district,
                    "state": state,
                    "pincode": pincode,
                    "latitude": float(lat),
                    "longitude": float(lon),
                }
    except Exception as exc:
        logger.warning(f"Reverse geocode failed: {exc}")

    return {
        "address": f"{lat:.4f}, {lon:.4f}",
        "address_line": f"Location ({lat:.4f}, {lon:.4f})",
        "area": "",
        "city": "",
        "district": "",
        "state": "",
        "pincode": "",
        "latitude": float(lat),
        "longitude": float(lon),
    }


RESTAURANT_GEOFENCE_RADIUS_METERS = 100


def check_restaurant_geofence(partner_lat, partner_lon, rest_lat, rest_lon, radius_meters=RESTAURANT_GEOFENCE_RADIUS_METERS):
    """
    Check if delivery partner is within geofence radius of the restaurant.
    Returns True if distance <= radius_meters, False otherwise.
    """
    dist_km = calculate_distance(partner_lat, partner_lon, rest_lat, rest_lon)
    if dist_km is None:
        return False
    return (dist_km * 1000.0) <= radius_meters


_ROUTE_CACHE = {}


def get_road_route(origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Query real road route using OSRM routing service.
    Returns dict:
      {
         "coordinates": [[lat, lon], ...],
         "distance_km": float,
         "duration_minutes": int,
         "is_road_route": bool,
      }
    Falls back gracefully to direct straight line if OSRM is unreachable or disabled.
    Caches results in memory to respect OSRM usage policies and avoid redundant requests.
    """
    valid_orig, o_lat, o_lon = validate_coordinates(origin_lat, origin_lon)
    valid_dest, d_lat, d_lon = validate_coordinates(dest_lat, dest_lon)
    if not (valid_orig and valid_dest):
        return {
            "coordinates": [],
            "distance_km": None,
            "duration_minutes": None,
            "is_road_route": False,
        }

    o_lat_f, o_lon_f = float(o_lat), float(o_lon)
    d_lat_f, d_lon_f = float(d_lat), float(d_lon)

    cache_key = f"{round(o_lat_f, 4)},{round(o_lon_f, 4)}->{round(d_lat_f, 4)},{round(d_lon_f, 4)}"
    now = timezone.now()
    if cache_key in _ROUTE_CACHE:
        cached_entry, cached_at = _ROUTE_CACHE[cache_key]
        if (now - cached_at).total_seconds() < 300:
            return cached_entry

    direct_dist = calculate_distance(o_lat_f, o_lon_f, d_lat_f, d_lon_f) or 0.0
    fallback = {
        "coordinates": [[o_lat_f, o_lon_f], [d_lat_f, d_lon_f]],
        "distance_km": round(direct_dist, 2),
        "duration_minutes": max(1, round((direct_dist / AVERAGE_RIDER_SPEED_KMPH) * 60)),
        "is_road_route": False,
    }

    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{o_lon_f:.6f},{o_lat_f:.6f};{d_lon_f:.6f},{d_lat_f:.6f}"
        f"?overview=full&geometries=geojson"
    )
    headers = {"User-Agent": "Food_Ex-DeliveryApp/1.0"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("code") == "Ok" and payload.get("routes"):
                    best_route = payload["routes"][0]
                    geojson_coords = best_route.get("geometry", {}).get("coordinates", [])
                    if geojson_coords:
                        lat_lng_coords = [[coord[1], coord[0]] for coord in geojson_coords]
                        dist_km = round(best_route.get("distance", 0) / 1000.0, 2)
                        dur_sec = best_route.get("duration", 0)
                        dur_min = max(1, round(dur_sec / 60.0))
                        result = {
                            "coordinates": lat_lng_coords,
                            "distance_km": dist_km if dist_km > 0 else round(direct_dist, 2),
                            "duration_minutes": dur_min,
                            "is_road_route": True,
                        }
                        _ROUTE_CACHE[cache_key] = (result, now)
                        if len(_ROUTE_CACHE) > 500:
                            _ROUTE_CACHE.clear()
                        return result
    except Exception as exc:
        logger.warning(f"OSRM routing request failed: {exc}")

    _ROUTE_CACHE[cache_key] = (fallback, now)
    return fallback


def get_nearby_restaurants(
    latitude,
    longitude,
    radius_km=10.0,
    limit=30,
    query=None,
    cuisine=None,
    state=None,
    district=None,
    city=None,
    area=None,
):
    """
    Query approved, active restaurants with coordinates, calculate distance from given point,
    filter by radius, and sort by nearest first.
    """
    valid, user_lat, user_lon = validate_coordinates(latitude, longitude)
    if not valid:
        return []

    try:
        radius_km = float(radius_km)
    except (ValueError, TypeError):
        radius_km = 10.0

    restaurants_qs = Restaurant.objects.filter(
        status="approved",
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    ).select_related("owner").prefetch_related("reviews")

    if query:
        q_term = query.strip()
        restaurants_qs = restaurants_qs.filter(
            Q(name__icontains=q_term)
            | Q(cuisine_type__icontains=q_term)
            | Q(address__icontains=q_term)
            | Q(city__icontains=q_term)
            | Q(menu_items__name__icontains=q_term)
        ).distinct()

    if cuisine:
        restaurants_qs = restaurants_qs.filter(cuisine_type__icontains=cuisine.strip())
    for field_name, value in (
        ("state", state),
        ("district", district),
        ("city", city),
        ("area", area),
    ):
        if value and value.strip():
            restaurants_qs = restaurants_qs.filter(
                **{f"{field_name}__icontains": value.strip()}
            )

    results = []
    for r in restaurants_qs:
        dist = calculate_distance(user_lat, user_lon, r.latitude, r.longitude)
        restaurant_radius = float(r.delivery_radius_km)
        if dist is not None and dist <= min(radius_km, restaurant_radius):
            eta_info = calculate_eta(dist)

            # Compute rating
            ratings = [rev.rating for rev in r.reviews.all() if not rev.is_hidden]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

            results.append({
                "id": r.id,
                "name": r.name,
                "cuisine_type": r.cuisine_type,
                "restaurant_type": r.restaurant_type,
                "address": r.address,
                "area": r.area,
                "city": r.city,
                "district": r.district,
                "state": r.state,
                "pincode": r.pincode,
                "latitude": float(r.latitude),
                "longitude": float(r.longitude),
                "distance": dist,
                "delivery_radius_km": restaurant_radius,
                "delivery_available": True,
                "eta": eta_info["range"],
                "eta_minutes": eta_info["minutes"],
                "is_open": r.is_open,
                "rating": avg_rating,
                "review_count": len(ratings),
                "image_url": r.image.url if r.image else None,
            })

    results.sort(key=lambda item: item["distance"])
    return results[:limit]
