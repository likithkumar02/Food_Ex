# Feature-by-feature workflow

This document follows concrete code paths found in the repository. A route may have both a server-rendered page and an API implementation; they are not interchangeable. For the exhaustive API route inventory see [COMPLETE_API_REFERENCE.md](./COMPLETE_API_REFERENCE.md).

## Registration and authentication

### Customer

`/customer/register/` → `accounts.views.portal_register_view(role="customer")` → `auth/portal_register.html` → Django registration form POST → `UserRegistrationForm` / `CustomerProfile` → role-specific session login → redirect to customer dashboard/storefront.

The API alternative is `POST /api/auth/customer/register/` → `RegisterAPIView` with fixed role `"customer"` → `RegistrationSerializer` → atomic user/profile creation → JSON success. Login API returns JWT access/refresh tokens and profile payload. Browser login additionally establishes a role session.

### Restaurant partner

`/restaurant/register/` → portal registration view with fixed `restaurant_owner` role → user and `RestaurantRegistrationForm` validation → restaurant profile creation → partner login/session. Registration is not the same as approval: `Restaurant.status` defaults to pending and `is_active` defaults false. Admin approval activates listings.

### Delivery partner

`/delivery/register/` → portal registration view with fixed `delivery_partner` role → required vehicle/license/address fields → `DeliveryPartnerProfile` creation → portal login. API registration similarly chooses role server-side and creates an offline partner profile.

### Login, password and session

Portal login verifies that the authenticated account's role matches the requested portal. `RoleSessionMiddleware` can keep customer/delivery sessions separate. Django password validators are configured; forgot-password uses Django's single-use reset workflow and console email backend in base settings. Legacy session JSON routes coexist with DRF JWT routes.

## Restaurant discovery and menu

Homepage `/` → `food_ex.views.home` queries active approved restaurants and available items and renders `food_ex/templates/home.html`.

Customer restaurant list is `/customer/` → `accounts.views.customer_portal_view` → `restaurant_listing_context` in `restaurant/views.py` → `restaurant/templates/restaurant/list.html`. It filters query/location and approved status; customer-location JS can update the URL filters.

Restaurant detail `/restaurants/<id>/` → `restaurant.views.restaurant_detail_view` → `restaurant/templates/restaurant/detail.html`; menu items come from `MenuItem`. Public JSON equivalents are under `/api/restaurants/`.

Partner menu writes use either simple owner menu routes under `/api/restaurants/manage/menu/` or the broader `/api/restaurants/partner/menu/` and category endpoints. All owner mutations should be read with the `owned_restaurant` / `PartnerAPIView` scoping checks.

## Cart and checkout

Page path: menu action → POST `/orders/cart/add/<menu_item_id>/` → `orders.views.add_to_cart_view` → validates menu availability/restaurant state → one-restaurant cart rule → `Cart`/`CartItem` → redirect to `/orders/cart/`.

When a cart already contains another restaurant's item, `orders/templates/orders/cart_conflict.html` asks the user to keep or clear the cart before proceeding. Quantity is limited to 20 per item.

Checkout page `/orders/checkout/` loads the customer's saved addresses. POST calls atomic `create_order_from_cart()`; server computes subtotal, discount, tax, fee and total, stores an `OrderStatusEvent` and immutable-ish item snapshots, clears the cart, and redirects to `/payments/orders/<order-id>/payment/`.

The API counterpart is `GET/POST /api/cart/`, `PATCH/DELETE /api/cart/items/<id>/`, `GET /api/cart/summary/`, and `GET/POST /api/orders/`. The API does not trust client-calculated totals.

## Payment and cash on delivery

Payment page POST → `payments.views.payment_page` → `PaymentService.process(order, payment_method)`:

- COD: create or reuse pending COD payment; notify restaurant/customer.
- Development `"test"`: only accepted when `PAYMENT_PROVIDER=="mock"`; server generates the transaction reference and marks payment paid.
- Card/UPI/wallet without a configured real provider: rejected.

