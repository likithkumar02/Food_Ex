# Django backend functions and symbols

## Reading this index

This guide covers executable Django backend modules and points to their symbols. Line numbers refer to the audited source snapshot and may move when source changes. The syntax inventory included migrations and tests; this symbol guide focuses on runtime source, with test and migration files described separately in [COMPLETE_FILE_STRUCTURE.md](./COMPLETE_FILE_STRUCTURE.md).

Common patterns:

- Page functions accept a `request`, query models, then return `render`, `redirect`, or a response.
- DRF classes inherit `APIView`; methods use `request.data`/query params, serializers, ORM operations, and `Response`.
- `role_required(...)`, `IsAuthenticated`, and explicit owner filters provide access checks. DRF global defaults are in `food_ex/settings/base.py`.
- Domain services hold reusable business rules; views should be read alongside the corresponding service.

## Settings, URL routing, and shared project

| File / symbols | Purpose, input/output, and important dependencies |
|---|---|
| `food_ex/settings/base.py`: `env_list(name, default="")` | Splits a comma-separated environment variable into trimmed nonempty values. Used for host/CORS settings. `BASE_DIR`, `DATABASES`, `AUTH_USER_MODEL`, `REST_FRAMEWORK`, `SIMPLE_JWT`, template/static/media settings are module configuration rather than callable service APIs. |
| `food_ex/settings/dev.py`, `prod.py` | Import `base.py` then set environment-specific `DEBUG`, hosts, CSRF, and CORS values. Production mode does not itself configure a live payment provider or external database. |
| `food_ex/urls.py` | Root route composition. Includes app URL modules and appends media-serving routes only with `DEBUG`. |
| `food_ex/views.py`: `home(request)` | Reads state/district query parameters; filters approved active restaurants and available menu items; renders `home.html` with cards/count/location. Uses `Restaurant`, `MenuItem`, `Q`, and remote fallback image URLs. |
| `manage.py`: `main()` | Sets up and invokes Django's command-line utility. |

## Accounts and role sessions

| File / symbols | Purpose and execution flow |
|---|---|
| `accounts/models.py`: `User.__str__` | Display username plus role; model extends `AbstractUser`, adding unique email and role choices. |
| `accounts/forms.py`: `UserRegistrationForm.save(commit=True)` | Creates user through Django's user manager, hashes password, and saves only when requested. |
| `accounts/serializers.py`: `RegistrationSerializer.validate_email`, `validate_phone`, `validate`, `create` | Checks email/phone uniqueness and role/profile data; creates a password-hashed user plus role-specific profiles, including restaurant/delivery profile data where applicable. |
| `accounts/serializers.py`: `LoginSerializer.validate` | Authenticates credentials and enforces a requested role when passed by role-specific endpoints. |
| `accounts/serializers.py`: `ProfileUpdateSerializer.validate_email`, `validate_phone`, `validate_profile_image`, `update` | Validates profile data and applies updates to user/customer profile. |
| `accounts/session_utils.py`: `login_role_user(request,user,role)` | Persists role-specific session identity and performs Django login/session setup. |
| `accounts/session_utils.py`: `logout_role_user(request,role)` | Clears only the selected role session and updates the request's active-role state. |
| `accounts/session_utils.py`: `get_active_roles(request)` | Reports role sessions active in the request. |
| `accounts/middleware.py`: `_resolve_role_user(request,role)` | Resolves a role's session user from a session ID, then a matching standard authenticated user; memoizes it on the request. The current implementation treats ORM errors as anonymous via a broad exception; this can obscure database/session failures. |
| `accounts/middleware.py`: `RoleSessionMiddleware.__init__`, `__call__` | Wraps request handling, adds lazy `customer_user`, `delivery_user`, `restaurant_user`, and selects `request.user` according to path/portal context. |
| `accounts/decorators.py`: `role_required(role)` | Decorator factory used by page views to require a role and redirect/deny when the request user is not eligible. |
| `accounts/views.py`: `register_view`, `login_view`, `portal_login_view`, `portal_register_view` | Browser account workflows; role-specific portal config is server-controlled. Restaurant registration validates a restaurant form; delivery registration captures vehicle/license/address data. |
| `accounts/views.py`: `customer_portal_view`, `restaurant_portal_view`, `delivery_portal_view` | Render storefront or role portal shell; logged-in partner roles are sent to their dashboard. |
| `accounts/views.py`: `customer_logout_view`, `delivery_logout_view`, `logout_view` | POST-based logout and role selection/redirect. |
| `accounts/views.py`: `forgot_password_view`, `settings_view`, `delete_account_view`, `password_change_view` | Password reset/change, account profile settings and confirmation/deletion paths. Uses Django password reset/change forms and validators. |
| `accounts/views.py`: `api_signup_view`, `api_login_view`, `api_forgot_password_view`, `api_password_change_view`, `api_profile_view` | Legacy function-based JSON routes. These are separate from the DRF JWT endpoints and use Django session login/authentication. |
| `accounts/views.py`: `dashboard_view`, `customer_dashboard_view`, `_customer_restaurants_for_state`, `restaurant_dashboard_view`, `delivery_dashboard_view`, `admin_dashboard_view` | Redirects or assembles dashboard context from each role's domain models/services. |
| `accounts/api_views.py`: `profile_payload(user,request)` | Ensures `CustomerProfile`, builds an absolute image URL when present, returns user/profile JSON. |
| `accounts/api_views.py`: `RegisterAPIView.post`; `RestaurantRegisterAPIView`, `DeliveryRegisterAPIView` | Public registration using a fixed class role, serializer validation, atomic save, and integrity error response. Subclasses choose server-side role rather than trusting client-supplied role. |
| `accounts/api_views.py`: `LoginAPIView.post`; role-specific subclasses | Validates credentials/role, establishes role login, issues Simple JWT access/refresh tokens and profile JSON. |
| `accounts/api_views.py`: `ProfileAPIView.get/put/delete`, `DeleteAccountAPIView.post/delete` | Authenticated profile read/update and account deletion. Blocks deleting a superuser; logs out and deletes the current user. |
| `accounts/api_views.py`: `LogoutAPIView.post`, customer/delivery subclasses | Optionally blacklists a refresh token after checking its user ID; clears a role session. |
| `accounts/admin_views.py`: `_clamp`, `AdminForbidden`, `AdminAPIView.dispatch` | Clamp decimal setting values, represent admin-only 403, and guard admin APIs by authenticated `role == "admin"`. |
| `accounts/admin_views.py`: `AdminRestaurantListAPIView.get`, `AdminRestaurantActionAPIView.post`, `AdminRestaurantCommissionAPIView.post` | List/search and approve/reject/suspend restaurants; adjust commission under row locks and transactions. **The list implementation references `Restaurant.cuisine`, `Restaurant.fssai_license_no`, and other names that do not match current model fields (`cuisine_type`, `fssai_number`); verify/fix only after approval.** |
| `accounts/admin_views.py`: `AdminPlatformSettingsAPIView.get/patch`, `AdminReviewModerateAPIView.post` | Read/update platform commission/GST/delivery fee and moderate reviews. |

## Customer and restaurant backend

| File / symbols | Purpose and dependencies |
|---|---|
| `customer/models.py`: `CustomerProfile.__str__`, `CustomerAddress.__str__` | Profile and per-user saved-address display labels. |
| `customer/models.py`: `Review.stars`, `clean`, `save`, `__str__` | Generates star characters; validates 1–5 rating, order ownership, restaurant match, delivered status; `save()` calls `full_clean()`. |
| `customer/serializers.py`: `ReviewSerializer.get_customer_name`, `ReviewCreateSerializer` | Exposes review data and validates review submission fields. |
| `customer/api_views.py`: `RestaurantReviewListAPIView.get` | Public list of non-hidden reviews for active restaurant. |
| `customer/api_views.py`: `ReviewCreateAPIView.post` | Authenticated customer-only review; locks/loads own delivered order, prevents duplicate review, then creates the record in an atomic transaction. |
| `customer/views.py`: `customer_profile_view`, `order_review_view` | Profile/order-review pages and form submissions. |
| `restaurant/fields.py`: `EncryptedCharField._cipher`, `get_prep_value`, `from_db_value` | Encrypts before database storage and decrypts on database read. Encryption-key configuration and rotation are operational requirements. |
| `restaurant/forms.py`: `validate_restaurant_image_size`; `RestaurantRegistrationForm.clean_*`; `RestaurantProfileForm.clean_*`; `RestaurantOwnerAccountForm.clean_*` | Validates upload size, business IDs/bank IFSC, pincode, account email/mobile and profile fields. |
| `restaurant/models.py`: `quantize_money`; `PlatformSetting.save/load`; `Restaurant.is_approved/commission_rate/accepts_orders/average_rating`; menu/category/offer properties and `clean/save` | Model business helpers. `PlatformSetting.load()` obtains the singleton-style record; restaurant properties are used by listing, order and commission calculations. `MenuItem.save()` applies model-level validation. |
| `restaurant/serializers.py`: `validate_upload`, `absolute_url`, serializers and `validate_*` methods | API input validation and model-to-JSON representation for menu/profile/offer/timing/document/earning/review/order/notification data. See the symbol index below for every serializer class. |
| `restaurant/api_views.py`: restaurant read APIs and `owned_restaurant` | Public list/detail/menu endpoints; `owned_restaurant(user)` only resolves an owner-role user's restaurant; management APIs filter item IDs by that restaurant before mutation. |
| `restaurant/partner_api_views.py`: `get_owned_restaurant_or_403`, `partner_context`, `build_order_payload`, `PartnerAPIView.initial` | Shared owner scoping and order payload formatting. Base `initial()` rejects non-owner/missing restaurant before partner API method execution. |
| `restaurant/partner_api_views.py`: `PartnerDashboardAPIView.get` through `PartnerNotificationReadAPIView.post` | Dashboard aggregations, profile/menu/category/timing/document/order/offer/review/earning/payment/notification surfaces. Writes use partner-scoped model lookups and serializers; order actions call `transition_restaurant_order`. |
| `restaurant/services.py`: `record_order_earning`, `cancel_order_earning`, `restaurant_earnings_queryset`, `earnings_summary`, `payments_summary`, `restaurant_analytics` | Server-side payout split and aggregate summaries. The earning function only records delivered orders; it does not transfer money. |
| `restaurant/views.py`: `restaurant_list_view`, `restaurant_listing_context`, `restaurant_detail_view`, `restaurant_management_view`, `restaurant_account_settings_view` | Storefront filtering and restaurant pages. Listing combines query parameters/profile/session/cookie location, then filters approved active restaurants and menu data. |

