# Complete file structure and source inventory

## Scope and counting

This is an inventory of 241 relevant files present before these documentation files were created. The scan included Python source, migrations, tests, all HTML templates, application static CSS/JS, setup/database support files, and project notes. It excluded `.env`, `database_data.txt`, local database files, `venv/`, uploaded `media/`, caches, generated static output, and compiled Python files. The contents of excluded potentially sensitive data were not read or reproduced.

The complete 49-template explanation is in [TEMPLATE_BY_TEMPLATE_GUIDE.md](./TEMPLATE_BY_TEMPLATE_GUIDE.md); JavaScript and CSS usage is in [JAVASCRIPT_AND_FRONTEND_FUNCTIONS.md](./JAVASCRIPT_AND_FRONTEND_FUNCTIONS.md); Python symbols are indexed in [DJANGO_BACKEND_FUNCTIONS.md](./DJANGO_BACKEND_FUNCTIONS.md). Those documents provide the per-file responsibilities without repeating the same explanation in three places.

## High-level tree

```text
Food_Ex/
├── accounts/       custom user, auth, role sessions, account APIs and templates
├── customer/       customer profile, saved addresses, reviews
├── delivery/       partners, assignments, delivery workflow and GPS API
├── food_ex/        project settings, root URLs, shared views/templates/static
├── location/       location settings, geospatial services, map pages and APIs
├── notifications/  notifications and API/page surfaces
├── orders/         cart, orders, status events, checkout and tracking
├── payments/       payment records, mock/COD service and payment page
├── restaurant/     restaurant/menu/partner APIs, services, forms and admin
├── templates/      project-level shared/legacy templates
├── database/       MySQL setup/import/sample SQL and database instructions
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

## Python files by app

### Project entry, configuration, and root URLs

| File | Type and responsibility |
|---|---|
| `manage.py` | Django command entry point; calls `execute_from_command_line`. |
| `food_ex/__init__.py` | Python package marker. |
| `food_ex/admin.py` | User admin customization/registration. |
| `food_ex/apps.py` | `FoodExConfig` application configuration. |
| `food_ex/asgi.py`, `food_ex/wsgi.py` | ASGI/WSGI deployment entry points. |
| `food_ex/urls.py` | Root URL tree and DEBUG-only media serving. |
| `food_ex/views.py` | Customer homepage query/context. |
| `food_ex/settings/__init__.py` | Settings package marker. |
| `food_ex/settings/base.py` | Shared apps, middleware, templates, database, auth, DRF/JWT, email, static/media and map settings. |
| `food_ex/settings/dev.py`, `food_ex/settings/prod.py` | Development and production overrides. |

### `accounts/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py` | Package and Django app configuration. |
| `admin.py`, `admin_api_urls.py`, `admin_views.py` | Admin registration and authenticated, admin-role API endpoints. |
| `api_urls.py`, `api_views.py` | Role-specific/general API registration, login, profile, deletion, logout and JWT refresh. |
| `urls.py`, `views.py` | Portal/page routes, account forms, password flows, dashboards and legacy JSON views. |
| `decorators.py` | Role-required view decorator. |
| `forms.py`, `serializers.py` | Browser registration form and API validation/serialization. |
| `middleware.py`, `session_utils.py` | Per-role request user resolution and role-session operations. |
| `models.py` | Custom `User`. |
| `tests.py` | Authentication, role session, dashboard, registration, password and account deletion tests. |
| `migrations/0001_initial.py`, `0002_alter_user_email.py`, `migrations/__init__.py` | User schema history. |

### `customer/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py`, `admin.py` | Package, app config, and customer/review admin. |
| `api_urls.py`, `api_views.py`, `serializers.py` | Public review listing, customer review creation and review representation. |
| `urls.py`, `views.py` | Profile and review page routes/views. |
| `models.py` | Customer profile, saved addresses, reviews. |
| `tests.py`, `test_dashboard.py` | Customer profile privacy/update, review eligibility and dashboard layout tests. |
| `migrations/0001_initial.py` through `0006_customeraddress_area_customeraddress_district_and_more.py`; `migrations/__init__.py` | Profile, review, and address schema history. |

### `restaurant/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py`, `admin.py` | Package, app configuration, admin actions and model admin. |
| `api_urls.py`, `api_views.py` | Public restaurant/menu endpoints and simple owner menu management. |
| `partner_api_views.py`, `partner_compat_urls.py` | Restaurant-owner dashboard/profile/categories/menu/timing/documents/orders/offers/reviews/earnings/payments/notifications APIs and compatibility routes. |
| `urls.py`, `views.py` | Restaurant pages, listing context, management and account settings. |
| `fields.py` | `EncryptedCharField` for restaurant bank-account data. |
| `forms.py`, `serializers.py` | Restaurant registration/profile validation and API representations. |
| `models.py` | Restaurant, menus, offers, operating times, documents, earnings and settlements. |
| `services.py` | Earnings recording/cancellation, summary calculations, payment summary and restaurant analytics. |
| `tests.py` | Restaurant, API, menu, order and partner-flow coverage. |
| `management/commands/seed_demo_data.py` and its `__init__.py` files | Explicit demo-data command; not run during this audit. |
| `migrations/0001_initial.py` through `0011_restaurant_area_restaurant_delivery_radius_km_and_more.py`; `migrations/__init__.py` | Restaurant domain schema history. |

### `orders/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py`, `admin.py` | Package/app config and order/cart admin, including retry action. |
| `api_urls.py`, `api_views.py`, `serializers.py` | Cart/order/status APIs and JSON representation. |
| `urls.py`, `views.py` | Cart, checkout, order history/detail, restaurant order management and state-action pages. |
| `models.py` | Cart, cart item, order, order item, and order status event. |
| `services.py` | Server-side totals, offer checks, atomic order creation, transition/authorization rules, status history and cancellation/refund hooks. |
| `tests.py` | Cart, checkout, transitions, payment integration and order lifecycle tests. |
| `migrations/0001_initial.py` through `0008_alter_order_status_orderstatusevent.py`; `migrations/__init__.py` | Order schema history. |

### `delivery/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py`, `admin.py` | Package/app config and delivery admin. |
| `api_urls.py`, `api_views.py` | Partner dashboard, availability, offers, assignment progression, history and location APIs. |
| `urls.py`, `views.py` | Delivery portal pages and POST actions. |
| `models.py` | Partner profile, current assignment, per-offer attempt history and location samples. |
| `services.py` | Assignment selection, timeout/retry, manual assignment, notification, accept/reject, lifecycle advancement and COD settlement bookkeeping. |
| `tests.py` | Assignment, timeout, role, GPS, lifecycle and transition tests. |
| `migrations/0001_initial.py` through `0007_alter_deliveryassignmentattempt_status.py`; `migrations/__init__.py` | Delivery schema history. |

### `location/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py`, `admin.py` | Package/app config and location settings/address admin. |
| `api_urls.py`, `api_views.py` | GPS update, addresses, nearby search, order tracking/routes and admin live view. |
| `urls.py`, `views.py` | Customer, restaurant, and admin location pages. |
| `models.py` | Map and location/assignment configuration (`LocationSetting`). |
| `services.py` | Coordinate validation, distance/ETA, reverse geocoding, geofence, routing and nearby restaurant query. |
| `tests.py` | Location validation, update, tracking and nearby behavior tests. |
| `migrations/0001_initial.py`, `0002_locationsetting_partner_location_max_age_seconds.py`, `0003_locationsetting_delivery_assignment_accept_timeout_seconds_and_more.py`, `migrations/__init__.py` | Location setting schema history; current model defaults differ in two fields, see [TESTING_AND_DEBUGGING.md](./TESTING_AND_DEBUGGING.md). |

### `payments/`

| File(s) | Responsibility |
|---|---|
| `__init__.py`, `apps.py`, `admin.py` | Package/app config and payment admin. |
| `api_urls.py`, `api_views.py` | Order payment API. |
| `urls.py`, `views.py` | Payment page. |
| `models.py` | Payment/refund state. |
| `services.py` | Mock provider, COD, payment idempotency, notifications, and refund bookkeeping. |
| `tests.py` | COD/mock/refund behavior tests. |
| `migrations/0001_initial.py` through `0003_alter_payment_options_payment_provider_and_more.py`; `migrations/__init__.py` | Payment schema history. |

### `notifications/`

| File(s) | Responsibility |
|---|---|
| `apps.py`, `admin.py`, `models.py` | App config, admin, notification record. |
| `api_urls.py`, `api_views.py` | Authenticated notification list and mark-read endpoint. |
| `urls.py`, `views.py` | Notification page and page-level read action. |
| `services.py` | Shared notification creation helper. |
| `tests.py` | Notification ownership and display/API tests. |
| `migrations/0001_initial.py`, `migrations/__init__.py` | Notification schema history. |

### Cross-app support and assets

| Paths | Responsibility |
|---|---|
| `accounts/static/accounts/css/accounts.css`, `accounts/static/accounts/js/auth.js` | Account/auth styling and browser auth/profile behavior. |
| `customer/static/customer/css/customer.css`, `customer/static/customer/js/dashboard.js` | Customer presentation and customer-location helper. |
| `delivery/static/delivery/css/delivery.css`, `delivery/static/delivery/js/dashboard.js`, `delivery/static/delivery/js/detail.js` | Delivery portal styling, request polling, and delivery map/GPS behavior. |
| `food_ex/static/food_ex/css/food_ex.css` | Shared shell and dashboard styles. |
| `location/static/location/css/location.css`, `location/static/location/css/location-app.css`, `location/static/location/js/*.js` | Map styles and five location/GPS page scripts plus shared map/GPS library. |
| `orders/static/orders/css/orders.css`, `orders/static/orders/js/order-live-tracking.js`, `orders/static/orders/js/order-tracking.js` | Order presentation and tracking scripts. |
| `payments/static/payments/css/payments.css`, `notifications/static/notifications/css/notifications.css`, `restaurant/static/restaurant/css/restaurant.css` | App-specific styles. |
| `accounts/templates/auth/*` | Registration/login, password/account pages and reset email/subject text templates. |
| `customer/templates/customer/profile.html`, `delivery/templates/delivery/*`, `food_ex/templates/*`, `location/templates/location/*`, `notifications/templates/notifications/*`, `orders/templates/orders/*`, `payments/templates/payments/*`, `restaurant/templates/restaurant/*` | Role/domain HTML pages; all 49 HTML files are itemized in the template guide. |
| `templates/includes/*`, `templates/restaurant/*` | Project-level includes and legacy/compatibility templates; some have no direct render call in current URL/view scan. |

## Non-Python support files

| Path | Purpose |
|---|---|
| `README.md` | Setup and feature overview. Some API summaries are abbreviated; use the API reference for actual URL routing. |
| `requirements.txt` | Python dependency manifest. |
| `.env.example` | Names/placeholders for environment configuration; actual `.env` was not read. |
| `.gitignore` | Ignore rules. |
| `database/README.md` | Database setup/import guidance. |
| `database/mysql_setup.sql` | MySQL setup SQL. |
| `database/mysql_export_example.sql` | Example schema/export SQL; not proof of deployed schema. |
| `database/sample_data.sql` | Example/sample SQL data. |
| `database/import_mysql.ps1` | Windows database import helper. |
| `.claude/agents/claude.agent.md`, `.trae/specs/spec.md`, `.trae/specs/tasks.md` | Project/agent notes, not runtime Django modules. |
| `accounts/templates/auth/password_reset_email.txt`, `password_reset_subject.txt` | Password reset email body and subject. |
| `restaurant/management/commands/seed_demo_data.py` | Demo seeding utility; not run. |
| `export_db.py` | Database export utility; not run or inspected for data output. |

## Organization and safe reorganization notes

- App-namespaced `static/<app>/` and app `templates/<app>/` follow Django discovery conventions. Keep those names consistent with static/template references.
- `food_ex/settings/` intentionally separates base, dev, and prod settings. Do not move settings or rename apps without updating `DJANGO_SETTINGS_MODULE`, migrations, imports, and deployment configuration.
- `templates/restaurant/` duplicates some `restaurant/templates/restaurant/` names. Django template loader precedence depends on `TEMPLATES['DIRS']` and `APP_DIRS`; first verify which copy renders before deleting or moving anything.
- Migration files are historical schema instructions, not ordinary cleanup candidates. Never edit or remove applied migrations to “tidy” the tree.
- `database_data.txt`, `.env`, local databases, `media/`, and generated folders were deliberately excluded from content inspection. Do not add their contents to documentation.