`POST /api/payments/orders/<id>/pay/` requires an authenticated customer and scopes order to that user. The project is not connected to a real gateway by this code path.

## Restaurant order lifecycle

Partner order list/detail → `orders.views.restaurant_order_management_view` or partner API order endpoints → restaurant-scoped order rows. Actions call `transition_restaurant_order()`:

`placed → accepted → preparing → ready_for_pickup`

Rejection/cancellation paths record reason/status events and may invoke refund/earning cancellation services. Invalid transitions are rejected. Restaurant actions are separate from delivery-partner progression.

## Delivery assignment and completion

When an order becomes ready, `delivery.services.assign_ready_order()`:

1. Locks the order and assignment.
2. Expires an overdue offer and records its attempt.
3. Filters partners by online/available status, recent location, no active assignment, and not previously offered.
4. Ranks/selects nearest eligible partner within an expanding radius.
5. Creates/updates assignment and attempt history; notifies relevant users.
6. After configured unsuccessful offers, marks assignment attention needed and notifies customer, restaurant, and admin.

Offers can also be manually assigned by a restaurant; that request is not complete until the partner accepts. Offer timeout is checked during app requests, not by a scheduled worker.

Partner path:

`assigned → accepted → arrived_at_pickup → picked_up → on_the_way → delivered`

`delivery.api_views` delegates actions to `accept_assignment`, `reject_assignment`, and `advance_assignment`. The service validates assignment ownership and legal next state. Customers can cancel before pickup through the restaurant order flow; assignment release/cancellation is handled by the delivery service.

## GPS and tracking

Delivery detail loads `delivery/static/delivery/js/detail.js`; shared `GPSLocationManager` calls `/api/location/delivery/update/` with the active assignment/order identifiers. Backend validates role, coordinates, telemetry and assignment ownership; updates current profile location and throttles history rows.

Customer order detail loads `orders/static/orders/js/order-live-tracking.js`; polls the configured tracking endpoint every 3 seconds. `OrderDeliveryLocationAPIView` checks that the requester is order owner, assigned partner, restaurant owner, or admin/staff, then returns phase, coordinates, freshness, route and ETA fields. The browser renders via `FoodExMap`.

This is periodic polling, not WebSocket streaming. Route quality depends on configured routing and external providers. GPS may be absent, stale, denied, or inaccurate.

## Reviews, notifications, admin, earnings

- Reviews: only a customer's own delivered order may be reviewed; `Review` is one-to-one with an order. Public review listing filters hidden reviews. Partner reply and admin moderation APIs exist.
- Notifications: services write `Notification` records; API/page reads are user-scoped and mark-read endpoints update owner-scoped rows.
- Restaurant approval: admin API manages pending/approved/rejected/suspended status. A source/model-field mismatch in the list endpoint is recorded in [AUTHENTICATION_AND_SECURITY.md](./AUTHENTICATION_AND_SECURITY.md).
- Earnings: delivered orders can create `RestaurantEarning`; APIs provide summary views. `Settlement` exists but no bank transfer or complete settlement processor was verified.
- Django Admin provides direct model management and an order-assignment retry action.

## Features not verified as complete

| Feature | Evidence-based status |
|---|---|
| Live payment capture/refund | Mock/COD ledger code exists; no real provider configured or tested. |
| Automated payout/settlement | Models and summaries exist; transfer/settlement automation not evidenced. |
| Real-time push tracking | HTTP polling is implemented; no WebSocket code found. |
| Background dispatch/timeout worker | None found; progress occurs when requests trigger service calls. |
| Deployed MySQL parity | Not verified; migration state has two pending location-field changes. |
| Visual GPS/map end-to-end behavior | Unit/integration tests pass, but browser permission, tiles, routing and stale GPS were not browser-tested. |
