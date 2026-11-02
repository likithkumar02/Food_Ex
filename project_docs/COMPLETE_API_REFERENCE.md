# Complete API reference

## Conventions and verification boundary

The root router resolves **93 API URL patterns** (93 distinct patterns in this source snapshot, including compatibility/alias and older function-based JSON routes). DRF endpoints accept JSON by default; several account/partner endpoints also allow form and multipart parsing. For session authentication, unsafe requests require CSRF. JWT requests use the configured DRF authentication classes. Unless noted, DRF's global default permission is `IsAuthenticated`.

The actual status/response shapes below are summarized from the view implementations. DRF can additionally return framework-level authentication, parser, and method errors. Request bodies are examples of the fields consumed by code, not a guarantee that every optional field is required. Page routes such as `/orders/checkout/` are **not** JSON API endpoints.

## Accounts and authentication

| Method and URL | Implementation / access | Request and response behavior |
|---|---|---|
| `POST /api/signup/` | `accounts.views.api_signup_view`; public legacy session API. | JSON/form: `username`, `email`, `password` or `password1`; role is fixed to customer. Returns 201 `success/message/user`; duplicate username/email and missing fields return 400; malformed JSON 400. |
| `POST /api/login/` | `accounts.views.api_login_view`; public legacy session API. | `username_or_email`/`username`, `password`; returns session login and `success/message/user`; invalid credentials 401, missing fields 400. |
| `POST /api/forgot-password/` | `accounts.views.api_forgot_password_view`; public. | `{email}`; Django password reset form; returns enumeration-safe success/message; invalid form 400. |
| `POST /api/password/change/` | `accounts.views.api_password_change_view`; Django `login_required`. | `{old_password,new_password,confirm_password}`; JSON success/message or 400 error/errors. Django login-required redirect behavior may differ from a DRF 401. |
| Any HTTP method `/api/profile/` | `accounts.views.api_profile_view`; checks `request.user.is_authenticated`. | Returns `{success:true,user:{id,username,email,first_name,last_name,role}}`; unauthenticated 401. The function does not restrict to GET, despite being read-only. |
| `POST /api/auth/customer/register/` | `RegisterAPIView` with fixed role `customer`; public. | `RegistrationSerializer`: `name,email,phone,password,confirm_password`; validates phone/email/password. 201 `{success,message,role}`; serializer/uniqueness errors 400. |
| `POST /api/auth/restaurant/register/` | `RestaurantRegisterAPIView`; public, fixed `restaurant_owner`. | Also requires restaurant name/type/cuisine/address/city/state/6-digit pincode/phone/FSSAI/bank details/account holder; optional GST/PAN/logo/cover image. Creates pending inactive restaurant. 201 success; invalid/duplicate 400. |
| `POST /api/auth/delivery/register/` | `DeliveryRegisterAPIView`; public, fixed `delivery_partner`. | Also requires vehicle type/number, license number, address. Creates partner profile; 201 success or 400 errors. |
| `POST /api/auth/register/` | `RegisterAPIView`; public generic registration, default customer role. | Same registration serializer; client cannot set privileged role. |
| `POST /api/auth/customer/login/`, `/api/auth/restaurant/login/`, `/api/auth/delivery/login/` | Role-specific `LoginAPIView` subclasses; public. | `{email,password}`. Wrong role/credentials return 401 serializer errors. Success returns `{success,message,access,refresh,user:{id,name,email,phone,role,profile_image,address}}`. |
| `POST /api/auth/login/` | General `LoginAPIView`; public. | `{email,password}`; issues JWTs and session login for authenticated user role. |
| `POST /api/auth/token/refresh/` | Simple JWT `TokenRefreshView`; public token endpoint. | Simple JWT refresh request/response fields; exact validation/error shape follows installed Simple JWT configuration. |
| `GET/PUT/DELETE /api/auth/profile/` | `ProfileAPIView`; authenticated. | GET returns `profile_payload`; PUT accepts partial `name,email,phone,address,profile_image` as JSON/form/multipart; serializer errors 400. DELETE removes current account except superuser (400); success `{success,message}`. |
| `POST/DELETE /api/auth/delete-account/` | `DeleteAccountAPIView`; authenticated alias to profile deletion. | Same superuser guard and deletion response. |
| `POST /api/auth/logout/` | `LogoutAPIView`; authenticated. | Optional `{refresh,role}`. Refresh token must belong to current user; invalid token 400. Blacklists refresh when provided, clears role session, returns success/message. |
| `POST /api/auth/customer/logout/`, `/api/auth/delivery/logout/` | Role-specific logout subclasses; authenticated. | Same optional refresh token semantics; role fixed by route. |