## Orders, payment, delivery, location, and notification services

| File / symbols | Purpose and important behavior |
|---|---|
| `orders/models.py`: cart/order methods | `Cart.total_items/total_price`, `CartItem.subtotal`, `Order.save/_generate_code`, live/closed/payment/customer properties, `OrderItem.save/subtotal`. Order items snapshot item name and unit price at purchase. |
| `orders/serializers.py`: `OrderItemSerializer`, `OrderSerializer`, `OrderCreateSerializer.validate/validate_delivery_address` | Read-only order/item JSON and address/coordinate/offer validation. |
| `orders/services.py`: `_money`, `compute_order_totals`, `resolve_offer`, `create_order_from_cart` | Decimal-safe server totals, offer validation, and atomic order creation. It locks the cart, validates restaurant/orderability/coordinates/availability/quantity/minimum amount, creates order/status/item snapshots, increments offer use, and empties the cart. |
| `orders/services.py`: `_assert_order_is_paid`, `transition_restaurant_order`, `record_order_status_event`, `_refund_if_prepaid`, `_cancel_order_earning` | Enforces legal status changes, authorization/payment requirements, timestamps, status audit events, payment refund and earning cancellation hooks. |
| `orders/api_views.py`: `customer_only`, `cart_payload`; `CartAPIView`, `CartItemAPIView`, `CheckoutSummaryAPIView`, `OrderListCreateAPIView`, `OrderDetailAPIView`, `OrderStatusAPIView` | Customer JSON APIs. Cart/order ownership is scoped to the requester; cart POST checks active restaurant/menu availability and uses transactions/row locks. `OrderStatusAPIView` can trigger assignment refresh as a side effect. |
| `orders/views.py`: `cart_view`, `add_to_cart_view`, `cart_item_update_view`, `checkout_view`, `order_detail_view`, `order_history_view`, `restaurant_order_management_view`, `order_assign_delivery_partner_view`, `order_accept_view`, `order_reject_view`, `order_cancel_view`, `order_preparing_view`, `order_ready_view` | Page-form implementation of cart/checkout/order and restaurant lifecycle. Most mutations are `require_POST`; calls the order and delivery services. |
| `payments/services.py`: `PaymentProcessingError`, `MockPaymentProvider.charge/refund`, `get_provider`, `PaymentService.process/_notify_restaurant_of_new_order`, `refund_order_payments` | Locks the order and avoids duplicate paid/COD rows; COD remains pending; development `test` creates a generated mock reference; other unconfigured methods fail. Refunds update ledger status and notify parties but mock refund is not a real transfer. |
| `payments/api_views.py`: `OrderPaymentAPIView.post`; `payments/views.py`: `payment_page` | Customer-owned order payment API and server-rendered payment form. |
| `delivery/services.py`: `_distance_to_restaurant`, `_notify_waiting_for_delivery`, `_notify_assignment_failed`, `_set_order_status`, `_expire_pending_offer`, `assign_ready_order`, `dispatch_ready_orders`, `manually_assign_delivery_partner`, `retry_delivery_assignment`, `refresh_partner_offers`, `cancel_order_assignment`, `accept_assignment`, `reject_assignment`, `advance_assignment`, `_settle_cash_on_delivery` | Core assignment and delivery state machine. See [FEATURE_BY_FEATURE_WORKFLOW.md](./FEATURE_BY_FEATURE_WORKFLOW.md); assignment uses row locks, distance and freshness, availability, retry attempts, and transition restrictions. |
| `delivery/api_views.py`: `is_delivery_partner`, `assignment_payload`, dashboard/availability/request/action/advance/location/history views | Role-scoped delivery JSON endpoints. Assignment querysets are partner-filtered; advancement delegates to `delivery.services`. |
| `delivery/views.py`: `delivery_dashboard_view`, `delivery_detail_view`, `assign_delivery_view`, `delivery_availability_view`, `accept_delivery_view`, `reject_delivery_view`, `update_delivery_status_view` | Session-authenticated delivery pages and POST actions. |
| `location/services.py`: `calculate_distance`, `calculate_eta`, `validate_coordinates`, `reverse_geocode`, `check_restaurant_geofence`, `get_road_route`, `get_nearby_restaurants` | Coordinate validation and geographic calculations; optional third-party geocoding/road route; nearby restaurant database query. |
| `location/api_views.py`: `IsAdmin.has_permission`; customer/address/restaurant/delivery update APIs; nearby/order tracking/route/admin/detect APIs | Validates location and role/ownership, serializes nearby/tracking payloads, and returns JSON. `OrderDeliveryLocationAPIView` permits order owner, assigned partner, restaurant owner, and admin/staff; unrelated users receive 403. |
| `location/views.py`: admin/customer/restaurant location views | Role-protected HTML pages for map and address tasks. |
| `location/models.py`: `LocationSetting.save/load` | Enforces singleton name and lazily creates default settings. Current model defaults for tile URL/attribution are not synchronized to migrations. |
| `notifications/services.py`: `notify_user` | Shared notification creation helper. |
| `notifications/api_views.py`: `serialize_notification`, list/read API methods | Returns only current user's notifications, capped at 50, and updates read state only on the owner's row. |
| `notifications/views.py`: `notification_center_view`, `mark_notification_read_view` | Page display/read-state actions. |

## Test, admin, and command modules

- `*/tests.py` files define Django `TestCase` classes and integration checks. 174 tests passed in this audit run; see [TESTING_AND_DEBUGGING.md](./TESTING_AND_DEBUGGING.md).
- `*/admin.py` modules register models and admin actions; `orders.admin.retry_delivery_assignment_action` is a staff/admin retry route through Django Admin.
- `restaurant/management/commands/seed_demo_data.py` defines `Command.add_arguments`, `handle`, and internal seed helpers. It writes demo fixtures if explicitly run; it was not run during the audit.
- No runtime `signals.py`, `tasks.py`, Channels consumer, or Celery task module was found in the application source inventory.

## Compact runtime symbol index

The AST-based index located 821 Python class/function symbols when tests and migrations are included (261 classes, 560 function/method definitions). The following runtime files contain the main functions discussed above:

```text
accounts: admin_views.py, api_views.py, decorators.py, forms.py, middleware.py,
          models.py, serializers.py, session_utils.py, views.py
customer: api_views.py, models.py, serializers.py, views.py
delivery: api_views.py, models.py, services.py, views.py
food_ex: settings/base.py, views.py
location: api_views.py, models.py, services.py, views.py
notifications: api_views.py, models.py, services.py, views.py
orders: api_views.py, models.py, serializers.py, services.py, views.py
payments: api_views.py, models.py, services.py, views.py
restaurant: api_views.py, fields.py, forms.py, models.py, partner_api_views.py,
            serializers.py, services.py, views.py
```

Treat this as a map, not a substitute for reading implementation. Start with `orders/services.py`, `delivery/services.py`, `payments/services.py`, and `location/api_views.py` to understand the most consequential stateful behavior.

## Definition index

The appendix below is generated from every in-scope Python source file, including tests and migrations. It lists exact class/function names, parameter names, and source line numbers. It is an index, not a replacement for the behavior explanations above; each symbol's caller and side effects depend on its surrounding implementation. The generator excludes `.env`, database exports, virtual environments, uploaded media, and generated files.

Indexed 157 Python files: **261 classes** and **560 function/method definitions**.

### `accounts/admin_views.py`

- L19: `_clamp(value, bounds)`
- L28: `AdminForbidden` ? class
- L29: `AdminForbidden.__init__(self, detail)`
- L33: `AdminAPIView` ? class
- L36: `AdminAPIView.dispatch(self, request, *args, **kwargs)`
- L46: `AdminRestaurantListAPIView` ? class
- L49: `AdminRestaurantListAPIView.get(self, request)`
- L87: `AdminRestaurantActionAPIView` ? class
- L91: `AdminRestaurantActionAPIView.post(self, request, restaurant_id, action)`
- L141: `AdminRestaurantCommissionAPIView` ? class
- L143: `AdminRestaurantCommissionAPIView.post(self, request, restaurant_id)`
- L179: `AdminPlatformSettingsAPIView` ? class
- L180: `AdminPlatformSettingsAPIView.get(self, request)`
- L190: `AdminPlatformSettingsAPIView.patch(self, request)`
- L242: `AdminReviewModerateAPIView` ? class
- L244: `AdminReviewModerateAPIView.post(self, request, review_id)`

### `accounts/api_views.py`

