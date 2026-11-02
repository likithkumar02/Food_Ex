# GPS and live-tracking guide

## Components

| Layer | Implementation |
|---|---|
| Browser permission and GPS | `navigator.geolocation` through `GPSLocationManager` in `location/static/location/js/location.js`. |
| Map UI | `FoodExMap` Leaflet wrapper; markers for restaurant, customer, delivery partner and picker; polyline route rendering. |
| Backend location endpoints | `location/api_views.py` updates customer, restaurant and delivery locations; returns nearby/tracking/admin payloads. `delivery/api_views.py` has a second delivery location route. |
| Stored data | Current delivery coordinates and timestamp on `DeliveryPartnerProfile`; optional history in `DeliveryLocation`; customer profile/address and restaurant coordinates in their own models; order snapshots in `Order`. |
| Tracking client | `orders/static/orders/js/order-live-tracking.js` polls the order endpoint every 3 seconds; delivery page transmits GPS while active. |
| Configuration | `LocationSetting` controls defaults, minimum update interval/movement, maximum coordinate age, offer timeout/attempt/radius and routing toggle. |

## Delivery partner coordinate path

1. The delivery partner opens `delivery/templates/delivery/detail.html`. Its data attributes provide assignment/order and restaurant/customer positions.
2. `delivery/static/delivery/js/detail.js` creates `FoodExMap` and `GPSLocationManager`; browser GPS permission is requested through `watchPosition`.
3. The GPS manager posts JSON to `/api/location/delivery/update/` with latitude, longitude, accuracy, speed, heading, assignment ID, and order ID. It uses same-origin cookies and a CSRF token.
4. `DeliveryLocationUpdateAPIView.post` requires authentication and delivery-partner role (staff is also accepted), validates coordinate ranges and telemetry, confirms the submitted assignment/order belongs to the requester, and rejects inactive assignments.
5. The view updates `DeliveryPartnerProfile` current coordinates/timestamp. It creates a `DeliveryLocation` history row only when the configured time/distance threshold is met and there is an active assignment.
6. `OrderDeliveryLocationAPIView.get` checks order owner/assigned partner/restaurant owner/admin authorization, tests location freshness against `partner_location_max_age_seconds`, and returns location/phase/route/ETA.
7. The order detail tracker polls that JSON and updates timeline/map. Map markers are not a guarantee of GPS precision or road-route accuracy.

## Stored coordinate semantics

- `CustomerProfile` holds current customer coordinates, accuracy, and update time.
- `CustomerAddress` holds optional per-address coordinates.
- `Restaurant` holds restaurant coordinates and location update time.
- `DeliveryPartnerProfile` holds the latest partner coordinates and telemetry.
- `DeliveryLocation` holds optional assignment/order-linked history points.
- `Order` stores customer/restaurant/delivery coordinate snapshots and delivery-location timestamp. Snapshot fields help preserve the order destination even if a profile later changes.

Latitude/longitude use decimal storage (typically 6 fractional digits in these models); services validate legal coordinate ranges before writes. Timestamps are timezone-aware under `USE_TZ=True`.

## Polling and freshness

- Customer order tracker: HTTP polling every 3 seconds.
- Delivery request feed: HTTP polling every 10 seconds.
- Admin live feed: HTTP polling every 10 seconds.
- `LocationSetting.partner_location_max_age_seconds` defaults to 120 seconds in the model. A stale coordinate may be returned with `is_fresh=false`; clients should not label it as live.
- Delivery location writes are throttled by `min_update_interval_seconds` and `min_movement_meters`.
- Assignment service requires recent partner location and rechecks availability when it dispatches.

There is no WebSocket or push channel in the scanned code. “Live” here means repeated HTTP reads/writes while pages remain open.

## Map and route behavior

`FoodExMap` uses Leaflet if the global `L` library is present. It initializes default center/zoom, adds map tiles, draws markers and lines, and switches tile layer after repeated tile errors. The location settings default routing toggle is false; the browser can display straight visual segments, while server `get_road_route()` can request external route data when enabled. A polyline is not necessarily a route a driver should follow.

Reverse geocoding appears both as a backend helper and direct browser calls to Nominatim in customer/restaurant location pages. External provider rate limits, privacy policy, CORS/network conditions, and attribution requirements apply.

## 403 and other failure causes

The code gives specific authorization failures:

- `DeliveryLocationUpdateAPIView`: user is not a delivery partner/staff → 403.
- Location update with an `assignment_id` or `order_id` owned by another partner → 403.
- Order tracking/route: requester is not customer order owner, assigned partner, restaurant owner, or admin/staff → 403.
- Missing/inactive assignment usually returns 404; terminal assignment can return 410; malformed coordinates/IDs return 400.
- Missing/expired authentication may become DRF 401/403 depending on whether JWT or session authentication handles the request.

For browser debugging, check: active role session, `request.user.role`, correct assignment ID, assignment status, CSRF token, same-origin cookies, and whether the tracking URL is for an order the user owns. The delivery page's 403 handler intentionally stops GPS transmission because continued sends cannot succeed.

## Privacy and limitations

- Customer, restaurant and delivery coordinates are sensitive. Endpoints must retain order ownership and assignment checks; do not expose admin feed or tracking payloads publicly.
- Location is only collected after browser permission; denying permission should leave manual address entry possible.
- The code uses external map/geocoding/routing services in some flows; location may be disclosed to those providers. Verify provider configuration/privacy disclosures before production use.
- Coordinate freshness is time-based; the application does not establish exact physical arrival merely by receiving coordinates. A geofence helper exists, but do not claim automatic arrival is reliable without testing its call sites and real GPS error.
- The delivery update endpoint can report an arrival signal to the client under some service behavior; partner status still has server-side transition rules.

## Viva explanation

> “The browser does not decide the order's status. It sends a coordinate update for an assignment; the server validates the role, coordinate range, and assignment owner, then stores the current position and optionally a throttled history point. The customer page polls an owner-protected endpoint, which returns whether the fix is fresh. Leaflet draws the returned points and optional route. It is polling-based tracking, not a WebSocket.”