`profile_payload()` ensures a `CustomerProfile` exists, so profile GET can write a profile row. API login creates server-side session state in addition to JWT tokens.

## Administrator

All endpoints below use `AdminAPIView`, which requires `IsAuthenticated` and `request.user.role == "admin"`. Most write methods are atomic.

| Method and URL | View | Input/output |
|---|---|---|
| `GET /api/admin/restaurants/?status=&q=` | `AdminRestaurantListAPIView` | Returns `{count,items:[...]}` up to 200 rows. **Current implementation references restaurant properties absent from `Restaurant` (`cuisine`, `fssai_license_no`); treat response as broken until corrected and tested.** |
| `POST /api/admin/restaurants/<restaurant_id>/<action>/` | `AdminRestaurantActionAPIView` | Action `approve`, `reject`, or `suspend`; reject requires `reason` length ≥2, suspend accepts optional reason. Returns status/active/reviewed fields; invalid action/reason 400; missing restaurant 404. |
| `POST /api/admin/restaurants/<restaurant_id>/commission/` | `AdminRestaurantCommissionAPIView` | `commission_percent` decimal or null/empty (platform default); invalid number 400; value clamps to 0–90. Returns effective rate and default flag. |
| `GET/PATCH /api/admin/platform/settings/` | `AdminPlatformSettingsAPIView` | GET returns commission, GST, delivery fee and timestamp. PATCH updates supplied settings; validates numbers and bounds (commission 0–90, GST 0–100; delivery fee nonnegative). |
| `POST /api/admin/reviews/<review_id>/moderate/` | `AdminReviewModerateAPIView` | Review moderation data; admin-only. Exact accepted fields and response are defined in this view; invalid/missing review or payload yields DRF/404/400 response. |

## Restaurant discovery and menu

Public read APIs explicitly use `AllowAny`. Owner management routes require authentication and resolve the owner from the authenticated user. Partner routes inherit `PartnerAPIView`, which rejects non-restaurant owners or owners without a restaurant.