- L18: `profile_payload(user, request)`
- L36: `RegisterAPIView` ? class
- L42: `RegisterAPIView.post(self, request)`
- L70: `RestaurantRegisterAPIView` ? class
- L74: `DeliveryRegisterAPIView` ? class
- L78: `LoginAPIView` ? class
- L83: `LoginAPIView.post(self, request)`
- L109: `RestaurantLoginAPIView` ? class
- L113: `CustomerLoginAPIView` ? class
- L117: `DeliveryLoginAPIView` ? class
- L121: `ProfileAPIView` ? class
- L125: `ProfileAPIView.get(self, request)`
- L128: `ProfileAPIView.put(self, request)`
- L140: `ProfileAPIView.delete(self, request)`
- L158: `DeleteAccountAPIView` ? class
- L161: `DeleteAccountAPIView.post(self, request)`
- L164: `DeleteAccountAPIView.delete(self, request)`
- L168: `LogoutAPIView` ? class
- L172: `LogoutAPIView.post(self, request)`
- L197: `CustomerLogoutAPIView` ? class
- L201: `DeliveryLogoutAPIView` ? class

### `accounts/apps.py`

- L4: `AccountsConfig` ? class

### `accounts/decorators.py`

- L6: `role_required(*roles)`
- L7: `role_required.decorator(view_func)`

### `accounts/forms.py`

- L7: `UserRegistrationForm` ? class
- L13: `UserRegistrationForm.Meta` ? class
- L25: `UserRegistrationForm.save(self, commit)`

### `accounts/middleware.py`

- L39: `_resolve_role_user(request, role)`
- L68: `RoleSessionMiddleware` ? class
- L75: `RoleSessionMiddleware.__init__(self, get_response)`
- L78: `RoleSessionMiddleware.__call__(self, request)`

### `accounts/migrations/0001_initial.py`

- L9: `Migration` ? class

### `accounts/migrations/0002_alter_user_email.py`

- L6: `Migration` ? class

### `accounts/models.py`

- L5: `User` ? class
- L21: `User.__str__(self)`

### `accounts/serializers.py`

- L16: `RegistrationSerializer` ? class
- L51: `RegistrationSerializer.validate_email(self, value)`
- L57: `RegistrationSerializer.validate_phone(self, value)`
- L65: `RegistrationSerializer.validate(self, attrs)`
- L132: `RegistrationSerializer.create(self, validated_data)`
- L180: `LoginSerializer` ? class
- L184: `LoginSerializer.validate(self, attrs)`
- L202: `ProfileUpdateSerializer` ? class
- L209: `ProfileUpdateSerializer.validate_email(self, value)`
- L216: `ProfileUpdateSerializer.validate_phone(self, value)`
- L225: `ProfileUpdateSerializer.validate_profile_image(self, value)`
- L230: `ProfileUpdateSerializer.update(self, user, validated_data)`

### `accounts/session_utils.py`

- L7: `login_role_user(request, user, role)`
- L32: `logout_role_user(request, role)`
- L63: `get_active_roles(request)`

### `accounts/tests.py`

- L18: `UserRoleTests` ? class
- L19: `UserRoleTests.test_user_roles_are_defined(self)`
- L26: `UserRoleTests.test_register_page_loads(self)`
- L30: `UserRoleTests.test_user_can_register(self)`
- L47: `UserRoleTests.test_customer_dashboard_redirect(self)`
- L58: `UserRoleTests.test_restaurant_order_urls_use_restaurant_session_before_customer_order_prefix(self)`
- L83: `UserRoleTests.test_customer_profile_can_update_email_phone_and_address(self)`
- L110: `UserRoleTests.test_customer_header_actions_match_authentication_state(self)`
- L129: `UserRoleTests.test_customer_accounts_share_the_same_features_without_sharing_identity(self)`
- L161: `UserRoleTests.test_admin_dashboard_lists_users(self)`
- L174: `UserRoleTests.test_guest_customer_dashboard_shows_auth_prompt(self)`
- L180: `UserRoleTests.test_each_portal_entry_page_loads(self)`
- L195: `UserRoleTests.test_legacy_restaurant_portal_route_redirects_to_partner_route(self)`
- L202: `UserRoleTests.test_homepage_shows_customer_discovery_and_partner_portals(self)`
- L210: `UserRoleTests.test_portal_registration_assigns_its_fixed_role(self)`
- L274: `UserRoleTests.test_portal_login_rejects_an_account_from_another_role(self)`
- L289: `UserRoleTests.test_restaurant_partner_can_log_in_and_reaches_dashboard(self)`
- L305: `UserRoleTests.test_portal_login_and_register_remain_available_across_roles(self)`
- L339: `UserRoleTests.test_customer_cannot_open_restaurant_management(self)`
- L351: `UserRoleTests.test_password_reset_sends_a_one_time_link_without_enumerating_accounts(self)`
- L399: `UserRoleTests.test_authenticated_user_can_change_password_through_api(self)`
- L421: `JwtAuthenticationAPITests` ? class
- L422: `JwtAuthenticationAPITests.setUp(self)`
- L432: `JwtAuthenticationAPITests.register(self, data)`
- L439: `JwtAuthenticationAPITests.test_registration_hashes_password_and_creates_customer_profile(self)`
- L449: `JwtAuthenticationAPITests.test_restaurant_api_registration_creates_restaurant(self)`
- L478: `JwtAuthenticationAPITests.test_delivery_api_registration_creates_offline_partner_profile(self)`
- L495: `JwtAuthenticationAPITests.test_role_specific_login_rejects_other_roles(self)`
- L509: `JwtAuthenticationAPITests.test_api_registration_cannot_assign_a_privileged_role(self)`
- L515: `JwtAuthenticationAPITests.test_registration_rejects_duplicate_email_and_phone(self)`
- L527: `JwtAuthenticationAPITests.test_login_returns_jwt_tokens_and_profile_data(self)`
- L544: `JwtAuthenticationAPITests.test_profile_requires_jwt_and_can_be_updated(self)`
- L579: `SeparateSessionTests` ? class
- L580: `SeparateSessionTests.setUp(self)`
- L605: `SeparateSessionTests.test_customer_and_delivery_sessions_coexist_independently(self)`
- L651: `SeparateSessionTests.test_delivery_portal_does_not_block_user_when_customer_session_is_active(self)`
- L663: `DeleteAccountTests` ? class
- L664: `DeleteAccountTests.setUp(self)`
- L685: `DeleteAccountTests.test_customer_can_delete_own_account(self)`
- L691: `DeleteAccountTests.test_delivery_partner_can_delete_own_account(self)`
- L697: `DeleteAccountTests.test_admin_can_delete_user_from_dashboard(self)`
- L703: `DeleteAccountTests.test_admin_cannot_delete_own_account(self)`
- L709: `DeleteAccountTests.test_delete_account_confirm_page_loads(self)`
- L715: `DeleteAccountTests.test_api_delete_account(self)`

### `accounts/views.py`

- L62: `register_view(request)`
- L79: `login_view(request)`
- L99: `portal_login_view(request, role)`
- L142: `portal_register_view(request, role)`
- L252: `customer_portal_view(request)`
- L256: `restaurant_portal_view(request)`
- L271: `delivery_portal_view(request)`
- L292: `customer_logout_view(request)`
- L298: `delivery_logout_view(request)`
- L304: `logout_view(request)`
- L328: `forgot_password_view(request)`
- L341: `settings_view(request)`
- L361: `delete_account_view(request)`
- L389: `admin_delete_user_view(request, user_id)`
- L403: `password_change_view(request)`
- L413: `api_signup_view(request)`
- L458: `api_login_view(request)`
- L497: `api_forgot_password_view(request)`
- L524: `api_password_change_view(request)`
- L550: `api_profile_view(request)`
- L568: `dashboard_view(request)`
- L579: `customer_dashboard_view(request)`
- L610: `_customer_restaurants_for_state(state)`
- L623: `restaurant_dashboard_view(request)`
- L644: `delivery_dashboard_view(request)`
- L665: `admin_dashboard_view(request)`

### `customer/admin.py`

- L7: `CustomerProfileAdmin` ? class
- L13: `ReviewAdmin` ? class

### `customer/api_views.py`

- L14: `RestaurantReviewListAPIView` ? class
- L17: `RestaurantReviewListAPIView.get(self, request, restaurant_id)`
- L28: `ReviewCreateAPIView` ? class
- L32: `ReviewCreateAPIView.post(self, request, restaurant_id)`

### `customer/apps.py`

- L4: `CustomerConfig` ? class

### `customer/migrations/0001_initial.py`

- L8: `Migration` ? class

### `customer/migrations/0002_customerprofile_profile_image_and_more.py`

- L6: `Migration` ? class

### `customer/migrations/0003_review.py`

- L8: `Migration` ? class

### `customer/migrations/0004_review_is_hidden_review_moderated_at_and_more.py`

- L8: `Migration` ? class

### `customer/migrations/0005_customerprofile_address_line_and_more.py`

- L8: `Migration` ? class

### `customer/migrations/0006_customeraddress_area_customeraddress_district_and_more.py`

- L6: `Migration` ? class

### `customer/models.py`

- L6: `CustomerProfile` ? class
- L28: `CustomerProfile.__str__(self)`
- L32: `CustomerAddress` ? class
- L52: `CustomerAddress.Meta` ? class
- L57: `CustomerAddress.__str__(self)`
- L61: `Review` ? class
- L110: `Review.Meta` ? class
- L114: `Review.stars(self)`
- L118: `Review.clean(self)`
- L128: `Review.save(self, *args, **kwargs)`
- L132: `Review.__str__(self)`

### `customer/serializers.py`

- L6: `ReviewSerializer` ? class
- L9: `ReviewSerializer.Meta` ? class
- L14: `ReviewSerializer.get_customer_name(self, review)`
- L18: `ReviewCreateSerializer` ? class

