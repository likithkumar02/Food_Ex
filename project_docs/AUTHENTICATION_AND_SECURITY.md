# Authentication and security notes

This is a source-based explanation and improvement checklist, not a penetration test. No credentials, real tokens, database rows, or `.env` values were read or copied.

## Authentication paths

- `accounts.User` extends Django `AbstractUser`, so password hashing and Django's authentication backends are used.
- Password validators are configured in `food_ex/settings/base.py`: similarity, minimum length, common-password and numeric-password validators.
- Django session authentication supports server-rendered forms and same-origin APIs.
- DRF defaults to Simple JWT followed by session authentication. JWT access lifetime is 15 minutes; refresh lifetime is one day with rotation and blacklist-after-rotation.
- API login creates access/refresh tokens and calls role session login. Logout can blacklist the authenticated user's refresh token.
- `RoleSessionMiddleware` resolves customer, delivery, and restaurant roles separately according to request path and portal context.
- Password reset uses Django's reset-token views; base email backend prints email to the development console.

## Authorization and ownership controls found

- Page views use `role_required(...)` and/or Django `login_required`.
- Restaurant-owner APIs resolve the restaurant from `request.user`; partner methods do not trust a posted restaurant ID.
- Customer order/cart APIs scope data to `request.user`; detail and tracking methods use ownership checks.
- Delivery assignment actions and location writes check partner ownership.
- Review creation requires a customer and a delivered order owned by that customer; `Review.clean()` enforces order/restaurant consistency.
- Notifications are filtered by the current user.
- Admin API base class checks `role == "admin"` in addition to `IsAuthenticated`; location admin permission also accepts staff.

## CSRF, CORS, uploads, and payment

- `CsrfViewMiddleware` is enabled. Same-origin form/JS requests include CSRF tokens where implemented; DRF session-authenticated unsafe methods also use CSRF protection.
- CORS is restricted to configured allowed origins; credentials are enabled. Do not configure wildcard origins when credentials are used.
- Profile/menu/document serializers/forms include upload validation; inspect their size/type rules before changing upload handling.
- Payment state is server-owned. Client-provided transaction IDs are not proof; mock transaction IDs are generated server-side. Card/UPI are not a live provider integration.
- Bank-account field uses a custom encrypted field, but encryption key configuration/rotation must be handled securely.

## Findings and recommended follow-up

| Observation | Evidence / impact | Recommended action (not applied; approval required) |
|---|---|---|
| Development secret fallback is present in shared settings | `SECRET_KEY` falls back to a known unsafe development string; production settings import the same base module. The local `.env` was not inspected. | Fail startup in production when a strong secret is missing; keep development fallback isolated to dev settings. |
| Bank encryption key defaults to `SECRET_KEY` | `BANK_DATA_ENCRYPTION_KEY` falls back to the Django signing secret. Rotating one key can break decryption or couple separate security domains. | Require a dedicated key in production, document key rotation/backup, and test encrypted-field compatibility. |
| Production security flags need deployment review | `prod.py` sets `DEBUG=False` and host/CORS/CSRF lists, but no explicit Secure cookie/HSTS/SSL redirect values are visible in that file. | Run Django deploy checks behind the actual TLS/proxy configuration and set appropriate secure cookie/HSTS settings there. |
| Admin restaurant list uses stale field names | `accounts/admin_views.py` reads `Restaurant.cuisine` and `fssai_license_no`; current model defines `cuisine_type` and `fssai_number`. The list response can raise at runtime. | Align API fields and add a focused endpoint test after approval. |
| Admin and map scripts insert dynamic values into HTML | `location/static/location/js/admin-location.js` builds `innerHTML`/popup markup from API fields such as names, status, address; the map script also inserts popup HTML. If stored values are attacker-controlled, this can create stored DOM XSS. | Escape text/attributes and use DOM text nodes; sanitize only where rich markup is genuinely needed; test with hostile-looking fixture values. |
| Role middleware suppresses broad exceptions | `_resolve_role_user()` catches `Exception` around user lookup and treats failures as anonymous, which can hide database/session failures in logs. | Narrow the caught exception and log unexpected failures without exposing sensitive data. |
| No API throttling is configured globally | `REST_FRAMEWORK` sets authentication/permissions but no default throttle classes/rates. | Consider per-endpoint rate limits for login, registration, password reset and location writes. |
| Public/admin display data should remain scoped | Tracking and admin GPS payloads contain locations/contact fields. | Keep current ownership checks and add negative tests for every role/ID boundary before changing endpoints. |
| Role-specific sessions add complexity | Multiple role identities share a browser and middleware changes `request.user` based on URL/context. | Maintain tests for cross-portal sessions and redirects; avoid adding prefixes without updating middleware. |
| Upload validation should be rechecked at deployment | App-level extension/size checks do not replace content inspection, storage isolation, antivirus scanning, or safe serving. | Validate MIME/content and configure private storage for identity/business documents. |

These observations are not assigned formal vulnerability severities because the task requested project documentation rather than a security review. No source changes have been made.

## Privacy notes

- GPS coordinates, saved addresses, phone numbers, restaurant identity documents and banking data are sensitive.
- Never include real customer data in documentation/demo screenshots; use fictional examples.
- Do not commit `.env`, local DB files, exported database text, real uploads, access tokens, or production encryption keys.
- External geocoding/routing providers may receive coordinates; review consent and privacy disclosures before deployment.

## Viva-safe explanation

> “Django stores hashed passwords, and the application uses role checks plus object ownership filters. The browser can use sessions or JWT, and unsafe session requests require CSRF protection. Payment status is decided by the server; the current payment provider is a mock/COD implementation. I also identified configuration and dynamic HTML risks that should be resolved before production.”
