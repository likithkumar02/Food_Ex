# Template-by-template guide

## How to read this guide

The project has **49 HTML templates**. Each entry identifies role, purpose, route/view or whether it appears unused, inheritance, important content/data, actions, relevant JavaScript/API/CSS, resulting UI, oral explanation, and five concise viva questions/answers. A template being present does not prove a route renders it: entries marked **not found in a current render call** should be treated as legacy/unverified until traced.

Most pages extend `food_ex/templates/base.html` either directly or through a role base. The base provides shared navigation, messages, static styles, auth JavaScript, and fallback logout. The `TEMPLATES['DIRS']` order checks project `templates/` before app templates, so same-named project-level `templates/restaurant/*` copies can shadow `restaurant/templates/restaurant/*`.

## Accounts and password templates

### `accounts/templates/auth/delete_account_confirm.html`
- **Role/purpose/route:** Authenticated account owner; confirmation for `/delete-account/`; `accounts.views.delete_account_view`.
- **Inheritance/content:** Extends `base.html`; displays username and role, explains consequence and presents confirmation form plus cancel/navigation.
- **Data/actions:** `user.username`, `user.get_role_display`; POST to account deletion route; backend handles deletion and superuser guard.
- **JS/API/CSS/states:** Shared base/auth styling; no page-specific API. Confirmation page, validation/message and redirect states.
- **Viva:** “This page confirms a destructive account action before the view deletes the current user.”
- **Q&A:** Q: Why confirm? A: Avoid accidental deletion. Q: Which user is deleted? A: The authenticated request user. Q: Is it a JSON API? A: No, an HTML form. Q: What protects it? A: Authentication/role context and server checks. Q: What exception exists? A: Superusers cannot self-delete through the API deletion path.

### `accounts/templates/auth/forgot_password.html`
- **Role/purpose/route:** Public; `/forgot-password/`; `forgot_password_view`.
- **Inheritance/content:** `base.html`; email field, reset submit, error/message display.
- **Data/actions:** Django `PasswordResetForm`; POST submits email; backend returns a generic reset flow.
- **JS/API/CSS/states:** No page-specific JS; shared form styles/messages. Invalid email displays form errors; valid submission redirects to reset-done.
- **Viva:** “Django validates the submitted email and issues a single-use reset link when appropriate.”
- **Q&A:** Q: Does the page set a new password? A: No, it sends reset instructions. Q: What validates email? A: Django's reset form. Q: Does it reveal account existence? A: The design uses generic messaging. Q: Is email delivery live? A: Base settings use console email. Q: Which template follows? A: Password-reset-done.

### `accounts/templates/auth/login.html`
- **Role/purpose/route:** General sign-in page; `/login/`; `login_view`.
- **Inheritance/content:** `base.html`; email/password fields, submit and registration/reset links.
- **Data/actions:** Form POST handled by `accounts.views.login_view`, using Django authentication and role session helper.
- **JS/API/CSS/states:** Shared `auth.js` binds `loginForm` where present; validation/error/success notices and redirect.
- **Viva:** “The server authenticates credentials and stores a role session; the browser doesn't determine the account role.”
- **Q&A:** Q: What does login return? A: An HTML redirect. Q: Where is password checked? A: Django authentication. Q: What is role session? A: A separate portal identity stored in session. Q: Is this the JWT route? A: No, this is a page form. Q: How do errors appear? A: Django messages/template state.

### `accounts/templates/auth/password_change.html`
- **Role/purpose/route:** Authenticated account; `/password-change/`; `password_change_view`.
- **Inheritance/content:** `base.html`; current/new/confirmation password fields and field-level errors.
- **Data/actions:** Django `PasswordChangeForm` via POST; updates session auth hash on success.
- **JS/API/CSS/states:** Shared styles; no page-specific API. Invalid current/new password displays field errors.
- **Viva:** “Django's password form validates the old password and configured validators before saving a hash.”
- **Q&A:** Q: Is password stored in plaintext? A: No, Django stores a hash. Q: Why ask current password? A: To authorize sensitive change. Q: What validators run? A: Configured Django password validators. Q: Does user get logged out? A: Session hash is updated. Q: What is the endpoint type? A: Server-rendered form.

### `accounts/templates/auth/password_reset_complete.html`
- **Role/purpose/route:** Public completion state; `/password-reset/complete/`; Django `PasswordResetCompleteView`.
- **Inheritance/content:** Extends base; success confirmation and login link.
- **Data/actions:** No form/data; navigation returns user to login.
- **JS/API/CSS/states:** Shared styling; rendered only after successful reset confirmation.
- **Viva:** “This is the terminal confirmation page for Django's password reset flow.”
- **Q&A:** Q: What renders it? A: Django's built-in completion view. Q: Does it change the password? A: The preceding confirm view does. Q: Is a token shown? A: No. Q: What is its main action? A: Return to login. Q: Is this a REST endpoint? A: No.

