# JavaScript and frontend functions

## Shared frontend conventions

The UI is server-rendered. JavaScript is included by selected Django templates via `{% static %}`; other pages use ordinary Django form POSTs. `food_ex/templates/base.html` loads the common shell styles and `accounts/js/auth.js`. Page scripts use `DOMContentLoaded`, read URL/data attributes from HTML, and update page elements. No WebSocket client or `localStorage` use was found. The auth and location discovery scripts use `sessionStorage`.

The browser's session and CSRF behavior matters: `RoleSessionMiddleware` establishes role-specific sessions; form/API requests on the same origin use Django cookies/CSRF. `auth.js` also stores JWT access/refresh tokens in `sessionStorage` and attaches an access token for authenticated API requests.

## JavaScript inventory

| File | Functions / classes | Templates and behavior |
|---|---|---|
| `accounts/static/accounts/js/auth.js` | IIFE-local `clearTokens`, `refreshAccessToken`, `authenticatedFetch`, `displayMessage`, `responseData`, `createLink`, `renderGuestNav`, `renderUserNav`, `logout`, `showFormError`, `getCsrfToken`, `bindRegistrationForm`, `bindLoginForm`, `bindProfileForm`; nested `setEditing`, `populate`. | Shared `base.html`, auth forms, customer/profile UI. Registration/login post to URL values in `body.dataset`; profile fetches `/api/auth/profile/`; refresh uses configured token-refresh URL. |
| `customer/static/customer/js/dashboard.js` | `DOMContentLoaded` callback; local `setFeedback`. | Customer dashboard location button. Gets browser GPS, posts to the URL embedded in the button, asks backend to reverse-geocode, then filters the dashboard by state. |
| `delivery/static/delivery/js/dashboard.js` | `showGpsError`, `transmit`, `addActionForm`, `refreshRequests` inside a DOM-ready callback. | Delivery dashboard. Uses `GPSLocationManager`; polls the delivery request feed every 10 seconds, creates accept/reject POST forms, and sends GPS updates when online. |
| `delivery/static/delivery/js/detail.js` | DOM-ready map/GPS event handler. | Delivery detail page. Uses `FoodExMap` for pickup/dropoff and starts GPS tracking while the assignment is open; posts to `/api/location/delivery/update/` with assignment/order identifiers. Stops tracking after terminal response or when the page unloads. |
| `location/static/location/js/location.js` | `GPSLocationManager` class; `FoodExMap` class; `getCookie`. | Shared location library. GPS one-shot and continuous tracking; Leaflet tile layer, markers, route polyline and bounds. Used by location, delivery and customer pages. |
| `location/static/location/js/admin-location.js` | `fetchLiveFeed`, `renderLiveMap`, `renderLists`; `window.selectOrder`. | Admin location dashboard; polls `/api/location/admin/live/` every 10 seconds, renders markers and active order/partner summaries. |
| `location/static/location/js/customer-location.js` | `setFeedback`, `updateMarkerAndFields`, DOM event handlers. | Customer address/location page; GPS/map pin selection, optional direct Nominatim reverse-geocode, customer location update, saved address create/delete. |
| `location/static/location/js/customer-storefront-location.js` | `setDetecting`, `handleCoords`, `detectLocation`; DOM handlers. | Restaurant list page; uses browser geolocation and `/api/location/detect/`, stores current coordinates/state in `sessionStorage`, and updates query parameters. |
| `location/static/location/js/restaurant-location.js` | `setFeedback`, `updateMarkerAndFields`, DOM event handlers. | Restaurant location settings page; GPS, draggable map pin, reverse-geocode, and POST to `/api/location/restaurant/update/`. |
| `orders/static/orders/js/order-live-tracking.js` | `hasCoordinates`, `updateTimeline`, `updateMap`, `refreshTracking`; DOM-ready setup. | Order detail and customer location page (depending on template context). Polls the tracking URL every 3 seconds, updates timeline, assignment text, freshness, route and map markers. |
| `orders/static/orders/js/order-tracking.js` | `refreshStatus`; DOM-ready setup. | Legacy/simple tracker. Polls the status URL every 5 seconds and updates text/timeline. No local template reference to this asset was found in the static-reference scan; verify before relying on it. |

## Shared GPS and map library

### `GPSLocationManager`

