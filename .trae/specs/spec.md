# Food_Ex Restaurant Partner — Spec (Remaining Backend Foundation)

## Problem
The Food_Ex backend has the core domain models, services, and customer/cart/order flow in place — but three critical backend layers are still missing:
1. The **Restaurant Partner REST API surface** (orders, categories, offers, earnings, payments, timings, documents, profile, dashboard) that the partner dashboard will call.
2. The **Admin Approval & Commission REST API** (approve/reject/suspend restaurants, set platform & per-restaurant commission).
3. **Review reply & moderation** endpoints so restaurants can reply to customer reviews and moderation can hide them.

Without these four pieces, the partner frontend and admin tooling have no server contract to speak to, and the end-to-end flow cannot be exercised with demo data.

## Users & Goals

| User | Goal |
|------|------|
| Restaurant Owner | Manage profile, menu, categories, offers, timings, documents; accept/reject/prepare orders; view deliveries, earnings, payments, reviews; reply to reviews; view analytics & notifications via a REST API. |
| Admin | List pending restaurants, approve/reject/suspend them, set platform-wide and per-restaurant commission, inspect earnings and settlements via API. |
| Platform Moderation | Hide inappropriate reviews from public listing. |

## Non-Goals
- No new payment gateway integration (mock/COD stays).
- No Django Channels / WebSocket layer — polling remains the real-time mechanism.
- No React/Vue rebuild — HTML + Vanilla JS stays.
- No multi-tenant SaaS features beyond single `PlatformSetting`.
- No printable invoice generation in this slice.

## Functional Requirements

### FR-1 — Restaurant Partner API (full surface)
For an authenticated `restaurant_owner` user, expose endpoints for:
- **Dashboard** (today/week/month stats, orders by status, menu counts, revenue, top items).
- **Profile** (get + update all fields including logo/cover, open/closed toggle, opening/closing times).
- **Menu Categories** CRUD scoped to the owner's restaurant.
- **Menu Items** CRUD using the existing `MenuItemWriteSerializer` (price server-side recomputed).
- **Timings** list + bulk upsert for 7-day opening/closing schedule.
- **Documents** list + upload + status (verified/rejected/pending) read-only view.
- **Orders** by status filter (`placed` / `accepted` / `preparing` / `ready_for_pickup` / `delivered` / `cancelled` / `rejected` / history with date ranges), order detail with items, customer info, payment status, and actions:
  - `POST .../orders/{id}/accept/` (requires `estimated_preparation_minutes`)
  - `POST .../orders/{id}/reject/` (requires `rejection_reason`, optional note)
  - `POST .../orders/{id}/prepare/`
  - `POST .../orders/{id}/ready/`
- **Delivery** info for orders that reached `ready_for_pickup` (partner name, phone, status, pickup time).
- **Offers** CRUD scoped to restaurant, including `is_currently_valid` pre-check.
- **Reviews** list with rating/comment/reply fields, `POST .../reviews/{id}/reply/`.
- **Earnings** summary (today/week/month/total gross, commission, net) + paginated per-order earning rows.
- **Payments** summary (total sales, commission, refunds, pending/paid settlements) + settlement list.
- **Notifications** list + mark-read.

Every queryset MUST be scoped to the authenticated restaurant owner. Never trust a `restaurant_id` posted from the client.

### FR-2 — Review Reply + Moderation
- `POST /api/restaurant/reviews/{id}/reply/` — owned-restaurant check, stores `restaurant_reply` + `replied_at`.
- `GET /api/customer/restaurants/{id}/reviews/` MUST exclude `is_hidden=True` reviews from unauthenticated + customer views.
- Admin-only `POST /api/admin/reviews/{id}/moderate/` toggles `is_hidden` with an optional `moderation_note`. (Field added to `Review`.)

### FR-3 — Admin Approval + Commission API
Authenticated `admin` role only:
- `GET /api/admin/restaurants/` with status filter (`pending` / `approved` / `rejected` / `suspended` / all).
- `POST /api/admin/restaurants/{id}/approve/` sets `status=approved`, `is_active=True`, `reviewed_at`, clears `status_reason`.
- `POST /api/admin/restaurants/{id}/reject/` requires `reason`, sets `status=rejected`, `is_active=False`, `status_reason`, `reviewed_at`.
- `POST /api/admin/restaurants/{id}/suspend/` optional `reason`.
- `POST /api/admin/restaurants/{id}/commission/` body `{commission_percent}` sets `Restaurant.commission_percent` (null = use platform default, 0-90 inclusive).
- `GET /api/admin/platform/settings/` — returns platform defaults.
- `PATCH /api/admin/platform/settings/` — updates `default_commission_percent`, `gst_percent`, `delivery_fee` (0–100 for percents, ≥0 for fees).