### `accounts/templates/auth/password_reset_confirm.html`
- **Role/purpose/route:** Reset-link recipient; `/password-reset/<uidb64>/<token>/`; built-in `PasswordResetConfirmView`.
- **Inheritance/content:** Base template; new password fields or invalid/expired-link message.
- **Data/actions:** Django validates token and form submission; success goes to reset complete.
- **JS/API/CSS/states:** Shared styling; token-valid and invalid/expired states.
- **Viva:** “Django validates a single-use reset token before accepting a new password.”
- **Q&A:** Q: What is `uidb64`? A: Encoded user identifier. Q: Who validates token? A: Django's built-in view. Q: Can token be reused? A: Reset tokens are single-use/invalidated after change. Q: What happens on failure? A: Invalid-link message. Q: Is the token stored in this template? A: It is a URL parameter, not a database password.

### `accounts/templates/auth/password_reset_done.html`
- **Role/purpose/route:** Public reset-request acknowledgement; `/password-reset/done/`.
- **Inheritance/content:** Base; “check email” status and return link.
- **Data/actions:** No user data; Django built-in reset view renders it.
- **JS/API/CSS/states:** Shared styles; generic acknowledgement to reduce account enumeration.
- **Viva:** “The page confirms the request without exposing whether a matching account exists.”
- **Q&A:** Q: Is this the reset form? A: No, it follows submission. Q: Which view? A: Django `PasswordResetDoneView`. Q: Why generic text? A: Privacy. Q: Does it show a password? A: No. Q: Next step? A: Open the email reset link.

### `accounts/templates/auth/portal_login.html`
- **Role/purpose/route:** Customer, restaurant, or delivery portal; `/<portal>/login/`; `portal_login_view(role)`.
- **Inheritance/content:** Standalone template (not an `extends` child); role label, email/password form, portal navigation.
- **Data/actions:** `portal.label`; POST checks account role matches route before role session login.
- **JS/API/CSS/states:** Template-specific styling; `auth.js` is loaded by page/base wiring when included; displays messages for wrong-role credentials.
- **Viva:** “The route chooses the required role, and the server rejects an account from another portal.”
- **Q&A:** Q: Who chooses role? A: URL/view configuration. Q: What is checked? A: Credentials and role equality. Q: Why standalone? A: Portal-specific shell/layout. Q: What does success do? A: Redirects to that role dashboard. Q: How does failure appear? A: Django message/form state.

### `accounts/templates/auth/portal_register.html`
- **Role/purpose/route:** New account in selected portal; `/<portal>/register/`; `portal_register_view(role)`.
- **Inheritance/content:** Standalone; common account fields, conditional restaurant fields or delivery vehicle/license/address fields.
- **Data/actions:** `form`, `restaurant_form`, `portal`, registration errors and posted values; multipart POST for images. View fixes role from route and validates fields.
- **JS/API/CSS/states:** Browser constraint validation; relevant account styles. Success creates role/profile, login session and redirects; invalid submission re-renders errors.
- **Viva:** “One form serves multiple portals, but the server supplies the role and shows role-specific required fields.”
- **Q&A:** Q: How is role set? A: Server-side route parameter. Q: What extra restaurant data? A: Business profile and verification fields. Q: Delivery fields? A: Vehicle/license/address. Q: Is restaurant immediately public? A: No, it begins pending/inactive. Q: What does invalid data do? A: Re-render with errors.

### `accounts/templates/auth/register.html`
- **Role/purpose/route:** General/customer registration; `/register/`; `register_view`.
- **Inheritance/content:** Base; account registration fields and links.
- **Data/actions:** `UserRegistrationForm`; role choices are restricted to customer by the view.
- **JS/API/CSS/states:** `auth.js` binds registration when form IDs match; client validation and server form errors; success logs in/redirects.
- **Viva:** “The general registration page only creates a customer account; partner registration uses portal routes.”
- **Q&A:** Q: Can user choose admin? A: No. Q: What validates server-side? A: UserRegistrationForm. Q: Is password hashed? A: Django user manager. Q: What is created with user? A: CustomerProfile. Q: What happens after success? A: Session login and redirect.

### `accounts/templates/auth/settings.html`
- **Role/purpose/route:** Authenticated user account settings; `/settings/`; `settings_view`.
- **Inheritance/content:** Standalone settings layout; account fields and delivery partner-specific vehicle/license information when applicable.
- **Data/actions:** User and optional `partner_profile`; forms POST account updates, password action and deletion link.
- **JS/API/CSS/states:** Account CSS/shared messages; request is a server form, not a dedicated page API. Validation messages re-render.
- **Viva:** “The view supplies common user data and conditionally adds delivery profile data.”
- **Q&A:** Q: Which roles use it? A: Authenticated account roles. Q: Where is partner detail from? A: DeliveryPartnerProfile. Q: Does it render JSON? A: No. Q: Where are errors shown? A: Form/message area. Q: Why conditional fields? A: Role-specific profile.

## Customer templates

### `customer/templates/customer/profile.html`
- **Role/purpose/route:** Customer profile/account hub; `/customer/profile/` and `/profile/`; `customer_profile_view`.
- **Inheritance/content:** `portals/customer_base.html`; profile/address forms and order summary/count.
- **Data/actions:** `profile`, orders, order codes/status/restaurant/totals; form updates profile/address; links to history/review.
- **JS/API/CSS/states:** Customer CSS and shared auth; profile form post, displayed success/error messages. No direct script API call identified in template.
- **Viva:** “The view scopes profile and order data to the signed-in customer.”
- **Q&A:** Q: What data is private? A: User profile and owned orders. Q: Which model? A: CustomerProfile plus Order. Q: Can another user read it? A: View ownership checks prevent it. Q: How are validation errors shown? A: Form/messages. Q: Parent layout? A: Customer portal base.