### `customer/test_dashboard.py`

- L8: `CustomerDashboardTests` ? class
- L9: `CustomerDashboardTests.test_restaurants_use_full_width_listing_cards(self)`

### `customer/tests.py`

- L13: `CustomerProfileTests` ? class
- L14: `CustomerProfileTests.setUp(self)`
- L22: `CustomerProfileTests.test_customer_profile_page_loads(self)`
- L27: `CustomerProfileTests.test_customer_profile_can_be_updated(self)`
- L42: `CustomerProfileTests.test_customer_profile_updates_are_private_to_each_account(self)`
- L76: `CustomerProfileTests.test_customer_can_review_only_a_delivered_order(self)`
- L108: `CustomerProfileTests.test_undelivered_order_cannot_be_reviewed(self)`
- L139: `CustomerProfileTests.test_review_api_accepts_only_customers_with_delivered_orders(self)`

### `customer/views.py`

- L20: `customer_profile_view(request)`
- L85: `order_review_view(request, order_id)`

### `delivery/admin.py`

- L11: `DeliveryAssignmentAttemptInline` ? class
- L23: `DeliveryAssignmentAttemptInline.has_add_permission(self, request, obj)`
- L28: `DeliveryAssignmentAdmin` ? class
- L36: `DeliveryAssignmentAttemptAdmin` ? class
- L49: `DeliveryAssignmentAttemptAdmin.has_add_permission(self, request)`
- L52: `DeliveryAssignmentAttemptAdmin.has_delete_permission(self, request, obj)`
- L57: `DeliveryPartnerProfileAdmin` ? class
- L64: `DeliveryLocationAdmin` ? class

### `delivery/api_views.py`

- L25: `is_delivery_partner(user)`
- L29: `assignment_payload(assignment)`
- L49: `DeliveryDashboardAPIView` ? class
- L52: `DeliveryDashboardAPIView.get(self, request)`
- L82: `DeliveryAvailabilityAPIView` ? class
- L85: `DeliveryAvailabilityAPIView.post(self, request, online)`
- L96: `DeliveryRequestListAPIView` ? class
- L99: `DeliveryRequestListAPIView.get(self, request)`
- L113: `DeliveryAssignmentActionAPIView` ? class
- L117: `DeliveryAssignmentActionAPIView.post(self, request, assignment_id, action)`
- L133: `AdvanceDeliveryAPIView` ? class
- L136: `AdvanceDeliveryAPIView.post(self, request, assignment_id, new_status)`
- L145: `DeliveryLocationAPIView` ? class
- L148: `DeliveryLocationAPIView.post(self, request)`
- L252: `DeliveryHistoryAPIView` ? class
- L255: `DeliveryHistoryAPIView.get(self, request)`

### `delivery/apps.py`

- L4: `DeliveryConfig` ? class

### `delivery/migrations/0001_initial.py`

- L8: `Migration` ? class

### `delivery/migrations/0002_alter_deliveryassignment_status_deliverylocation_and_more.py`

- L8: `Migration` ? class

### `delivery/migrations/0003_deliverylocation_accuracy_and_more.py`

- L8: `Migration` ? class

### `delivery/migrations/0004_deliverypartnerprofile_accuracy_and_more.py`

- L6: `Migration` ? class

### `delivery/migrations/0005_deliveryassignment_arrived_at_pickup_time_and_more.py`

- L6: `Migration` ? class

### `delivery/migrations/0006_alter_deliveryassignment_status_and_more.py`

- L8: `Migration` ? class

### `delivery/migrations/0007_alter_deliveryassignmentattempt_status.py`

- L6: `Migration` ? class

### `delivery/models.py`

- L7: `DeliveryPartnerProfile` ? class
- L27: `DeliveryPartnerProfile.__str__(self)`
- L31: `DeliveryAssignment` ? class
- L68: `DeliveryAssignment.__str__(self)`
- L72: `DeliveryAssignmentAttempt` ? class
- L107: `DeliveryAssignmentAttempt.Meta` ? class
- L111: `DeliveryAssignmentAttempt.__str__(self)`
- L115: `DeliveryLocation` ? class
- L145: `DeliveryLocation.Meta` ? class
- L152: `DeliveryLocation.__str__(self)`

### `delivery/services.py`

- L30: `_distance_to_restaurant(profile, restaurant)`
- L54: `_notify_waiting_for_delivery(order)`
- L82: `_notify_assignment_failed(order)`
- L125: `_set_order_status(order, status, actor, reason)`
- L134: `_expire_pending_offer(assignment, order, now)`
- L161: `assign_ready_order(order, force_retry)`
- L296: `dispatch_ready_orders()`
- L308: `manually_assign_delivery_partner(order_id, partner_id, actor)`
- L434: `retry_delivery_assignment(order_id, actor)`
- L451: `refresh_partner_offers(user)`
- L456: `cancel_order_assignment(order, actor, reason)`
- L490: `accept_assignment(user, assignment_id)`
- L534: `reject_assignment(user, assignment_id, reason)`
- L567: `advance_assignment(user, assignment_id, new_status)`
- L681: `_settle_cash_on_delivery(order)`

### `delivery/tests.py`

- L22: `DeliveryFlowTests` ? class
- L23: `DeliveryFlowTests.setUp(self)`
- L66: `DeliveryFlowTests.test_delivery_partner_cannot_self_assign_an_order(self)`
- L72: `DeliveryFlowTests.test_delivery_dashboard_loads(self)`
- L80: `DeliveryFlowTests.test_shared_settings_uses_delivery_partner_with_customer_session_active(self)`
- L104: `DeliveryFlowTests.test_customer_settings_keeps_shared_design_without_delivery_details(self)`
- L119: `DeliveryFlowTests.test_delivery_partner_can_update_assignment_status(self)`
- L142: `DeliveryFlowTests.test_delivery_partner_cannot_skip_arrival_before_pickup(self)`
- L164: `DeliveryFlowTests.test_restaurant_manually_assigns_partner_who_accepts_and_completes_pickup(self)`
- L252: `DeliveryFlowTests.test_ready_order_is_assigned_to_nearest_online_partner(self)`
- L287: `DeliveryFlowTests.test_ready_order_does_not_assign_to_stale_or_unavailable_partner(self)`
- L307: `DeliveryFlowTests.test_unassigned_ready_order_notifies_restaurant_and_admin_only_once(self)`
- L329: `DeliveryFlowTests.test_expired_offer_is_recorded_and_reassigned(self)`
- L383: `DeliveryFlowTests.test_maximum_offers_fail_and_admin_retry_preserves_attempt_history(self)`
- L418: `DeliveryFlowTests.test_delivery_status_rejects_get_requests(self)`
- L430: `DeliveryFlowTests.test_delivery_completion_does_not_override_offline_choice(self)`
- L448: `DeliveryFlowTests.test_delivery_api_accepts_tracks_and_completes_own_assignment(self)`
- L510: `DeliveryFlowTests.test_delivery_api_hides_other_partners_assignments(self)`
- L533: `DeliveryFlowTests.test_full_10_step_order_and_delivery_lifecycle(self)`
- L624: `DeliveryFlowTests.test_partner_rejects_assignment_reverts_order_to_ready(self)`

### `delivery/views.py`

- L17: `delivery_dashboard_view(request)`
- L34: `delivery_detail_view(request, assignment_id)`
- L44: `assign_delivery_view(request, order_id)`
- L55: `delivery_availability_view(request)`
- L66: `accept_delivery_view(request, assignment_id)`
- L78: `reject_delivery_view(request, assignment_id)`
- L90: `update_delivery_status_view(request, assignment_id, new_status)`

### `food_ex/admin.py`

- L7: `UserAdmin` ? class

### `food_ex/apps.py`

- L4: `FoodExConfig` ? class

### `food_ex/settings/base.py`

- L29: `env_list(name, default)`

### `food_ex/views.py`

- L7: `home(request)`

### `location/admin.py`

- L7: `LocationSettingAdmin` ? class
- L24: `CustomerAddressAdmin` ? class

### `location/api_views.py`

- L14: `IsAdmin` ? class
- L15: `IsAdmin.has_permission(self, request, view)`
- L34: `CustomerLocationUpdateAPIView` ? class
- L38: `CustomerLocationUpdateAPIView.post(self, request)`
- L109: `CustomerSavedAddressesAPIView` ? class
- L113: `CustomerSavedAddressesAPIView.get(self, request)`
- L134: `CustomerSavedAddressesAPIView.post(self, request)`
- L206: `CustomerAddressDetailAPIView` ? class
- L210: `CustomerAddressDetailAPIView.patch(self, request, address_id)`
- L283: `CustomerAddressDetailAPIView.delete(self, request, address_id)`
- L289: `RestaurantLocationUpdateAPIView` ? class
- L293: `RestaurantLocationUpdateAPIView.get(self, request)`
- L320: `RestaurantLocationUpdateAPIView.post(self, request)`
- L395: `DeliveryLocationUpdateAPIView` ? class
- L402: `DeliveryLocationUpdateAPIView.post(self, request)`
- L615: `NearbyRestaurantsAPIView` ? class
- L619: `NearbyRestaurantsAPIView.get(self, request)`
- L670: `NearbyDeliveryPartnersAPIView` ? class
- L674: `NearbyDeliveryPartnersAPIView.get(self, request)`
- L736: `OrderDeliveryLocationAPIView` ? class
- L743: `OrderDeliveryLocationAPIView.get(self, request, order_id)`
- L1049: `OrderRouteAPIView` ? class
- L1056: `OrderRouteAPIView.get(self, request, order_id)`
- L1157: `AdminLiveGPSAPIView` ? class
- L1161: `AdminLiveGPSAPIView.get(self, request)`
- L1305: `DetectLocationAPIView` ? class
- L1312: `DetectLocationAPIView.get(self, request)`