| Method and URL | View | Request/response summary |
|---|---|---|
| `GET /api/restaurants/?q=` | `RestaurantListAPIView` | Returns serialized approved/active restaurants; optional text search across restaurant/menu fields. |
| `GET /api/restaurants/<restaurant_id>/` | `RestaurantDetailAPIView` | Public active/approved detail with menu prefetch; missing/ineligible restaurant 404. |
| `GET /api/restaurants/<restaurant_id>/menu/` | `RestaurantMenuAPIView` | Public available items ordered by category/name. |
| `GET /api/restaurants/nearby/` | `location.api_views.NearbyRestaurantsAPIView` | Nearby search parameters are handled by location service; see Location section. |
| `GET/POST /api/restaurants/manage/menu/` | `RestaurantMenuManageAPIView` | Owner's menu list; POST serialized menu item fields, 201 item JSON; missing owner restaurant 404, validation errors 400. |
| `PUT/PATCH/DELETE /api/restaurants/manage/menu/<item_id>/` | `RestaurantMenuItemManageAPIView` | Owner-scoped menu item; PUT full update, PATCH partial, DELETE 204; missing/not-owned item 404. |
| `GET /api/restaurants/partner/dashboard/` | `PartnerDashboardAPIView` | Aggregates order counts/status/revenue, menu metrics, 30-day analytics, earnings and latest orders. |
| `GET/PATCH /api/restaurants/partner/profile/` | `PartnerProfileAPIView` | Owner profile read/update through `RestaurantProfileUpdateSerializer`; profile/file validation errors 400. |
| `POST /api/restaurants/partner/profile/toggle-open/` | `PartnerProfileToggleOpenAPIView` | Toggles owner restaurant open state; response reflects current setting. |
| `GET/POST /api/restaurants/partner/categories/` | `PartnerCategoryListAPIView` | List or create restaurant-owned menu category. |
| `GET/PATCH/DELETE /api/restaurants/partner/categories/<category_id>/` | `PartnerCategoryDetailAPIView` | Owner-scoped category read/update/delete; not-found/other-owner is 404. |
| `GET/POST /api/restaurants/partner/menu/` | `PartnerMenuListAPIView` | List/create partner menu items using partner serializers. |
| `GET/PATCH/DELETE /api/restaurants/partner/menu/<item_id>/` | `PartnerMenuDetailAPIView` | Owner-scoped item detail/update/delete. |
| `GET /api/restaurants/partner/timings/` | `PartnerTimingListAPIView` | List weekly operating times. |
| `PUT /api/restaurants/partner/timings/bulk/` | `PartnerTimingBulkAPIView` | Validated bulk timing update; serializer enforces structure and day rules. |
| `GET/POST /api/restaurants/partner/documents/` | `PartnerDocumentListAPIView` | List/upload restaurant documents; multipart supported and file validation applied. |
| `GET /api/restaurants/partner/orders/`, `GET /api/restaurant/orders/` | `PartnerOrderListAPIView` | Owner-scoped order list; second path is compatibility alias. |
| `GET /api/restaurants/partner/orders/<order_id>/`, `GET /api/restaurant/orders/<order_id>/` | `PartnerOrderDetailAPIView` | Owner-scoped detail/payload; compatibility alias exists. |
| `POST /api/restaurants/partner/orders/<order_id>/<action>/`, `POST /api/restaurant/orders/<order_id>/<action>/` | `PartnerOrderActionAPIView` | Order action path parameter; delegates to `transition_restaurant_order`; invalid action/state/owner returns validation/permission error. |
| `GET/POST /api/restaurants/partner/offers/` | `PartnerOfferListAPIView` | List/create offers; write serializer validates offer fields. |
| `GET/PATCH/DELETE /api/restaurants/partner/offers/<offer_id>/` | `PartnerOfferDetailAPIView` | Owner-scoped offer detail/update/delete. |
| `GET /api/restaurants/partner/reviews/` | `PartnerReviewListAPIView` | Owner restaurant reviews. |
| `POST /api/restaurants/partner/reviews/<review_id>/reply/` | `PartnerReviewReplyAPIView` | Validated reply for review belonging to owner restaurant. |
| `GET /api/restaurants/partner/earnings/` | `PartnerEarningsAPIView` | Earning summary/records; no transfer is performed by reading it. |
| `GET /api/restaurants/partner/payments/` | `PartnerPaymentsAPIView` | Payment/settlement summary from domain aggregates. |
| `GET /api/restaurants/partner/notifications/` | `PartnerNotificationListAPIView` | Owner-specific notification feed. |
| `POST /api/restaurants/partner/notifications/<notification_id>/read/` | `PartnerNotificationReadAPIView` | Marks owner-scoped notification read. |

## Customer reviews

| Method and URL | View / access | Request/response |
|---|---|---|
| `GET /api/customer/restaurants/<restaurant_id>/reviews/` | `RestaurantReviewListAPIView`, public. | Returns serialized non-hidden reviews for an active restaurant. |
| `POST /api/customer/restaurants/<restaurant_id>/reviews/create/` | `ReviewCreateAPIView`, authenticated customer only. | `{order_id,rating,comment?}`. Order must be owned by user, match restaurant, be delivered, and not already reviewed. Success 201 serialized review; invalid serializer 400, invalid state/duplicate 409, inaccessible order 404. |

## Cart and orders

All routes require authentication and additionally enforce customer role (the order-detail APIs scope rows to current user).