## Delivery templates

### `delivery/templates/delivery/assignment.html`
- **Role/purpose/route:** Assignment status fragment/page; no direct current `render()` call found.
- **Inheritance/content:** Extends `base.html`; displays assignment status and order ID.
- **Data/actions:** Expects an `assignment`; no forms or JavaScript detected.
- **JS/API/CSS/states:** Shared base styles; no API call found. Mark as legacy/unverified.
- **Viva:** “This template exists, but I cannot claim it is part of the current page flow because no view renders it.”
- **Q&A:** Q: Which role? A: Intended delivery partner. Q: What does it show? A: Assignment and order status. Q: Which route renders it? A: Not found in current view calls. Q: Should it be deleted? A: Not without checking references. Q: What does the audit say? A: Present but unverified.

### `delivery/templates/delivery/dashboard.html`
- **Role/purpose/route:** Delivery partner dashboard; `/delivery/dashboard/`; `delivery_dashboard_view`.
- **Inheritance/content:** `portals/delivery_base.html`; availability control, active assignments, pending request feed and GPS status.
- **Data/actions:** `assignments`, `partner_profile`, order and restaurant/customer details; forms change availability/accept/reject.
- **JS/API/CSS:** `delivery/js/dashboard.js` and shared `location/js/location.js`; polls configured request URL and sends GPS.
- **States/output:** Online/offline, no deliveries, offer list, GPS failure/status.
- **Viva:** “The dashboard shows partner-owned assignments and polls offers while the partner is online.”
- **Q&A:** Q: Which model stores availability? A: DeliveryPartnerProfile. Q: How are offers refreshed? A: Ten-second fetch polling. Q: What does accept do? A: POST to scoped assignment action. Q: How is GPS obtained? A: Browser Geolocation API. Q: Is polling a background worker? A: No.

### `delivery/templates/delivery/detail.html`
- **Role/purpose/route:** Partner's assignment detail; `/delivery/detail/<id>/`; `delivery_detail_view`.
- **Inheritance/content:** Delivery portal base; order/restaurant/customer contact/address, route map, status and action controls.
- **Data/actions:** Assignment relation and order coordinate/status fields; POST forms for accept/reject/arrive/pickup/out-for-delivery/complete.
- **JS/API/CSS:** `location/js/location.js`, `delivery/js/detail.js`, map CSS; sends assignment-scoped GPS updates to `/api/location/delivery/update/`.
- **States/output:** Route and marker, current state, GPS error/completion.
- **Viva:** “The partner's route page uses the assignment ID to send authenticated GPS and exposes only legal state actions.”
- **Q&A:** Q: Who can open it? A: Assigned partner. Q: Which API receives GPS? A: Location delivery update. Q: What happens on 403? A: Tracking stops. Q: How does order advance? A: POST action/service. Q: Does map prove exact route? A: No, it is a visual/provider-dependent route.

## Shared shell and dashboards

### `food_ex/templates/base.html`
- **Role/purpose/route:** Shared shell for most site pages.
- **Inheritance/content:** Root template; title/style/navigation/content/JS blocks, messages and logout fallback form.
- **Data/actions:** Template URL tags and request/user context; links to role/account routes.
- **JS/CSS/API:** All app stylesheet references and `accounts/js/auth.js`; no page-specific API.
- **Output:** Common Bootstrap shell, navigation, message display and child content.
- **Viva:** “Child templates use Django blocks so navigation and assets are shared.”
- **Q&A:** Q: What is a template block? A: Child-overridable content section. Q: Where are messages rendered? A: Shared include. Q: How are styles loaded? A: Static tags. Q: What is fallback logout? A: Server POST form. Q: Does this access DB? A: Not by itself.

### `food_ex/templates/dashboard/admin.html`
- **Role/purpose/route:** Admin dashboard; `/dashboard/admin/`; `admin_dashboard_view`.
- **Inheritance/content:** `base.html`; user table and admin delete form.
- **Data/actions:** User list, username/email/role; POST deletion route with protections.
- **JS/API/CSS:** Shared styling; server-rendered page, no dedicated JS.
- **Output:** Admin-visible users and actions; errors/success through messages.
- **Viva:** “This dashboard shows user records to admins and delegates deletion to a protected POST view.”
- **Q&A:** Q: Who may see it? A: Admin role. Q: What fields display? A: Username/email/role. Q: How is delete submitted? A: POST form. Q: Can admin delete self? A: The view blocks it. Q: Is it the admin API? A: No, HTML dashboard.

### `food_ex/templates/dashboard/customer.html`
- **Role/purpose/route:** Customer dashboard; `/dashboard/customer/`; `customer_dashboard_view`.
- **Inheritance/content:** Customer portal base; account callout, restaurant discovery, location button and menu/restaurant cards.
- **Data/actions:** Restaurants, menu items, state and first name; GPS form may save current location.
- **JS/API/CSS:** `location/js/location.js`, `customer/js/dashboard.js`; customer location POST URL is embedded as a data attribute.
- **Output:** Personalized listing or empty-state messages; GPS error/status.
- **Viva:** “The dashboard combines server-filtered restaurants with an optional GPS-based location update.”
- **Q&A:** Q: Which view supplies restaurants? A: Customer dashboard view. Q: What if guest? A: Auth prompt/guest path. Q: How is GPS sent? A: Fetch POST. Q: Which model supplies restaurants? A: Approved active Restaurant. Q: What happens if state unavailable? A: Manual browsing remains.