### `location/apps.py`

- L4: `LocationConfig` ? class

### `location/migrations/0001_initial.py`

- L6: `Migration` ? class

### `location/migrations/0002_locationsetting_partner_location_max_age_seconds.py`

- L6: `Migration` ? class

### `location/migrations/0003_locationsetting_delivery_assignment_accept_timeout_seconds_and_more.py`

- L6: `Migration` ? class

### `location/models.py`

- L12: `LocationSetting` ? class
- L72: `LocationSetting.Meta` ? class
- L77: `LocationSetting.__str__(self)`
- L80: `LocationSetting.save(self, *args, **kwargs)`
- L85: `LocationSetting.load(cls)`

### `location/services.py`

- L21: `calculate_distance(lat1, lon1, lat2, lon2)`
- L50: `calculate_eta(distance_km, prep_minutes)`
- L77: `validate_coordinates(latitude, longitude)`
- L93: `reverse_geocode(latitude, longitude)`
- L157: `check_restaurant_geofence(partner_lat, partner_lon, rest_lat, rest_lon, radius_meters)`
- L171: `get_road_route(origin_lat, origin_lon, dest_lat, dest_lon)`
- L249: `get_nearby_restaurants(latitude, longitude, radius_km, limit, query, cuisine, state, district, city, area)`

### `location/tests.py`

- L19: `LocationServicesTests` ? class
- L20: `LocationServicesTests.test_haversine_distance_calculation(self)`
- L29: `LocationServicesTests.test_distance_with_none_returns_none(self)`
- L33: `LocationServicesTests.test_coordinate_validation(self)`
- L44: `LocationServicesTests.test_eta_calculation(self)`
- L50: `LocationAPITests` ? class
- L51: `LocationAPITests.setUp(self)`
- L139: `LocationAPITests.test_customer_location_page_shows_only_the_signed_in_customers_latest_order(self)`
- L158: `LocationAPITests.test_customer_location_page_shows_empty_tracking_state_without_orders(self)`
- L167: `LocationAPITests.test_customer_location_update(self)`
- L183: `LocationAPITests.test_customer_gps_saves_accuracy_and_rejects_invalid_accuracy(self)`
- L202: `LocationAPITests.test_customer_gps_response_includes_reverse_geocoded_state(self, reverse_geocode)`
- L228: `LocationAPITests.test_order_checkout_stores_customer_and_restaurant_location_snapshots(self)`
- L270: `LocationAPITests.test_nearby_restaurants_honors_delivery_radius_and_location_filters(self)`
- L302: `LocationAPITests.test_checkout_rejects_delivery_address_outside_restaurant_radius(self)`
- L333: `LocationAPITests.test_invalid_coordinates_rejected(self)`
- L343: `LocationAPITests.test_unauthenticated_user_cannot_update_customer_location(self)`
- L351: `LocationAPITests.test_customer_saved_addresses_isolation(self)`
- L376: `LocationAPITests.test_customer_can_update_only_their_saved_address(self)`
- L408: `LocationAPITests.test_restaurant_owner_can_update_restaurant_location(self)`
- L424: `LocationAPITests.test_customer_cannot_update_restaurant_location(self)`
- L433: `LocationAPITests.test_delivery_partner_location_update(self)`
- L456: `LocationAPITests.test_nearby_restaurants_api(self)`
- L472: `LocationAPITests.test_order_tracking_privacy_security(self)`
- L485: `LocationAPITests.test_nearby_restaurants_rejects_radius_over_twenty_km(self)`
- L492: `LocationAPITests.test_nearby_delivery_partners_returns_only_fresh_available_partners(self)`
- L514: `LocationAPITests.test_nearby_delivery_partners_requires_authentication(self)`
- L521: `LocationAPITests.test_delivery_location_cannot_update_an_unassigned_order(self)`
- L539: `LocationAPITests.test_tracking_api_alias_and_customer_tracking_page(self)`
- L555: `LocationAPITests.test_online_partner_gps_update_retries_ready_order_dispatch(self)`
- L583: `LocationAPITests.test_ready_order_waits_when_online_partner_is_outside_dispatch_radius(self)`
- L604: `LocationAPITests.test_admin_live_feed_includes_private_operational_states_only_for_admin(self)`
- L633: `LocationAPITests.test_partner_gps_update_with_assigned_status(self)`
- L661: `LocationAPITests.test_partner_gps_update_forbidden_for_other_partner(self)`
- L680: `LocationAPITests.test_partner_gps_update_returns_410_on_completed_delivery(self)`
- L699: `LocationAPITests.test_partner_gps_update_rejects_invalid_coordinates(self)`
- L711: `LocationAPITests.test_customer_order_tracking_returns_live_location(self)`
- L735: `LocationAPITests.test_customer_order_tracking_forbidden_for_other_customer(self)`
- L742: `LocationAPITests.test_customer_order_tracking_stale_location_returns_gracefully(self)`
- L766: `LocationAPITests.test_location_setting_carto_tile_url_default(self)`
- L772: `RealTimeGPSAndRestaurantFirstRouteTests` ? class
- L773: `RealTimeGPSAndRestaurantFirstRouteTests.setUp(self)`
- L864: `RealTimeGPSAndRestaurantFirstRouteTests.test_geofence_arrival_detection_helper(self)`
- L874: `RealTimeGPSAndRestaurantFirstRouteTests.test_road_route_service_returns_valid_data(self)`
- L882: `RealTimeGPSAndRestaurantFirstRouteTests.test_phase_a_partner_to_restaurant_route(self)`
- L908: `RealTimeGPSAndRestaurantFirstRouteTests.test_phase_b_geofence_arrival_triggers_status_update(self)`
- L949: `RealTimeGPSAndRestaurantFirstRouteTests.test_phase_c_and_d_pickup_switches_destination_to_customer(self)`
- L972: `RealTimeGPSAndRestaurantFirstRouteTests.test_phase_e_delivered_status(self)`
- L989: `RealTimeGPSAndRestaurantFirstRouteTests.test_unauthorized_partner_gps_update_rejected(self)`
- L1010: `RealTimeGPSAndRestaurantFirstRouteTests.test_unauthorized_customer_cannot_track_order(self)`

### `location/views.py`

- L15: `admin_location_dashboard_view(request)`
- L39: `customer_location_view(request)`
- L64: `restaurant_location_view(request)`

### `manage.py`

- L7: `main()`

### `notifications/admin.py`

- L7: `NotificationAdmin` ? class

### `notifications/api_views.py`

- L9: `serialize_notification(notification)`
- L21: `NotificationListAPIView` ? class
- L24: `NotificationListAPIView.get(self, request)`
- L32: `NotificationReadAPIView` ? class
- L35: `NotificationReadAPIView.patch(self, request, notification_id)`

### `notifications/apps.py`

- L4: `NotificationsConfig` ? class

### `notifications/migrations/0001_initial.py`

- L8: `Migration` ? class

### `notifications/models.py`

- L5: `Notification` ? class
- L25: `Notification.Meta` ? class
- L28: `Notification.__str__(self)`

### `notifications/services.py`

- L4: `notify_user(user, category, title, message, link)`

### `notifications/tests.py`

- L10: `NotificationAPITests` ? class
- L11: `NotificationAPITests.setUp(self)`
- L33: `NotificationAPITests.test_customer_can_list_and_mark_own_notification_read(self)`
- L47: `NotificationAPITests.test_customer_cannot_read_another_users_notification(self)`
- L63: `NotificationAPITests.test_html_notification_center_shows_only_signed_in_user_notices(self)`

### `notifications/views.py`

- L9: `notification_center_view(request)`
- L20: `mark_notification_read_view(request, notification_id)`

### `orders/admin.py`

- L7: `retry_delivery_assignment_action(modeladmin, request, queryset)`
- L29: `CartAdmin` ? class
- L34: `CartItemAdmin` ? class
- L39: `OrderAdmin` ? class
- L46: `OrderItemAdmin` ? class
- L51: `OrderStatusEventAdmin` ? class
- L64: `OrderStatusEventAdmin.has_add_permission(self, request)`
- L67: `OrderStatusEventAdmin.has_delete_permission(self, request, obj)`

### `orders/api_views.py`

- L26: `customer_only(request)`
- L30: `cart_payload(cart)`
- L51: `CartAPIView` ? class
- L54: `CartAPIView.get(self, request)`
- L60: `CartAPIView.post(self, request)`
- L105: `CartItemAPIView` ? class
- L108: `CartItemAPIView._item(self, request, item_id)`
- L113: `CartItemAPIView.patch(self, request, item_id)`
- L130: `CartItemAPIView.delete(self, request, item_id)`
- L138: `CheckoutSummaryAPIView` ? class
- L143: `CheckoutSummaryAPIView.get(self, request)`
- L172: `OrderListCreateAPIView` ? class
- L175: `OrderListCreateAPIView.get(self, request)`
- L185: `OrderListCreateAPIView.post(self, request)`
- L205: `OrderDetailAPIView` ? class
- L208: `OrderDetailAPIView.get(self, request, order_id)`
- L234: `OrderStatusAPIView` ? class
- L237: `OrderStatusAPIView.get(self, request, order_id)`

### `orders/apps.py`

- L4: `OrdersConfig` ? class

### `orders/migrations/0001_initial.py`

- L8: `Migration` ? class

### `orders/migrations/0002_order_delivery_latitude_order_delivery_longitude_and_more.py`

- L6: `Migration` ? class