| Method and URL | View | Request/response |
|---|---|---|
| `GET /api/cart/` | `CartAPIView.get` | `{items:[{id,menu_item_id,name,restaurant,restaurant_id,quantity,unit_price,subtotal}],total_items,subtotal}`. Creates an empty cart if absent. |
| `POST /api/cart/` | `CartAPIView.post` | `{menu_item_id,quantity?}`; quantity 1–20; item and restaurant must be available/approved/open; one-restaurant cart only. 201 `{id,quantity}`, 400 validation, 403 role, 404 item, 409 other restaurant. |
| `PATCH /api/cart/items/<item_id>/` | `CartItemAPIView.patch` | `{quantity}` 1–20; returns `{id,quantity,subtotal}`; invalid/missing/other user's item returns 400/404. |
| `DELETE /api/cart/items/<item_id>/` | `CartItemAPIView.delete` | Deletes only current user's item; 204 or 404. |
| `GET /api/cart/summary/?offer_code=` | `CheckoutSummaryAPIView.get` | Server-calculated `{subtotal,discount_amount,tax_amount,delivery_fee,total_price,offer,offer_error}`. |
| `GET /api/orders/` | `OrderListCreateAPIView.get` | Current customer's serialized orders with item snapshots. |
| `POST /api/orders/` | `OrderListCreateAPIView.post` | `OrderCreateSerializer`: `delivery_address?`, `address_id?`, paired `delivery_latitude`/`delivery_longitude?`, `offer_code?`. Calls atomic order service; success 201 `OrderSerializer`; validation/business error 400. |
| `GET /api/orders/<order_id>/` | `OrderDetailAPIView.get` | Current user's order JSON; other user's/missing order 404. |
| `GET /api/orders/<order_id>/status/` | `OrderStatusAPIView.get` | Owner-only status/timeline/partner/latest location. It may trigger ready-order dispatch before composing response. |
| `GET /api/orders/<order_id>/delivery-location/` | `location.api_views.OrderDeliveryLocationAPIView.get` | Compatibility tracking URL; owner/partner/restaurant/admin scoped; phase/location/route/ETA payload. |
| `GET /api/orders/<order_id>/tracking/` | Same tracking view | Alias of order tracking endpoint. |
| `GET /api/orders/<order_id>/route/` | `location.api_views.OrderRouteAPIView.get` | Authorized route/waypoint payload. |

## Payments

| Method and URL | View / access | Request/response |
|---|---|---|
| `POST /api/payments/orders/<order_id>/pay/` | `OrderPaymentAPIView.post`; authenticated customer, order scoped to owner. | `{payment_method:"cod"|"test"|...}`. 201 `{payment_id,status,payment_method,transaction_id}`. Cancelled order and unconfigured method return 400; wrong role 403; order not found 404. `test` succeeds only with mock provider. |

## Delivery

All routes are authenticated. The views additionally require delivery-partner role and scope assignment/history to the partner. Availability route supplies online/offline in URL kwargs.

| Method and URL | View | Request/response |
|---|---|---|
| `GET /api/delivery/dashboard/` | `DeliveryDashboardAPIView` | Partner summary and assignment payloads. |
| `POST /api/delivery/online/`, `/api/delivery/offline/` | `DeliveryAvailabilityAPIView` | Sets availability using route boolean; may dispatch ready orders. |
| `GET /api/delivery/requests/` | `DeliveryRequestListAPIView` | Current partner's pending offer feed; refreshes/expels expired offers as implemented. |
| `POST /api/delivery/requests/<assignment_id>/accept/` | `DeliveryAssignmentActionAPIView` | Calls service accept; returns assignment payload or business error. |
| `POST /api/delivery/requests/<assignment_id>/reject/` | Same action view | Optional rejection reason; service records attempt and can reassign. |
| `POST /api/delivery/<assignment_id>/arrived-at-pickup/` | `AdvanceDeliveryAPIView` | Advances only legal next status. |
| `POST /api/delivery/<assignment_id>/pickup/` | Same | Requires arrived-at-pickup state. |
| `POST /api/delivery/<assignment_id>/out-for-delivery/` | Same | Requires pickup first. |
| `POST /api/delivery/<assignment_id>/complete/` | Same | Completes assigned delivery and performs applicable COD/earning updates. |
| `POST /api/delivery/location/` | `DeliveryLocationAPIView` | Delivery-specific location path; body/behavior is in `delivery/api_views.py`. |
| `POST /api/delivery/location/update/` | `location.api_views.DeliveryLocationUpdateAPIView` | Compatibility update path; see Location section. |
| `GET /api/delivery/history/` | `DeliveryHistoryAPIView` | Partner-scoped completed/history assignments. |