### `food_ex/templates/dashboard/delivery.html`
- **Role/purpose/route:** Delivery workspace dashboard variant; `/dashboard/delivery/`; `delivery_dashboard_view`/role redirect as configured.
- **Inheritance/content:** Delivery portal base; active/recent assignments and counts.
- **Data/actions:** `active_count`, `delivery_count`, assignment status/address/order/restaurant.
- **JS/API/CSS:** Inherited delivery base styles; dashboard JS is loaded by delivery-specific dashboard template when used.
- **Output:** Assignment summaries or empty state.
- **Viva:** “This is a dashboard presentation; the delivery-specific page also contains availability and offer polling.”
- **Q&A:** Q: What is `active_count`? A: Active assignment count from view context. Q: What model? A: DeliveryAssignment. Q: Is it the detail page? A: No. Q: Which role? A: Delivery partner. Q: Where are actions handled? A: Delivery page/API views.

### `food_ex/templates/dashboard/restaurant.html`
- **Role/purpose/route:** Restaurant owner workspace; `/dashboard/restaurant/`; `restaurant_dashboard_view`.
- **Inheritance/content:** Restaurant portal base; restaurant details, menu and latest orders.
- **Data/actions:** Restaurant, item/menu/order counters and status data; links to management/orders.
- **JS/API/CSS:** Shared shell and restaurant CSS; no direct API request identified.
- **Output:** Summary plus orders/menu or missing-profile/empty states.
- **Viva:** “The owner dashboard aggregates the restaurant's own profile, menu, and incoming orders.”
- **Q&A:** Q: What scopes orders? A: Restaurant owner relationship. Q: What shows menu? A: MenuItem. Q: Can owner edit here? A: Navigation links to management. Q: What happens without restaurant? A: View redirects or prompts registration. Q: Parent? A: Restaurant portal base.

### `food_ex/templates/home.html`
- **Role/purpose/route:** Public/customer homepage `/`; `food_ex.views.home`.
- **Inheritance/content:** Base; search/location form, featured restaurants and dishes, empty states.
- **Data/actions:** `restaurant_cards`, `dish_cards`, counts/state; GET filters.
- **JS/API/CSS:** Base assets; no template-specific API call. Remote fallback images are selected by view if a model image is absent.
- **Output:** Homepage cards or “no approved”/empty messages.
- **Viva:** “The view filters approved active restaurants and available menu items before rendering homepage cards.”
- **Q&A:** Q: Which view? A: `home`. Q: Are cards generated in JS? A: No, server context. Q: What filters? A: State/district query. Q: Where do fallback images come from? A: Remote image URLs in view. Q: Is search a REST API? A: No, GET page filter.

### `food_ex/templates/portals/customer_base.html`
- **Role/purpose/route:** Shared customer storefront layout.
- **Inheritance/content:** Extends base; customer-specific header, location/search/navigation/account blocks.
- **Data/actions:** User/customer profile and query parameters; search/filter forms and navigation.
- **JS/API/CSS:** Base `auth.js`; location-specific scripts are loaded by child pages as needed.
- **Output:** Customer header/navigation reused by profile/cart/restaurant/tracking.
- **Viva:** “This child base lets customer pages share navigation and location controls.”
- **Q&A:** Q: Why inherit? A: Reduce duplicated layout. Q: Which data? A: User/profile/query state. Q: Does it own business logic? A: No. Q: Which child pages use it? A: Customer profile, restaurant list/detail, cart/tracking. Q: How are forms protected? A: CSRF tokens.

### `food_ex/templates/portals/delivery.html`
- **Role/purpose/route:** Delivery landing portal `/delivery/`; `delivery_portal_view`.
- **Inheritance/content:** Extends delivery base; intro, links to login/register, customer session notice and storefront links.
- **Data/actions:** `request.customer_user` role-session state.
- **JS/API/CSS:** Shared delivery base styles; no API.
- **Output:** Portal welcome or redirect to dashboard for logged-in delivery user.
- **Viva:** “The landing page introduces the delivery portal and does not itself assign work.”
- **Q&A:** Q: What view renders it? A: `delivery_portal_view`. Q: What if logged in? A: Redirect to dashboard. Q: Does it display GPS? A: No. Q: What user-specific value appears? A: Customer-session notice. Q: Which base? A: Delivery portal base.

### `food_ex/templates/portals/delivery_base.html`
- **Role/purpose/route:** Shared delivery layout.
- **Inheritance/content:** Extends base; delivery navigation and logout/account forms.
- **Data/actions:** User display name/email; POST logout actions.
- **JS/API/CSS:** Shared base/auth styles; role session routes.
- **Output:** Common delivery navigation around child content.
- **Viva:** “It is a layout, not a separate delivery workflow.”
- **Q&A:** Q: Parent? A: Main base. Q: What navigation? A: Delivery dashboard and account routes. Q: Why POST logout? A: Avoid state change by link. Q: Which user? A: Delivery role session. Q: Does it load GPS itself? A: No.

