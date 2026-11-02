# Testing and debugging

## Actual test files and observed result

| Test file | Coverage evidenced by test names/content |
|---|---|
| `accounts/tests.py` | Role choices, registration/login, fixed-role portals, password reset/change, profiles, dashboard access, JWT endpoints, role sessions, account deletion and ownership. |
| `customer/tests.py` | Customer profile privacy/update and review eligibility for delivered orders. |
| `customer/test_dashboard.py` | Customer dashboard listing card layout. |
| `delivery/tests.py` | Delivery status/ownership, manual and automatic assignment, nearest/stale partner selection, timeout/history/retry, notifications, COD and full order delivery. |
| `location/tests.py` | Coordinate/location updates, saved addresses, nearby search, order tracking and access checks. |
| `notifications/tests.py` | Notification service/API ownership and read behavior. |
| `orders/tests.py` | Cart/checkout/order snapshots, legal status transitions, cancellation, ownership and totals. |
| `payments/tests.py` | Mock/COD, invalid payment methods, duplicate payment and refund behavior. |
| `restaurant/tests.py` | Restaurant/menu/partner APIs, profile and owner permissions, offers/earnings/reviews and admin-related behavior. |

### Validation run in this audit

- `python manage.py check --settings=food_ex.settings.dev` — **passed**, no issues silenced.
- `python manage.py test --settings=food_ex.settings.dev` with `USE_SQLITE=True` — **passed: 174 tests**.
- `python manage.py makemigrations --check --dry-run --settings=food_ex.settings.dev` — **not clean**: reports a migration for `LocationSetting.tile_layer_attribution` and `tile_layer_url`.

The test run used SQLite to avoid depending on an unknown local database configuration. It does not prove production MySQL compatibility or inspect production data.

## Migration discrepancy

`LocationSetting` current model defaults for tile URL/attribution differ from migration state. `makemigrations --check --dry-run` proposes:

```text
location: AlterField tile_layer_attribution
location: AlterField tile_layer_url
```

No migration was created or applied. Confirm whether these default changes are intended, create a reviewed migration, then test migration forward/backward on a disposable database before deployment.

## Practical local commands

From `D:\programing\Food_Ex` in PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
$env:DJANGO_SETTINGS_MODULE = "food_ex.settings.dev"
python manage.py check
python manage.py test
python manage.py showmigrations
python manage.py makemigrations --check --dry-run
```

Use the real configured environment for ordinary development. For an isolated SQLite test run:

```powershell
$env:USE_SQLITE = "True"
python manage.py test --settings=food_ex.settings.dev
```

Do not run migrations against a production database as an exploratory test.

## Recommended manual plan beyond unit tests

1. Register/login with each role and confirm a mismatched account cannot enter another portal.
2. Register a restaurant; confirm it is not publicly orderable before admin approval.
3. Add menu items; test unavailable item, cross-restaurant cart, quantity limit, empty checkout and invalid saved-address ID.
4. Verify server totals for offer, tax, delivery fee and minimum order; tamper with client totals and confirm they are ignored.
5. Exercise restaurant accept/reject/prepare/ready/cancel transitions in invalid and valid order.
6. Test COD, mock payment only in development, unsupported card/UPI rejection, duplicate payment, refund bookkeeping.
7. Test delivery assignment with missing/stale coordinates, busy/offline partners, timeout, rejection, max attempts, retry and manual assignment acceptance.
8. Test delivery status sequence and ensure one partner cannot view/update another partner's assignment.
9. Test GPS permission denied/unavailable/stale coordinates, coordinate bounds, assignment mismatch, order ownership, and browser polling stop on terminal state.
10. Test saved address privacy, review rules, hidden-review filtering, notification ownership, admin role rejection, file upload size/type, and API error response shapes.
11. Run the same focused integration tests against a disposable MySQL test database before claiming MySQL deployment compatibility.

## Debugging 403/401

- Determine the authenticated principal and role; the role-session middleware can intentionally make the user anonymous on a different portal.
- Check the route prefix and active role, CSRF cookie/header, and whether JWT/session authentication was used.
- For delivery GPS, verify the assignment exists, is active, and belongs to the current partner; for tracking, verify current user is order owner, assigned partner, restaurant owner, or admin/staff.
- A 403 generally indicates authenticated-but-disallowed role/ownership; 401 indicates authentication was absent/invalid. DRF/session-auth configuration can affect the exact status.
- Do not solve an ownership error by weakening the permission check; fix the client identity/ID or correct assignment.

## Not validated in this audit

- Live MySQL connectivity and schema parity.
- Browser rendering and accessibility across browsers.
- Actual geolocation permission and physical GPS accuracy.
- External tile, Nominatim, and routing service uptime/limits.
- Real payment gateway, payout transfer, email delivery, production HTTPS and secure headers.
- Load/concurrency behavior under simultaneous checkouts or dispatch.
- Security testing of uploads, XSS, rate limits, and production deployment.