### `orders/migrations/0003_alter_order_options_order_accepted_at_and_more.py`

- L7: `Migration` ? class

### `orders/migrations/0004_order_offer_order_picked_up_at_order_preparing_at_and_more.py`

- L8: `Migration` ? class

### `orders/migrations/0005_order_address_order_customer_latitude_and_more.py`

- L7: `Migration` ? class

### `orders/migrations/0006_order_delivery_area_order_delivery_city_and_more.py`

- L6: `Migration` ? class

### `orders/migrations/0007_order_arrived_at_pickup_at_and_more.py`

- L6: `Migration` ? class

### `orders/migrations/0008_alter_order_status_orderstatusevent.py`

- L8: `Migration` ? class

### `orders/models.py`

- L11: `Cart` ? class
- L16: `Cart.__str__(self)`
- L20: `Cart.total_items(self)`
- L24: `Cart.total_price(self)`
- L31: `CartItem` ? class
- L40: `CartItem.Meta` ? class
- L43: `CartItem.__str__(self)`
- L47: `CartItem.subtotal(self)`
- L51: `Order` ? class
- L179: `Order.Meta` ? class
- L182: `Order.__str__(self)`
- L185: `Order.save(self, *args, **kwargs)`
- L190: `Order._generate_code(self)`
- L201: `Order.is_live(self)`
- L205: `Order.is_closed(self)`
- L209: `Order.payment_status(self)`
- L225: `Order.customer_display_name(self)`
- L230: `Order.customer_phone(self)`
- L235: `OrderStatusEvent` ? class
- L249: `OrderStatusEvent.Meta` ? class
- L253: `OrderStatusEvent.__str__(self)`
- L257: `OrderItem` ? class
- L268: `OrderItem.__str__(self)`
- L271: `OrderItem.save(self, *args, **kwargs)`
- L277: `OrderItem.subtotal(self)`

### `orders/serializers.py`

- L6: `OrderItemSerializer` ? class
- L12: `OrderItemSerializer.Meta` ? class
- L26: `OrderSerializer` ? class
- L33: `OrderSerializer.Meta` ? class
- L72: `OrderCreateSerializer` ? class
- L90: `OrderCreateSerializer.validate(self, attrs)`
- L103: `OrderCreateSerializer.validate_delivery_address(self, value)`

### `orders/services.py`

- L19: `CartCheckoutError` ? class
- L23: `OrderTransitionError` ? class
- L27: `_money(value)`
- L31: `compute_order_totals(subtotal, offer)`
- L55: `resolve_offer(restaurant, offer_code, subtotal)`
- L75: `create_order_from_cart(user, delivery_address, latitude, longitude, offer_code, address_id)`
- L249: `_assert_order_is_paid(order)`
- L257: `transition_restaurant_order(user, order_id, new_status, rejection_reason, rejection_note, preparation_minutes)`
- L364: `record_order_status_event(order, from_status, actor, reason)`
- L376: `_refund_if_prepaid(order)`
- L383: `_cancel_order_earning(order)`

### `orders/tests.py`

- L24: `OrderFlowTests` ? class
- L25: `OrderFlowTests.setUp(self)`
- L56: `OrderFlowTests.test_cart_is_created_for_user(self)`
- L60: `OrderFlowTests.test_order_can_be_created_from_cart(self)`
- L70: `OrderFlowTests.test_menu_has_an_authenticated_post_add_to_cart_action(self)`
- L76: `OrderFlowTests.test_add_to_cart_increments_existing_item_and_enforces_one_restaurant_choice(self)`
- L121: `OrderFlowTests.test_cart_page_has_server_calculated_summary_and_item_controls(self)`
- L136: `OrderFlowTests.test_cart_contents_are_private_to_each_customer_account(self)`
- L164: `OrderFlowTests.test_cart_item_quantity_buttons_decrease_and_remove(self)`
- L175: `OrderFlowTests.test_order_history_page_loads(self)`
- L180: `OrderFlowTests.test_customer_accounts_share_order_features_but_only_see_their_own_orders(self)`
- L218: `OrderFlowTests.test_customer_dashboard_only_shows_greeting(self)`
- L249: `OrderFlowTests.test_customer_dashboard_uses_saved_gps_state_to_filter_restaurants(self)`
- L283: `OrderFlowTests.test_restaurant_owner_can_accept_or_reject_order(self)`
- L370: `OrderFlowTests.test_restaurant_can_cancel_an_accepted_order(self)`
- L393: `OrderFlowTests.test_restaurant_cancellation_releases_an_active_delivery_offer(self)`
- L440: `OrderFlowTests.test_restaurant_order_decisions_reject_get_requests(self)`
- L451: `OrderFlowTests.test_customer_api_checkout_uses_database_prices_and_clears_cart(self)`
- L480: `OrderFlowTests.test_customer_order_api_does_not_expose_another_users_order(self)`
- L498: `OrderFlowTests.test_non_customer_cannot_use_cart_api(self)`
- L504: `OrderFlowTests.test_order_status_api_returns_timeline_only_to_its_customer(self)`
- L529: `OrderFlowTests.test_order_detail_page_includes_live_tracking(self)`
- L545: `OrderFlowTests.test_order_tracking_api_includes_restaurant_and_delivery_details(self)`
- L585: `OrderFlowTests.test_terminal_tracking_hides_partner_location_and_denies_partner_access(self)`
- L628: `OrderFlowTests.test_restaurant_order_api_is_scoped_and_uses_valid_transitions(self)`
- L670: `OrderFlowTests.test_restaurant_queue_hides_unpaid_online_orders(self)`
- L683: `OrderFlowTests.test_ready_restaurant_order_is_assigned_to_an_online_partner(self)`

### `orders/views.py`

- L25: `cart_view(request)`
- L43: `add_to_cart_view(request, menu_item_id)`
- L100: `cart_item_update_view(request, item_id, action)`
- L129: `checkout_view(request)`
- L157: `order_detail_view(request, order_id)`
- L169: `order_history_view(request)`
- L175: `restaurant_order_management_view(request)`
- L254: `order_assign_delivery_partner_view(request, order_id)`
- L282: `order_accept_view(request, order_id)`
- L292: `order_reject_view(request, order_id)`
- L308: `order_cancel_view(request, order_id)`
- L318: `order_preparing_view(request, order_id)`
- L328: `order_ready_view(request, order_id)`

### `payments/admin.py`

- L7: `PaymentAdmin` ? class

### `payments/api_views.py`

- L12: `OrderPaymentAPIView` ? class
- L15: `OrderPaymentAPIView.post(self, request, order_id)`

### `payments/apps.py`

- L4: `PaymentsConfig` ? class

### `payments/migrations/0001_initial.py`

- L7: `Migration` ? class

### `payments/migrations/0002_alter_payment_payment_method_alter_payment_status.py`

- L6: `Migration` ? class

### `payments/migrations/0003_alter_payment_options_payment_provider_and_more.py`

- L7: `Migration` ? class

### `payments/models.py`

- L6: `Payment` ? class
- L46: `Payment.Meta` ? class
- L49: `Payment.__str__(self)`
- L53: `Payment.is_captured(self)`
- L57: `Payment.net_amount(self)`

### `payments/services.py`

- L13: `PaymentProcessingError` ? class
- L17: `MockPaymentProvider` ? class
- L26: `MockPaymentProvider.charge(self, order)`
- L29: `MockPaymentProvider.refund(self, payment, amount)`
- L33: `get_provider()`
- L39: `PaymentService` ? class
- L41: `PaymentService.process(cls, order, payment_method)`
- L99: `PaymentService._notify_restaurant_of_new_order(order, kind)`
- L110: `refund_order_payments(order, reason, amount)`

### `payments/tests.py`

- L15: `PaymentFlowTests` ? class
- L16: `PaymentFlowTests.setUp(self)`
- L46: `PaymentFlowTests.test_payment_page_loads_for_customer(self)`
- L52: `PaymentFlowTests.test_mock_payment_generates_reference_on_the_server(self)`
- L75: `PaymentFlowTests.test_cash_on_delivery_is_not_marked_paid(self)`
- L86: `PaymentFlowTests.test_repeated_cash_on_delivery_submission_is_idempotent(self)`
- L96: `PaymentFlowTests.test_unconfigured_card_payment_is_rejected(self)`
- L110: `PaymentFlowTests.test_payment_api_generates_its_own_transaction_reference(self)`

### `payments/views.py`

- L12: `payment_page(request, order_id)`

### `restaurant/admin.py`

- L7: `approve_restaurants(modeladmin, request, queryset)`
- L12: `reject_restaurants(modeladmin, request, queryset)`
- L17: `suspend_restaurants(modeladmin, request, queryset)`
- L22: `RestaurantAdmin` ? class
- L30: `RestaurantAdmin.masked_bank_account_number(self, obj)`
- L38: `MenuItemAdmin` ? class

### `restaurant/api_views.py`

- L16: `RestaurantListAPIView` ? class
- L19: `RestaurantListAPIView.get(self, request)`
- L36: `RestaurantDetailAPIView` ? class
- L39: `RestaurantDetailAPIView.get(self, request, restaurant_id)`
- L49: `RestaurantMenuAPIView` ? class
- L52: `RestaurantMenuAPIView.get(self, request, restaurant_id)`
- L63: `owned_restaurant(user)`
- L69: `RestaurantMenuManageAPIView` ? class
- L72: `RestaurantMenuManageAPIView.get(self, request)`
- L79: `RestaurantMenuManageAPIView.post(self, request)`
- L90: `RestaurantMenuItemManageAPIView` ? class
- L93: `RestaurantMenuItemManageAPIView._owned_item(self, request, item_id)`
- L99: `RestaurantMenuItemManageAPIView.put(self, request, item_id)`
- L102: `RestaurantMenuItemManageAPIView.patch(self, request, item_id)`
- L105: `RestaurantMenuItemManageAPIView._update(self, request, item_id, partial)`
- L115: `RestaurantMenuItemManageAPIView.delete(self, request, item_id)`