### FR-4 — Demo Data Seed Script + Database Migrations
- Run `makemigrations` then `migrate` so every existing model change is applied.
- Add a management command `seed_demo_data` that creates:
  - 1 admin user.
  - 1 customer profile (with phone, address, city).
  - 2 delivery partners (with vehicles, lat/long in the same city, `is_online=True`).
  - 2 approved restaurants (different cuisine, full menu: 4 categories × 3 items each, timings for the week, FSSAI/GST docs placeholders, a few active offers, lat/long same city).
  - 1 `PlatformSetting` default row.
  - Optionally 1–2 completed orders (delivered) with earnings records for end-to-end verification.
- Script MUST be re-runnable (uses `get_or_create`, checks for existing objects) and NOT break production data.

## Non-Functional Requirements
- **Security**: All endpoints (except public restaurant list/detail/menu/reviews, auth endpoints) require `IsAuthenticated` + explicit role assertion via 403, not just frontend hiding.
- **Money**: Every amount is a `Decimal` with 2dp half-up rounding; never trust client-posted prices/commissions/discounts.
- **Idempotency**: Approve/reject order actions return 409 if transition already happened (handled by existing `TRANSITIONS` map).
- **Validation**: Serializers return 400 with clear per-field messages.
- **Performance**: Dashboard summary endpoints use `annotate`/`aggregate` — no N+1 queries.
- **File uploads**: Images ≤ 5MB, JPG/JPEG/PNG/WEBP only; documents ≤ 10MB, PDF/JPG/PNG.

## Constraints, Dependencies, Assumptions
- Existing domain models (`Restaurant`, `MenuCategory`, `RestaurantOffer`, `RestaurantTiming`, `RestaurantDocument`, `RestaurantEarning`, `Settlement`, `PlatformSetting`, `Order`, `Payment`, `Review`, `DeliveryAssignment`) are the source of truth; only add fields if the spec needs them.
- Existing services (`restaurant.services.record_order_earning`, `orders.services.transition_restaurant_order`, `delivery.services.assign_ready_order`) must be reused — do not duplicate logic.
- `TIME_ZONE = Asia/Kolkata`, money displayed as ₹ with 2dp formatting handled by clients.
- Assumption: the `.env` keeps `USE_SQLITE=true` for local dev + demo seed; MySQL switch requires only env changes (already supported).
- Dependency: the `bank_account_number` `EncryptedCharField` in `Restaurant` is already implemented; do not change it.

## Open Questions (Resolved by Assumption)
1. Q: Should `Review.is_hidden` have a reason field? → A: Add `moderation_note` (CharField 255, blank, admin-only write) and `moderated_at` DateTime.
2. Q: Bulk or single timing endpoint? → A: Bulk upsert (list of 7 day entries) to keep frontend simple.
3. Q: Seed script as management command or standalone shell? → A: Django management command `python manage.py seed_demo_data` for portability.

## Acceptance Criteria

### Rule ACs
- **AC-R1**: An authenticated restaurant owner calling `/api/restaurant/partner/orders/?status=placed` receives ONLY orders owned by their restaurant with that status; trying to `POST .../accept/` on another restaurant's order returns 404/403.
- **AC-R2**: Posting an offer with `discount_value=30`, `discount_type="flat"`, `minimum_order_amount=200`, and an order of ₹180 produces exactly `discount=0` when `compute_order_totals` runs (already true; covered by integration-style seed with an order using the offer).
- **AC-R3**: Calling `/api/admin/restaurants/{id}/approve/` as a non-admin user returns 403; calling it as admin flips `status=approved`, `is_active=True`, sets `reviewed_at` to a non-null value.
- **AC-R4**: `/api/restaurant/partner/reviews/{id}/reply/` only succeeds when the review's `restaurant_id` matches the authenticated owner; stores `replied_at = now()` and `restaurant_reply`.
- **AC-R5**: `python manage.py seed_demo_data` runs without errors and creates ≥ 2 approved restaurants, ≥ 4 menu categories, ≥ 12 menu items, ≥ 2 delivery partners, ≥ 1 platform setting. Running it a second time does NOT raise IntegrityError and keeps the same object count (no duplicates).
- **AC-R6**: `python manage.py makemigrations --check` reports "No changes detected" after the implementation slice.
- **AC-R7**: Public review endpoint `/api/customer/restaurants/{id}/reviews/` returns zero rows for a review with `is_hidden=True`.

### Rubric ACs
- **AC-Q1 API Design (0–2)**: 2 = consistent URL structure (`/api/restaurant/partner/*`, `/api/admin/*`), clear verbs, paging for list endpoints, uniform envelope `{data}` or direct list, meaningful status codes. 1 = inconsistent but functional. 0 = ad-hoc paths returning mixed shapes.
- **AC-Q2 Code Organization (0–2)**: 2 = serializers/views/urls separated; service logic stays in `restaurant.services.py`, `orders.services.py`, and a new `accounts.admin_services.py`; no 500-line view files. 1 = some duplication but readable. 0 = monolithic blobs hard to change.
- **AC-Q3 Seed Fidelity (0–2)**: 2 = seed data actually exercises the full flow (menu items available for ordering, restaurant approved, delivery partners online & close by, one delivered order with an earning row and a review to reply to) — so the 47-step end-to-end spec can be walked by hand on a fresh DB. 1 = basic objects only, no demo flow. 0 = empty or broken seed.