### `food_ex/templates/portals/restaurant.html`
- **Role/purpose/route:** Restaurant owner landing `/restaurant-partner/`; `restaurant_portal_view`.
- **Inheritance/content:** Extends restaurant base; intro, incoming-order/menu/customer-view links.
- **Data/actions:** Mostly static; logged-in owner is redirected by view.
- **JS/API/CSS:** Restaurant CSS through shell; no direct API.
- **Output:** Partner portal welcome and entry links.
- **Viva:** “This page is a portal entry point; actual restaurant management uses separate pages/APIs.”
- **Q&A:** Q: What role? A: Restaurant owner. Q: Does it display order list? A: No, it links to workspace. Q: What if already signed in? A: Dashboard redirect. Q: Which view? A: `restaurant_portal_view`. Q: Parent? A: Restaurant base.

### `food_ex/templates/portals/restaurant_base.html`
- **Role/purpose/route:** Shared restaurant owner shell.
- **Inheritance/content:** Extends base; custom `site_header` block and partner navigation context.
- **Data/actions:** Current user, route links.
- **JS/API/CSS:** Base and restaurant CSS; no API request.
- **Output:** Owner-specific header for dashboard/management/order views.
- **Viva:** “The template separates owner navigation from customer navigation.”
- **Q&A:** Q: Why separate portal bases? A: Roles need different navigation. Q: Is role authorization here? A: No, backend views enforce it. Q: Does it inherit base? A: Yes. Q: What does it provide? A: Header/navigation block. Q: Can it change data? A: No.

## Location templates

### `location/templates/location/admin_location.html`
- **Role/purpose/route:** Admin live GPS operations dashboard; `/location/admin/`; `admin_location_dashboard_view`.
- **Inheritance/content:** Base; metrics, map, active-order and partner lists.
- **Data/actions:** LocationSetting and metric context; refresh/select order actions.
- **JS/API/CSS:** `location/js/location.js`, `admin-location.js`; polls `/api/location/admin/live/`.
- **Output:** Fleet markers and active delivery summary; tile/provider errors handled in shared map.
- **Viva:** “The page is an admin map over an authenticated JSON feed; it refreshes periodically.”
- **Q&A:** Q: Who can access? A: Admin role. Q: Poll frequency? A: Ten seconds. Q: What does feed contain? A: Active delivery/partner/restaurant data. Q: Is it public? A: No. Q: Is marker data necessarily fresh? A: No, freshness is data-dependent.

### `location/templates/location/customer_location.html`
- **Role/purpose/route:** Customer location/address and latest-order tracking page; `/location/customer/`.
- **Inheritance/content:** Customer base; profile coordinates, saved-address list/forms, map, latest order/timeline.
- **Data/actions:** `profile`, `addresses`, `latest_order`, `setting`; update GPS/address and delete address actions.
- **JS/API/CSS:** location map/library and `customer-location.js`; `order-live-tracking.js` where latest order exists; customer address/location APIs.
- **Output:** Map, saved addresses, status and tracking where available.
- **Viva:** “The page combines a customer's saved-address CRUD with a protected latest-order tracking view.”
- **Q&A:** Q: Which models? A: CustomerProfile, CustomerAddress, Order. Q: How are addresses scoped? A: By current user. Q: Which API updates GPS? A: `/api/location/customer/update/`. Q: What happens without GPS? A: Manual address is possible. Q: How does order status refresh? A: Polling.

### `location/templates/location/restaurant_location.html`
- **Role/purpose/route:** Owner location page; `/location/restaurant/`; `restaurant_location_view`.
- **Inheritance/content:** Restaurant base; address fields, coordinate fields, map and GPS action.
- **Data/actions:** Restaurant and LocationSetting; owner saves GPS/address with form action.
- **JS/API/CSS:** `restaurant-location.js` and shared `location.js`; POST `/api/location/restaurant/update/`.
- **Output:** Editable marker/address and save feedback.
- **Viva:** “The owner selects or detects coordinates; the backend validates and stores them on Restaurant.”
- **Q&A:** Q: Which model stores location? A: Restaurant. Q: Who can update it? A: Owner-scoped API/page. Q: What service fills address? A: Reverse geocoding. Q: What if denied GPS? A: Manual map/address. Q: Which JS? A: restaurant-location.js.

## Notifications and order templates

### `notifications/templates/notifications/list.html`
- **Role/purpose/route:** Notification center `/notifications/`; `notification_center_view`.
- **Inheritance/content:** Base; list of notification title/message/date/link, unread indicators and read forms.
- **Data/actions:** User-scoped notifications; POST mark-read URL.
- **JS/API/CSS:** Notifications CSS; can use `/api/notifications/` counterpart but page form itself is server-side.
- **Output:** Empty/list states and updated read state.
- **Viva:** “Notification rows belong to one user and read changes are owner-scoped.”
- **Q&A:** Q: Which model? A: Notification. Q: Are all users' rows shown? A: No, current user's only. Q: How is read updated? A: POST page or PATCH API. Q: What categories exist? A: Order/payment/delivery/account. Q: Parent? A: Base.