### `restaurant/apps.py`

- L4: `RestaurantConfig` ? class

### `restaurant/fields.py`

- L9: `EncryptedCharField` ? class
- L12: `EncryptedCharField._cipher(self)`
- L17: `EncryptedCharField.get_prep_value(self, value)`
- L24: `EncryptedCharField.from_db_value(self, value, expression, connection)`

### `restaurant/forms.py`

- L13: `validate_restaurant_image_size(upload)`
- L18: `RestaurantRegistrationForm` ? class
- L72: `RestaurantRegistrationForm.__init__(self, *args, **kwargs)`
- L79: `RestaurantRegistrationForm.clean_fssai_number(self)`
- L82: `RestaurantRegistrationForm.clean_gst_number(self)`
- L88: `RestaurantRegistrationForm.clean_pan_number(self)`
- L94: `RestaurantRegistrationForm.clean_bank_ifsc_code(self)`
- L98: `RestaurantProfileForm` ? class
- L110: `RestaurantProfileForm.Meta` ? class
- L140: `RestaurantProfileForm.__init__(self, *args, **kwargs)`
- L151: `RestaurantProfileForm.clean_pincode(self)`
- L157: `RestaurantProfileForm.clean_fssai_number(self)`
- L163: `RestaurantProfileForm.clean_gst_number(self)`
- L169: `RestaurantProfileForm.clean_pan_number(self)`
- L176: `RestaurantOwnerAccountForm` ? class
- L220: `RestaurantOwnerAccountForm.__init__(self, *args, user, restaurant, **kwargs)`
- L230: `RestaurantOwnerAccountForm.clean_email(self)`
- L240: `RestaurantOwnerAccountForm.clean_mobile_number(self)`
- L253: `RestaurantOwnerAccountForm.clean_pincode(self)`

### `restaurant/management/commands/seed_demo_data.py`

- L29: `q(value, places)`
- L33: `try_save(obj, updates)`
- L51: `_get_or_create_user(email, password, role, **extra)`
- L86: `_update_or_create_profile(model, user_key, defaults)`
- L101: `Command` ? class
- L104: `Command.add_arguments(self, parser)`
- L111: `Command.handle(self, *args, **options)`
- L130: `Command._seed_users(self)`
- L216: `Command._seed_platform_settings(self)`
- L237: `Command._ramesh_spec(self)`
- L310: `Command._sagar_spec(self)`
- L387: `Command._seed_restaurant(self, owner_email, spec)`
- L535: `Command._seed_delivered_order(self)`
- L708: `Command._counts(self, extended)`

### `restaurant/migrations/0001_initial.py`

- L8: `Migration` ? class

### `restaurant/migrations/0002_restaurant_latitude_restaurant_longitude.py`

- L6: `Migration` ? class

### `restaurant/migrations/0003_menuitem_image_restaurant_image.py`

- L6: `Migration` ? class

### `restaurant/migrations/0004_restaurant_city_restaurant_closing_time_and_more.py`

- L6: `Migration` ? class

### `restaurant/migrations/0005_restaurant_account_holder_name_and_more.py`

- L7: `Migration` ? class

### `restaurant/migrations/0006_alter_restaurant_is_active.py`

- L6: `Migration` ? class

### `restaurant/migrations/0007_approve_existing_active_restaurants.py`

- L4: `approve_existing_active_restaurants(apps, schema_editor)`
- L9: `Migration` ? class

### `restaurant/migrations/0008_platformsetting_alter_menuitem_options_and_more.py`

- L10: `Migration` ? class

### `restaurant/migrations/0009_restaurant_reviewed_by.py`

- L8: `Migration` ? class

### `restaurant/migrations/0010_restaurant_address_line_and_more.py`

- L6: `Migration` ? class

### `restaurant/migrations/0011_restaurant_area_restaurant_delivery_radius_km_and_more.py`

- L8: `Migration` ? class

### `restaurant/models.py`

- L17: `quantize_money(value)`
- L24: `PlatformSetting` ? class
- L48: `PlatformSetting.Meta` ? class
- L52: `PlatformSetting.__str__(self)`
- L55: `PlatformSetting.save(self, *args, **kwargs)`
- L60: `PlatformSetting.load(cls)`
- L65: `Restaurant` ? class
- L164: `Restaurant.Meta` ? class
- L167: `Restaurant.__str__(self)`
- L171: `Restaurant.is_approved(self)`
- L175: `Restaurant.commission_rate(self)`
- L182: `Restaurant.accepts_orders(self)`
- L186: `Restaurant.average_rating(self)`
- L189: `MenuCategory` ? class
- L204: `MenuCategory.Meta` ? class
- L213: `MenuCategory.__str__(self)`
- L217: `MenuCategory.item_count(self)`
- L221: `MenuItem` ? class
- L275: `MenuItem.Meta` ? class
- L278: `MenuItem.__str__(self)`
- L282: `MenuItem.discount_amount(self)`
- L288: `MenuItem.has_discount(self)`
- L292: `MenuItem.final_price(self)`
- L295: `MenuItem.clean(self)`
- L303: `MenuItem.save(self, *args, **kwargs)`
- L320: `RestaurantTiming` ? class
- L341: `RestaurantTiming.Meta` ? class
- L350: `RestaurantTiming.__str__(self)`
- L354: `RestaurantDocument` ? class
- L380: `RestaurantDocument.Meta` ? class
- L383: `RestaurantDocument.__str__(self)`
- L387: `RestaurantOffer` ? class
- L429: `RestaurantOffer.Meta` ? class
- L432: `RestaurantOffer.__str__(self)`
- L436: `RestaurantOffer.is_currently_valid(self)`
- L448: `RestaurantOffer.calculate_discount(self, order_amount)`
- L461: `RestaurantEarning` ? class
- L543: `RestaurantEarning.Meta` ? class
- L546: `RestaurantEarning.__str__(self)`
- L550: `Settlement` ? class
- L577: `Settlement.Meta` ? class
- L580: `Settlement.__str__(self)`

### `restaurant/partner_api_views.py`

- L55: `get_owned_restaurant_or_403(user)`
- L62: `partner_context(request, restaurant)`
- L66: `build_order_payload(order)`
- L132: `PartnerAPIView` ? class
- L136: `PartnerAPIView.initial(self, request, *args, **kwargs)`
- L147: `PartnerDashboardAPIView` ? class
- L148: `PartnerDashboardAPIView.get(self, request)`
- L155: `PartnerDashboardAPIView.get.count_between(queryset, start_date)`
- L159: `PartnerDashboardAPIView.get.sum_between(queryset, start_date, field)`
- L218: `PartnerProfileAPIView` ? class
- L219: `PartnerProfileAPIView.get(self, request)`
- L229: `PartnerProfileAPIView.patch(self, request)`
- L239: `PartnerProfileToggleOpenAPIView` ? class
- L240: `PartnerProfileToggleOpenAPIView.post(self, request)`
- L257: `PartnerCategoryListAPIView` ? class
- L258: `PartnerCategoryListAPIView.get(self, request)`
- L271: `PartnerCategoryListAPIView.post(self, request)`
- L281: `PartnerCategoryDetailAPIView` ? class
- L282: `PartnerCategoryDetailAPIView._get(self, request, category_id)`
- L287: `PartnerCategoryDetailAPIView.get(self, request, category_id)`
- L290: `PartnerCategoryDetailAPIView.patch(self, request, category_id)`
- L303: `PartnerCategoryDetailAPIView.delete(self, request, category_id)`
- L319: `PartnerMenuListAPIView` ? class
- L320: `PartnerMenuListAPIView.get(self, request)`
- L326: `PartnerMenuListAPIView.post(self, request)`
- L339: `PartnerMenuDetailAPIView` ? class
- L340: `PartnerMenuDetailAPIView._get(self, item_id)`
- L343: `PartnerMenuDetailAPIView.get(self, request, item_id)`
- L348: `PartnerMenuDetailAPIView.patch(self, request, item_id)`
- L361: `PartnerMenuDetailAPIView.delete(self, request, item_id)`
- L370: `PartnerTimingListAPIView` ? class
- L371: `PartnerTimingListAPIView.get(self, request)`
- L392: `PartnerTimingBulkAPIView` ? class
- L393: `PartnerTimingBulkAPIView.put(self, request)`
- L425: `PartnerDocumentListAPIView` ? class
- L426: `PartnerDocumentListAPIView.get(self, request)`
- L436: `PartnerDocumentListAPIView.post(self, request)`
- L450: `PartnerOrderListAPIView` ? class
- L453: `PartnerOrderListAPIView.get(self, request)`
- L480: `PartnerOrderDetailAPIView` ? class
- L481: `PartnerOrderDetailAPIView._get(self, order_id)`
- L489: `PartnerOrderDetailAPIView.get(self, request, order_id)`
- L493: `PartnerOrderActionAPIView` ? class
- L502: `PartnerOrderActionAPIView.post(self, request, order_id, action)`
- L525: `PartnerOfferListAPIView` ? class
- L526: `PartnerOfferListAPIView.get(self, request)`
- L530: `PartnerOfferListAPIView.post(self, request)`
- L538: `PartnerOfferDetailAPIView` ? class
- L539: `PartnerOfferDetailAPIView._get(self, offer_id)`
- L542: `PartnerOfferDetailAPIView.get(self, request, offer_id)`
- L545: `PartnerOfferDetailAPIView.patch(self, request, offer_id)`
- L553: `PartnerOfferDetailAPIView.delete(self, request, offer_id)`
- L562: `PartnerReviewListAPIView` ? class
- L563: `PartnerReviewListAPIView.get(self, request)`
- L587: `PartnerReviewReplyAPIView` ? class
- L588: `PartnerReviewReplyAPIView._get(self, review_id)`
- L596: `PartnerReviewReplyAPIView.post(self, request, review_id)`
- L616: `PartnerEarningsAPIView` ? class
- L617: `PartnerEarningsAPIView.get(self, request)`
- L633: `PartnerPaymentsAPIView` ? class
- L634: `PartnerPaymentsAPIView.get(self, request)`
- L654: `PartnerNotificationListAPIView` ? class
- L655: `PartnerNotificationListAPIView.get(self, request)`
- L675: `PartnerNotificationReadAPIView` ? class
- L676: `PartnerNotificationReadAPIView.post(self, request, notification_id)`