## Notifications

| Method and URL | View / access | Request/response |
|---|---|---|
| `GET /api/notifications/` | `NotificationListAPIView.get`; authenticated. | `{unread_count,results:[{id,category,title,message,link,is_read,created_at}]}`; results capped at 50 and scoped to requester. |
| `PATCH /api/notifications/<notification_id>/read/` | `NotificationReadAPIView.patch`; authenticated. | Marks only own notification read and returns serialized notification; other/missing row 404. |

## Location, GPS, nearby search

| Method and URL | View / access | Request/response notes |
|---|---|---|
| `GET /api/location/detect/?lat=&lon=` | `DetectLocationAPIView`; check endpoint permission in source. | Coordinate input; optional reverse-geocode fields and success/error result. |
| `POST /api/location/customer/update/` | `CustomerLocationUpdateAPIView`; authenticated customer or staff. | `latitude,longitude`, optional `accuracy,reverse_geocode`; saves `CustomerProfile`; coordinate/accuracy errors 400, wrong role 403. |
| `GET/POST /api/location/customer/addresses/` | `CustomerSavedAddressesAPIView`; authenticated. | GET current user's saved addresses. POST accepts address text/parts, optional coordinate pair/default flag; returns 201 address or 400. Code filters records by user; it does not explicitly reject non-customer roles. |
| `PATCH/DELETE /api/location/customer/addresses/<address_id>/` | `CustomerAddressDetailAPIView`; authenticated, row scoped to user. | Partial address edit or delete; missing/not-owned row 404. |
| `GET/POST /api/location/restaurant/update/` | `RestaurantLocationUpdateAPIView`; owner-scoped. | GET current restaurant coordinates/address; POST validated location/address update; errors use JSON response. |
| `POST /api/location/delivery/update/` | `DeliveryLocationUpdateAPIView`; authenticated delivery partner or staff. | `latitude,longitude`, optional accuracy/speed/heading and assignment/order IDs. Validates finite/range values, active assignment and ownership. Wrong role/partner 403; malformed data 400; missing assignment 404; completed assignment 410. |
| `GET /api/restaurants/nearby/`, `/api/location/restaurants/nearby/`, `/api/location/nearby/restaurants/` | `NearbyRestaurantsAPIView`; route aliases. | Location/query/cuisine/state/district/city/area/radius arguments are interpreted by location service; returns nearby restaurant results. |
| `GET /api/location/nearby/delivery-partners/` | `NearbyDeliveryPartnersAPIView`; permission is view-defined. | Nearby eligible partner list; protect location/contact details and validate search inputs. |
| `GET /api/location/orders/<order_id>/delivery-location/`, `/api/orders/<order_id>/delivery-location/`, `/api/orders/<order_id>/tracking/` | `OrderDeliveryLocationAPIView`; authenticated with explicit ownership/role check. | Tracking phase, status timestamps, partner info, coordinates/freshness, route, distance and ETA. Unauthorized user 403; missing order 404. |
| `GET /api/location/orders/<order_id>/route/`, `/api/orders/<order_id>/route/` | `OrderRouteAPIView`; authenticated with owner/partner/restaurant/admin check. | Returns route/waypoint fields based on current order/assignment. |
| `GET /api/location/admin/live/` | `AdminLiveGPSAPIView`; admin/staff permission. | Admin metrics, active deliveries, restaurants and partner coordinates; sensitive response. |

## Page routes are not APIs

Examples: `/customer/`, `/restaurants/<id>/`, `/orders/cart/`, `/orders/checkout/`, `/delivery/dashboard/`, `/location/customer/`, and `/payments/orders/<id>/payment/` return HTML/redirects. They are defined in app page URL modules and use Django forms/session permissions. Their POST forms may create or update records but should not be documented as JSON REST APIs.

## Test suggestions

Use the endpoint-specific Django tests listed in [TESTING_AND_DEBUGGING.md](./TESTING_AND_DEBUGGING.md). For manual API checks, use a test account and a disposable database; never paste real JWTs into source/docs. For every endpoint, test success, invalid body, anonymous request, wrong role, foreign object ID, and terminal state as applicable.