### `orders/templates/orders/cart.html`
- **Role/purpose/route:** Customer cart `/orders/cart/`; `cart_view`.
- **Inheritance/content:** Customer base; item lines, quantities, restaurant, bill summary and empty state.
- **Data/actions:** Cart items and subtotal/tax/fee/discount/total; POST forms add/remove/update.
- **JS/API/CSS:** Orders CSS; template uses page POSTs rather than a detected cart API script.
- **Output:** Per-item subtotal and server-calculated total, or empty message.
- **Viva:** “The cart is stored per customer and checkout totals come from backend service logic.”
- **Q&A:** Q: Can cart mix restaurants? A: No. Q: What limits quantity? A: 20 per item. Q: What model? A: Cart and CartItem. Q: Where is total computed? A: Server. Q: What is empty state? A: Prompt to browse.

### `orders/templates/orders/cart_conflict.html`
- **Role/purpose/route:** Conflict response when adding a menu item from a different restaurant.
- **Inheritance/content:** Customer base; explains existing/new restaurant and keep/clear choices.
- **Data/actions:** Existing restaurant, menu item and selected restaurant; POST `decision=continue|clear`.
- **JS/API/CSS:** No page-specific JS; server returns HTTP 409 with page response when decision absent.
- **Output:** Keep current cart or clear then add item.
- **Viva:** “The one-restaurant rule is enforced by the view and this page asks for an explicit choice.”
- **Q&A:** Q: Why 409? A: Cart conflicts with another restaurant. Q: What are choices? A: Keep or clear. Q: Does page add item automatically? A: No, user chooses. Q: Where stored? A: CartItem. Q: Is this a REST response? A: HTML conflict page.

### `orders/templates/orders/checkout.html`
- **Role/purpose/route:** Customer checkout `/orders/checkout/`; `checkout_view`.
- **Inheritance/content:** Base; address selector/text and order summary.
- **Data/actions:** Cart and saved addresses; POST invokes `create_order_from_cart`.
- **JS/API/CSS:** Orders styles; no page JS API call detected. Server validates address/cart and redirects to payment.
- **Output:** Address errors and cart details or redirect to payment page.
- **Viva:** “The checkout page sends a selected saved address or entered text; server validates it and snapshots order data.”
- **Q&A:** Q: Which model contains saved addresses? A: CustomerAddress. Q: Who computes total? A: Backend. Q: What happens on empty cart? A: Redirect to cart. Q: Which service creates order? A: create_order_from_cart. Q: After success? A: Payment page redirect.

### `orders/templates/orders/detail.html`
- **Role/purpose/route:** Customer order detail/tracking; `/orders/orders/<id>/` and customer tracking alias.
- **Inheritance/content:** Customer base; order code/status/timeline, items, restaurant/contact, address, delivery section/map.
- **Data/actions:** Order snapshot and status values; cancellation/review links/forms where allowed.
- **JS/API/CSS:** `location/js/location.js`, `order-live-tracking.js`; polls tracking endpoint and updates timeline/map/phase.
- **Output:** Static snapshot plus refreshed status, partner, route/ETA/freshness or no-location message.
- **Viva:** “The page renders initial order data and then polls a protected endpoint for new tracking state.”
- **Q&A:** Q: Which user can access? A: Order owner. Q: Poll interval? A: Three seconds. Q: Is route always road-accurate? A: No. Q: What stops polling? A: Terminal/non-live order. Q: Which models? A: Order/OrderItem/Assignment/Location.

### `orders/templates/orders/history.html`
- **Role/purpose/route:** Customer history `/orders/orders/` or `/orders/orders/history/`; `order_history_view`.
- **Inheritance/content:** Base; past order cards, codes, restaurant, status and total; empty state.
- **Data/actions:** Current customer's orders ordered newest-first; links to detail.
- **JS/API/CSS:** Shared/orders CSS; no page API.
- **Output:** History rows or no-orders prompt.
- **Viva:** “The view filters orders by authenticated user and the template links to details.”
- **Q&A:** Q: How is privacy enforced? A: Query filters `user=request.user`. Q: How ordered? A: Newest first. Q: What is displayed? A: Code/status/restaurant/total. Q: Which model? A: Order. Q: Is it API? A: No, HTML.

### `orders/templates/orders/restaurant_management.html`
- **Role/purpose/route:** Restaurant order management `/orders/restaurant/orders/`; `restaurant_order_management_view`.
- **Inheritance/content:** Restaurant base; incoming order cards/items, payment/delivery assignment and status controls.
- **Data/actions:** Restaurant-scoped orders, item snapshots and delivery assignment/partner; POST accept/reject/cancel/prepare/ready/manual-assign forms.
- **JS/API/CSS:** Orders CSS; page posts to order action routes; partner API also available separately.
- **Output:** Pending and active order management or no incoming orders.
- **Viva:** “The owner sees only orders for their restaurant and each action calls a server transition.”
- **Q&A:** Q: How is restaurant chosen? A: From authenticated owner. Q: Can owner mark delivered? A: Delivery partner advances later states. Q: Which service? A: transition_restaurant_order. Q: How manual assignment works? A: Partner must accept. Q: Why status history? A: Audit/workflow trace.

## Payment templates