### `restaurant/serializers.py`

- L26: `validate_upload(file_obj, label, extensions, max_bytes)`
- L42: `absolute_url(request, file_field)`
- L49: `MenuCategorySerializer` ? class
- L52: `MenuCategorySerializer.Meta` ? class
- L65: `MenuCategorySerializer.validate_name(self, value)`
- L82: `MenuItemSerializer` ? class
- L89: `MenuItemSerializer.Meta` ? class
- L115: `MenuItemSerializer.get_image_url(self, item)`
- L119: `MenuItemWriteSerializer` ? class
- L120: `MenuItemWriteSerializer.Meta` ? class
- L138: `MenuItemWriteSerializer.validate_name(self, value)`
- L144: `MenuItemWriteSerializer.validate_mrp(self, value)`
- L149: `MenuItemWriteSerializer.validate_discount_percent(self, value)`
- L156: `MenuItemWriteSerializer.validate_image(self, value)`
- L159: `MenuItemWriteSerializer.validate_preparation_time_minutes(self, value)`
- L164: `MenuItemWriteSerializer.validate(self, attrs)`
- L178: `RestaurantSerializer` ? class
- L185: `RestaurantSerializer.Meta` ? class
- L215: `RestaurantSerializer.get_rating(self, restaurant)`
- L219: `RestaurantSerializer.get_review_count(self, restaurant)`
- L222: `RestaurantSerializer.get_image_url(self, restaurant)`
- L225: `RestaurantSerializer.get_logo_url(self, restaurant)`
- L228: `RestaurantSerializer.get_delivery_time_minutes(self, restaurant)`
- L236: `RestaurantProfileUpdateSerializer` ? class
- L240: `RestaurantProfileUpdateSerializer.Meta` ? class
- L277: `RestaurantProfileUpdateSerializer.validate_logo(self, value)`
- L280: `RestaurantProfileUpdateSerializer.validate_image(self, value)`
- L283: `RestaurantProfileUpdateSerializer.get_image_url(self, restaurant)`
- L286: `RestaurantProfileUpdateSerializer.get_logo_url(self, restaurant)`
- L290: `RestaurantOfferSerializer` ? class
- L293: `RestaurantOfferSerializer.Meta` ? class
- L314: `RestaurantOfferWriteSerializer` ? class
- L315: `RestaurantOfferWriteSerializer.Meta` ? class
- L330: `RestaurantOfferWriteSerializer.validate(self, attrs)`
- L346: `RestaurantTimingSerializer` ? class
- L349: `RestaurantTimingSerializer.Meta` ? class
- L362: `RestaurantTimingBulkSerializer` ? class
- L365: `RestaurantTimingBulkSerializer.validate(self, items)`
- L378: `RestaurantDocumentSerializer` ? class
- L383: `RestaurantDocumentSerializer.Meta` ? class
- L398: `RestaurantDocumentSerializer.validate_file(self, value)`
- L406: `RestaurantDocumentSerializer.get_file_url(self, document)`
- L410: `RestaurantEarningSerializer` ? class
- L415: `RestaurantEarningSerializer.Meta` ? class
- L439: `SettlementSerializer` ? class
- L443: `SettlementSerializer.Meta` ? class
- L463: `ReviewSerializer` ? class
- L477: `ReviewReplySerializer` ? class
- L480: `ReviewReplySerializer.validate_reply(self, value)`
- L487: `NotificationSerializer` ? class
- L497: `OrderItemSerializer` ? class
- L507: `DeliveryInfoSerializer` ? class
- L517: `PartnerOrderSerializer` ? class
- L544: `MenuCategoryPreviewSerializer` ? class
- L547: `MenuCategoryPreviewSerializer.Meta` ? class
- L551: `MenuCategoryPreviewSerializer.get_items(self, category)`
- L560: `RestaurantDetailSerializer` ? class
- L565: `RestaurantDetailSerializer.Meta` ? class
- L568: `RestaurantDetailSerializer.get_categories(self, restaurant)`
- L596: `RestaurantDetailSerializer.get_menu_items(self, restaurant)`
- L600: `RestaurantDetailSerializer.get_offers(self, restaurant)`

### `restaurant/services.py`

- L14: `record_order_earning(order)`
- L58: `cancel_order_earning(order)`
- L67: `restaurant_earnings_queryset(restaurant)`
- L71: `earnings_summary(restaurant, today)`
- L77: `earnings_summary.total_between(start)`
- L101: `payments_summary(restaurant)`
- L133: `restaurant_analytics(restaurant, days)`

### `restaurant/tests.py`

- L14: `RestaurantModelTests` ? class
- L15: `RestaurantModelTests.setUp(self)`
- L33: `RestaurantModelTests.test_restaurant_can_be_created(self)`
- L37: `RestaurantModelTests.test_menu_item_can_be_created(self)`
- L48: `RestaurantModelTests.test_bank_account_number_is_encrypted_in_database(self)`
- L65: `RestaurantModelTests.test_admin_approval_activates_restaurant(self)`
- L78: `RestaurantModelTests.test_pending_owner_dashboard_hides_operations(self)`
- L89: `RestaurantModelTests.test_restaurant_list_page_loads(self)`
- L96: `RestaurantModelTests.test_restaurant_list_redirect_preserves_search_and_location(self)`
- L106: `RestaurantModelTests.test_restaurant_dashboard_redirects_guests_to_owner_login(self)`
- L114: `RestaurantModelTests.test_customer_header_search_submits_to_customer_portal(self)`
- L120: `RestaurantModelTests.test_customer_list_welcomes_authenticated_customer_by_name(self)`
- L136: `RestaurantModelTests.test_guest_can_view_restaurant_menu_images_and_prices(self)`
- L153: `RestaurantModelTests.test_pending_restaurant_is_hidden_even_if_marked_active(self)`
- L169: `RestaurantModelTests.test_restaurant_search_matches_location(self)`
- L174: `RestaurantModelTests.test_restaurant_list_filters_by_state_and_city(self)`
- L212: `RestaurantModelTests.test_homepage_shows_all_approved_restaurants_then_filters_by_state(self)`
- L264: `RestaurantModelTests.test_customer_pages_do_not_render_gps_controls(self)`
- L273: `RestaurantModelTests.test_customer_dashboard_filters_approved_restaurants_by_state(self)`
- L316: `RestaurantModelTests.test_homepage_offers_all_restaurants_when_selected_state_has_no_matches(self)`
- L324: `RestaurantModelTests.test_customer_listing_offers_all_restaurants_when_selected_state_has_no_matches(self)`
- L335: `RestaurantModelTests.test_location_filter_uses_structured_fields_and_falls_back_to_state(self)`
- L388: `RestaurantModelTests.test_public_restaurant_api_returns_menu_data(self)`
- L401: `RestaurantModelTests.test_restaurant_menu_api_is_scoped_to_its_owner(self)`
- L432: `RestaurantModelTests.test_restaurant_owner_can_manage_menu(self)`
- L455: `RestaurantModelTests.test_pending_restaurant_owner_sees_customer_visibility_notice(self)`
- L475: `RestaurantModelTests.test_restaurant_owner_can_update_store_details(self)`
- L497: `RestaurantModelTests.test_owner_dashboard_shows_store_and_menu_details(self)`
- L522: `RestaurantModelTests.test_owner_dashboard_links_to_location_settings(self)`
- L536: `RestaurantModelTests.test_restaurant_location_update_api_get_and_post(self)`
- L572: `RestaurantModelTests.test_restaurant_location_update_api_permission_denied_for_customer(self)`
- L589: `RestaurantModelTests.test_restaurant_location_update_api_invalid_coords(self)`
- L601: `RestaurantModelTests.test_nearby_discovery_uses_saved_restaurant_coordinates(self)`
- L616: `RestaurantModelTests.test_restaurant_account_settings_view_authenticated(self)`
- L626: `RestaurantModelTests.test_restaurant_account_settings_unauthenticated_redirects(self)`
- L631: `RestaurantModelTests.test_restaurant_account_settings_non_owner_forbidden(self)`
- L643: `RestaurantModelTests.test_restaurant_account_settings_post_updates_db(self)`
- L679: `RestaurantModelTests.test_settings_url_redirects_restaurant_owner(self)`
- L684: `RestaurantModelTests.test_settings_url_keeps_customer(self)`

### `restaurant/views.py`

- L14: `restaurant_list_view(request)`
- L22: `restaurant_listing_context(request)`
- L227: `restaurant_detail_view(request, restaurant_id)`
- L241: `restaurant_management_view(request)`
- L301: `restaurant_account_settings_view(request)`