- Constructor accepts options: `enableHighAccuracy`, timeout, maximum age, minimum send interval, and minimum movement distance.
- `isSupported()` checks for `navigator.geolocation`.
- `getCurrentLocation(onSuccess, onError)` requests one position and formats permission/unavailable/timeout failures.
- `sendDeliveryLocation(position, identifiers={})` POSTs coordinates and telemetry to `/api/location/delivery/update/`, using same-origin credentials and a CSRF token. It throws an `Error` carrying `status` and response `data` for non-2xx results.
- `startTracking(onUpdate, onError)` uses `watchPosition`; suppresses updates under configured interval/distance thresholds.
- `stopTracking()` clears the browser watch.
- `calculateDistance(lat1,lon1,lat2,lon2)` implements haversine distance in kilometers.

### `FoodExMap`

- Constructor reads tile and center data from DOM attributes and creates a Leaflet map when Leaflet is loaded.
- `initialize()` sets the map view and tile provider.
- `_setupTileLayer()` installs a layer and falls back after repeated tile errors.
- `_createCustomIcon(type)` maps restaurant/customer/delivery/picker kinds to Leaflet div icons.
- `addMarker`, `updateMarker`, `removeMarker`, `clearMarkers` maintain keyed markers.
- `clearRoute`, `drawRoute(points,options)`, `fitBounds(pointsOrMarkers)`, `setCenter`, and `invalidateSize` manage map overlays/view.
- `getCookie(name)` reads Django's CSRF cookie or hidden form token.

## Important request/response behavior

| Interaction | Request | Browser behavior |
|---|---|---|
| Registration | POST JSON to `body.dataset.authRegisterUrl`; CSRF header is added when found. | Validates browser fields, reports server errors, redirects to login on success. |
| Login | POST JSON to `body.dataset.authLoginUrl`. | Saves access/refresh tokens to `sessionStorage`; redirects to `/`. |
| Refresh | POST `{refresh}` to configured refresh endpoint. | Stores new access token and rotated refresh token when returned; clears tokens for rejected response. Network exceptions return false. |
| Profile | GET/PUT `/api/auth/profile/`; profile image is sent as `FormData`. | Populates profile fields and image; can toggle edit/cancel; redirects to login if initial GET fails. |
| Storefront location | GET `/api/location/detect/?lat=…&lon=…`. | Updates state/district/city and query params; GPS failures leave restaurant browsing available. |
| Customer saved address | GET/POST/PATCH/DELETE `/api/location/customer/addresses/…`. | Saves address payload and reloads on create/delete. |
| Restaurant location | POST `/api/location/restaurant/update/`. | Saves coordinate and address fields, shows feedback, reloads on success. |
| Delivery GPS | POST `/api/location/delivery/update/`. | Sends lat/lon and accuracy/speed/heading; terminal assignment result stops watch; 403 stops tracking and displays authorization error. |
| Delivery offer feed | GET URL provided by `data-requests-url`; accept/reject use supplied URLs. | Polls every 10 seconds and constructs safe text nodes for request details/forms. |
| Customer order tracking | GET URL provided by `#orderTracking[data-tracking-url]`. | Polls every 3 seconds; updates timeline, partner/phase, route/map, ETA and freshness; stops on terminal/non-live response. |
| Admin GPS dashboard | GET `/api/location/admin/live/`. | Polls every 10 seconds and refreshes map/list metrics. |

## Error handling and limitations

- Most forms show server messages in a status element. GPS permission and request errors are surfaced as text.
- The `customer-location.js` delete handler reloads after any response without checking its HTTP status; the live tracker generally preserves the page and reports a retry message on exceptions.
- `admin-location.js` logs a failed fetch to the console. It builds some list and popup markup with `innerHTML`; source-derived untrusted names/address values should be HTML-escaped before insertion (see [AUTHENTICATION_AND_SECURITY.md](./AUTHENTICATION_AND_SECURITY.md)).
- Nominatim and map tile calls require network access, and browser geolocation generally requires a secure context and user permission.
- Polling is near-live, not streaming. Browser location accuracy, HTTP polling cadence, stale-coordinate threshold, and third-party routing availability all affect displayed results.

## Example for the viva

> “The delivery detail page creates a `GPSLocationManager`, starts `watchPosition`, and periodically sends the coordinates to a Django API with the active assignment ID. The backend verifies the role and assignment owner, saves the current profile position and throttles history rows. The customer page polls an order tracking endpoint and updates the Leaflet marker. This is periodic HTTP tracking, not a WebSocket.”

For the associated page markup and exact usage, see [TEMPLATE_BY_TEMPLATE_GUIDE.md](./TEMPLATE_BY_TEMPLATE_GUIDE.md); for endpoint rules see [COMPLETE_API_REFERENCE.md](./COMPLETE_API_REFERENCE.md).