### `payments/templates/payments/home.html`
- **Role/purpose/route:** Marketing/restaurant discovery page; no current payment view render call found.
- **Inheritance/content:** Base; food imagery, favorites and location links.
- **Data/actions:** Expects restaurant cards; GET navigation.
- **JS/API/CSS:** Payments stylesheet may be included through shared base; no API found.
- **Output:** Static/legacy promotional content.
- **Viva:** “This file is present but is not the payment page used by the current payment route.”
- **Q&A:** Q: Which route renders it? A: None found in current view scan. Q: Is it an invoice? A: No. Q: What data does it expect? A: Restaurant cards. Q: Should it be removed? A: Only after reference checks. Q: Which page handles payment? A: payments/payment.html.

### `payments/templates/payments/payment.html`
- **Role/purpose/route:** Payment choice for order; `/payments/orders/<id>/payment/`; `payment_page`.
- **Inheritance/content:** Base; order total, payment method form, messages.
- **Data/actions:** Order total and supported methods; POST to payment view/service.
- **JS/API/CSS:** Payments CSS; no page-specific JS/API. COD or test payment flows according to settings.
- **Output:** Success/error message or redirect; unsupported live methods rejected.
- **Viva:** “This form collects a method, but the server creates payment state; the current provider is mock/COD.”
- **Q&A:** Q: Is card live? A: No provider configured. Q: How is mock reference created? A: Server provider. Q: What status for COD? A: Pending. Q: What prevents client proof? A: Server-generated transaction ID. Q: Which model? A: Payment.

## Restaurant templates

### `restaurant/templates/restaurant/account_settings.html`
- **Role/purpose/route:** Restaurant profile/account settings; `/restaurant/account-settings/`; `restaurant_account_settings_view`.
- **Inheritance/content:** Extends `restaurant/base.html`; user and restaurant fields, profile forms, error feedback.
- **Data/actions:** Restaurant profile and user account forms; POST saves through validated forms.
- **JS/API/CSS:** Restaurant CSS; server form submission, no direct API.
- **Output:** Updated account or field validation errors.
- **Viva:** “The page separates owner identity fields from restaurant business profile fields.”
- **Q&A:** Q: Which models? A: User and Restaurant. Q: What validates business data? A: Forms. Q: Is it public? A: No, owner-protected. Q: Parent? A: Restaurant base. Q: Does it call a JSON API? A: Not from template.

### `restaurant/templates/restaurant/base.html`
- **Role/purpose/route:** App-level restaurant layout, potentially shadowed by project template.
- **Inheritance/content:** Extends base; custom partner header.
- **Data/actions:** Common owner navigation; no model mutation.
- **JS/API/CSS:** Shared base assets and restaurant styles.
- **Output:** Wrapper for restaurant pages.
- **Viva:** “This is the app-local copy of a restaurant layout.”
- **Q&A:** Q: What is parent? A: base.html. Q: Which role? A: Restaurant owner. Q: Is it a view? A: No. Q: Could another copy shadow it? A: Yes, project template dirs come first. Q: Safe to delete? A: Only after loader/reference verification.

### `restaurant/templates/restaurant/detail.html`
- **Role/purpose/route:** Restaurant public menu detail `/restaurants/<id>/`; `restaurant_detail_view`.
- **Inheritance/content:** Customer base; restaurant identity/address/contact, category/menu cards and empty menu state.
- **Data/actions:** Restaurant and available menu items; add-to-cart POST forms.
- **JS/API/CSS:** Shared customer/restaurant styles; browser form posts into cart route.
- **Output:** Restaurant/menu and add actions; no-items message.
- **Viva:** “Public detail is shown only for an active approved restaurant and its menu.”
- **Q&A:** Q: Who is allowed? A: Public customer. Q: What filters menu? A: Availability. Q: How add item? A: POST form. Q: Which models? A: Restaurant/MenuItem. Q: What if no items? A: Empty state.

### `restaurant/templates/restaurant/list.html`
- **Role/purpose/route:** Customer restaurant discovery `/customer/`; `customer_portal_view` plus `restaurant_listing_context`.
- **Inheritance/content:** Customer base; search/location filters, restaurant cards, menu previews, distance/ETA/fallback messages.
- **Data/actions:** Query/profile/session location, restaurant cards and items; GET filter/search.
- **JS/API/CSS:** `location/js/location.js` and `customer-storefront-location.js`; may call detect endpoint, update URL and reload.
- **Output:** Filtered list or fallback/empty-state text.
- **Viva:** “The listing context chooses location filters and gracefully falls back when no local restaurant exists.”
- **Q&A:** Q: What statuses are listed? A: Approved and active. Q: Where search query comes from? A: GET `q`. Q: Does GPS set address? A: Detection enriches location then reloads list. Q: Which helper builds context? A: restaurant_listing_context. Q: Is listing API? A: HTML page; a separate API exists.

### `restaurant/templates/restaurant/management.html`
- **Role/purpose/route:** Restaurant menu/profile management `/restaurants/manage/`; `restaurant_management_view`.
- **Inheritance/content:** Restaurant portal base; restaurant details, menu list, add/edit/delete forms.
- **Data/actions:** Restaurant and MenuItems; owner POST forms update model rows.
- **JS/API/CSS:** Restaurant CSS; form posts; partner JSON APIs also exist but this template is server-rendered.
- **Output:** Menu/profile forms and validation/empty states.
- **Viva:** “The page gives the owner a server-rendered menu editor, while the same domain also exposes partner APIs.”
- **Q&A:** Q: Who owns the menu? A: The restaurant. Q: How edits are authorized? A: Owner-role view and scoped query. Q: Which model? A: MenuItem. Q: Image field? A: Optional menu image. Q: API or HTML? A: HTML form workflow.

## Project-level shared and legacy templates

### `templates/includes/messages.html`
- **Role/purpose/route:** Message fragment included by shared templates.
- **Inheritance/content:** No parent; loops Django messages and displays tags/text.
- **Data/actions:** `messages` context processor; no form/API/database.
- **JS/CSS:** Bootstrap alert classes/shared CSS.
- **Viva:** “This include displays one-time Django messages across pages.”
- **Q&A:** Q: What supplies messages? A: Django message framework. Q: Does it query DB? A: No, it reads request context. Q: Why include? A: Reuse. Q: What is `message.tags`? A: Display category. Q: Is it standalone route? A: No.

### `templates/includes/restaurant_navbar.html`
- **Role/purpose/route:** Shared/legacy restaurant/customer navigation fragment.
- **Inheritance/content:** No parent; account navigation and POST logout forms.
- **Data/actions:** user and customer profile image; role-specific links.
- **JS/API/CSS:** Shared Bootstrap classes, no direct API.
- **Viva:** “This include centralizes a navbar fragment; confirm which base includes it before changing.”
- **Q&A:** Q: What data? A: User/profile. Q: Why POST logout? A: State-changing action. Q: Does it render a page? A: No, fragment. Q: Is it necessarily active? A: Verify include call sites. Q: Which framework? A: Django templates.

### `templates/restaurant/account_settings.html`
- **Role/purpose/route:** Project-level duplicate of app account settings template; likely selected first by template loader.
- **Inheritance/content:** Extends `"restaurant/base.html"`; same owner/profile forms.
- **Data/actions:** `form`, validation errors, account/profile fields; POST.
- **JS/API/CSS:** Server form and shared/restaurant styles.
- **Viva:** “The project template directory precedes app directories, so this duplicate may shadow the app-local file.”
- **Q&A:** Q: Why duplicate? A: Legacy/project override. Q: Which one renders? A: Loader order indicates project copy first. Q: Is content identical? A: Both show same settings structure. Q: Safe to remove? A: Not without test. Q: What function renders? A: restaurant_account_settings_view.

### `templates/restaurant/base.html`
- **Role/purpose/route:** Project-level restaurant base, which takes precedence over app-local copy.
- **Inheritance/content:** Extends base, owner header block.
- **Data/actions:** Shared owner shell.
- **JS/API/CSS:** Shared base assets.
- **Viva:** “It is a template override selected before the app template path.”
- **Q&A:** Q: What does `DIRS` do? A: Adds project-level template search paths. Q: Why note precedence? A: Same-name template shadowing. Q: Does it enforce roles? A: No. Q: Parent? A: base.html. Q: How verify? A: Render a focused template test.

### `templates/restaurant/dashboard.html`
- **Role/purpose/route:** Legacy dashboard wrapper extending `dashboard/restaurant.html`; no direct current render call found.
- **Inheritance/content:** Inherits all output from the restaurant dashboard template.
- **Data/actions:** Uses its parent's context; no form.
- **JS/API/CSS:** Inherited styling; no direct API.
- **Viva:** “This is a compatibility wrapper rather than the primary dashboard template.”
- **Q&A:** Q: What is its parent? A: dashboard/restaurant.html. Q: Does it add content? A: No blocks are declared. Q: Is it currently rendered? A: No direct call found. Q: Should it be moved? A: Verify references first. Q: What view is primary? A: restaurant_dashboard_view.

### `templates/restaurant/location_settings.html`
- **Role/purpose/route:** Legacy alias extending `location/restaurant_location.html`; no direct current render call found.
- **Inheritance/content:** All page content inherited.
- **Data/actions:** Parent expects restaurant/settings context.
- **JS/API/CSS:** Inherited location map scripts/styles.
- **Viva:** “This file reuses the actual location page, but current route points to the app template.”
- **Q&A:** Q: What is parent? A: location/restaurant_location.html. Q: Does wrapper add fields? A: No. Q: Is it directly rendered? A: Not found. Q: Which route should be tested? A: `/location/restaurant/`. Q: Safe to delete? A: Only after reference checks.

## Template audit caveats

- Source/static scan found templates that are not directly rendered by a current view call (`delivery/assignment.html`, `payments/home.html`, and the three legacy project-level restaurant wrappers). Keep them until route/template-loader references are verified.
- `food_ex/templates/base.html` loads several app CSS assets globally. Actual selectors may be unused on a given page.
- API calls are generally in JavaScript, not HTML. The page-to-API mapping is in [JAVASCRIPT_AND_FRONTEND_FUNCTIONS.md](./JAVASCRIPT_AND_FRONTEND_FUNCTIONS.md) and [COMPLETE_API_REFERENCE.md](./COMPLETE_API_REFERENCE.md).
- Five Q&A entries per template are intentionally brief; for backend implementation answers, follow the linked view/service source.
