# Food_Ex — Implementation Tasks (4 Backend Foundation Tasks)

## Task 1: Model Hardening + Add Moderation Fields + Database Migrations

**Priority**: high
**Status**: pending
**Maps to ACs**: AC-R5, AC-R6, AC-R7
**Depends on**: —

### Scope
1. Review every model (`Review model (add Review model
    - `moderation_note` (CharField 255 blank), `moderated_at` (DateTime null blank, `moderated_by` FK to User null blank, limit choices to admin role).
2. Verify existing models have all required fields from the spec (MenuCategory / RestaurantOffer / RestaurantEarning / Settlement / RestaurantTiming / RestaurantDocument / PlatformSetting).
3. Ensure Settlement model: add `earnings` M2M to RestaurantEarning with through table is overkill; instead add optional FK from RestaurantEarning.settlement FK to Settlement (nullable. Mark settlements with `null`, `on_delete=SET_NULL`, `related_name="earnings_set"`.
4. RestaurantEarning: add `delivery_fee`, `platform_fee` Decimal default=0` fields for fully transparent payout breakdown (`order_amount → commission → restaurant_amount formula in project_memory already specifies split: Restaurant payout = food + GST - 10% admin commission; Rider payout = fixed delivery fee; Admin revenue = platform fee + commission. Explicitly track these in the earning row.
5. Run `makemigrations` then `migrate`.

### Test Requirements (TRs)
#### Rule TRs
- **TR-R1**: `makemigrations --check` passes after the changes.
- **TR-R2**: Adding `Review model exposes `moderation_note`, `moderated_at`, `moderated_by` fields.
- **TR-R3**: RestaurantEarning row after seed can hold `delivery_fee` and `platform_fee`.

### Completion Evidence
- New migration files in each affected app present.
- `migrate` runs successfully on SQLite.
- `showmigrations` shows all migrations applied.

---

## Task 2: Restaurant Partner Full API Surface + Serializers

**Priority**: high
**Status**: pending
**Maps to ACs**: AC-R1, AC-Q1, AC-Q2
**Depends on**: Task 1

### Scope
Create serializers in `restaurant/serializers.py`:
- `RestaurantProfileSerializer` (write)
- `RestaurantOfferSerializer`, `RestaurantOfferWriteSerializer`
- `RestaurantTimingSerializer`TimingWriteSerializer` (bulk upsert)
- `RestaurantDocumentSerializer` (read-only upload support)
- `RestaurantEarningSerializer`, `SettlementSerializer`
- `RestaurantDashboardSerializer` (outputs all dashboard summary: order counts, revenue breakdown)
- `RestaurantOrderSerializer` (extends OrderSerializer with items + customer info + delivery info)

Create views in `restaurant/api_views.py`:
- **Dashboard**: `GET /api/restaurant/partner/dashboard/`
- **Profile**: `GET/PATCH /api/restaurant/partner/profile/` + `POST /api/restaurant/partner/profile/toggle-open/`
- **Categories CRUD**: `GET/POST /api/restaurant/partner/categories/` + `GET/PATCH/DELETE /api/restaurant/partner/categories/{id}/`
- **Menu Items CRUD**: move existing into partner-scoped endpoints
- **Timings**: `GET /api/restaurant/partner/timings/` + `PUT /api/restaurant/partner/timings/bulk/`
- **Documents**: `GET /api/restaurant/partner/documents/` + `POST /api/restaurant/partner/documents/`
- **Orders List by status + detail + accept/reject/prepare/ready
- **Delivery Info**: `GET /api/restaurant/partner/orders/{id}/delivery/`
- **Offers CRUD**: `GET/POST /api/restaurant/partner/offers/` + `PATCH/DELETE {id}/`
- **Reviews List + Reply**: `GET /api/restaurant/partner/reviews/` + `POST /api/restaurant/partner/reviews/{id}/reply/`
- **Earnings**: `GET /api/restaurant/partner/earnings/` (summary + rows)
- **Payments/Settlements**: `GET /api/restaurant/partner/payments/`
- **Notifications**: `GET /api/restaurant/partner/notifications/` + `POST {id}/read/`

Wire URLs in `restaurant/api_urls.py`.

Add helper `get_owned_restaurant(request)` returning 404/403 on missing role.

### Test Requirements (TRs)
#### Rule TRs
- **TR-R1**: Every list endpoint returns only objects belonging to the authenticated restaurant.
- **TR-R2**: Accepting another restaurant's order returns 403/404.
- **TR-R3**: Creating a menu item with `mrp=300`, `discount_percent=10` saves `price=270.00` server-side.

#### Rubric TRs
- **TR-Q1 Endpoint Consistency (0–2): 2 = uniform `/api/restaurant/partner/*` prefix, 4× grouping.
- **TR-Q2 Scope Isolation (0–2): 2 = every queryset `.filter(restaurant=owner_rest)` without exception.

### Completion Evidence
- `restaurant/api_urls.py` wires all routes above.
- Running the 3 `restaurant/serializers.py` contains every serializer listed.
- Manual curl-style self-test: login as restaurant, hit `/api/restaurant/partner/dashboard/ returns 200.

---

## Task 3: Admin Approval + Commission APIs + Review Moderation

**Priority**: high
**Status**: pending
**Maps to ACs**: AC-R3, AC-R4, AC-R7
**Depends on**: Task 1, Task 2

### Scope
Create `accounts/admin_api_urls.py` and `accounts/admin_views.py` (or extend `food_ex/admin_api_views.py` if no better spot):
- `GET /api/admin/restaurants/` — status filter, search by name/city.
- `POST /api/admin/restaurants/{id}/approve/`
- `POST /api/admin/restaurants/{id}/reject/` — requires reason.
- `POST /api/admin/restaurants/{id}/suspend/`
- `POST /api/admin/restaurants/{id}/commission/` — accepts 0–90 percent or null for default.
- `GET/PATCH /api/admin/platform/settings/`
- `POST /api/admin/reviews/{id}/moderate/` — sets `is_hidden`, `moderation_note`, `moderated_at`, `moderated_by`.

Customer-facing review filter: update `customer/api_views.py RestaurantReviewListAPIView` to exclude `is_hidden=True` for non-admin.

Wire `/api/auth/admin/` url prefix in food_ex/urls.py.

### Test Requirements (TRs)
#### Rule TRs
- **TR-R1**: Non-admin POST to `/api/admin/restaurants/{id}/approve/ returns 403.
- **TR-R2**: After approve, restaurant.status=="approved" and is_active=True.
- **TR-R3**: After moderate review with is_hidden=True disappears from `GET /api/customer/restaurants/{id}/reviews/.
- **TR-R4**: Platform settings PATCH with `default_commission_percent=15` persists and returns in next GET.

### Completion Evidence
- Admin API URLs wired.
- Self-test: approve a pending restaurant → status flips.
- Self-test: hide a review → disappears from public list.

---

## Task 4: Demo Seed Data Management Command + Earnings Hook Fixes

**Priority**: medium
**Status**: pending
**Maps to ACs**: AC-R5, AC-Q3
**Depends on**: Task 1, Task 2, Task 3

### Scope
1. Create `restaurant/management/commands/seed_demo_data.py` (or `accounts/management/commands/seed_demo_data.py`) with all objects:
   - Admin user: `admin@foodex.in` / password in docs.
   - Customer: `rahul@foodex.incustomer + profile with phone, address in "Bangalore".
   - 2 Delivery partners in Bangalore lat/long ~ (12.97, 77.59) + vehicles + vehicles + is_online=True.
   - 2 Restaurants: "Ramesh Biryani Point" (Biryani, Non-Veg,  FSSAI "12345678901234", lat/long 12.9716, 77.5946) and "Sagar Veg" (South Indian, Veg lat/long 12.9352, 77.6245) — both status=approved, is_active=True.
   - 4 MenuCategories × 3 MenuItems each per restaurant with realistic prices (e.g. Biryani 249, Chicken 65 180, etc.).
   - 7 RestaurantTiming each day Mon–Sun 09:00 – 23:00 per restaurant.
   - 1 RestaurantOffer per restaurant (e.g. 20% off min ₹300, cap ₹100).
   - 1 PlatformSetting default (commission 15%, GST 5%, delivery 40).
   - 1 delivered order: chicken biryani × 2 from Ramesh Biryani Point → earning row, paid via test payment → + review (4 stars + comment).

2. Verify earnings hook: ensure in `delivery/services.py` `advance_assignment delivered calls `record_order_earning` and also `cancel_order_earning` is called in order cancel in the reject/cancel path in `orders/services.py`. Confirm RestaurantEarning now also records `order_amount = food subtotal - commission% + tax_amount → matches project_memory: Food+GST-10% commission`.

### Test Requirements (TRs)
#### Rule TRs
- **TR-R1**: `python manage.py seed_demo_data` runs twice without IntegrityError.
- **TR-R2**: After seed ≥ 2 restaurants approved, ≥ 24 menu items, ≥ 2 partners.
- **TR-R3**: Delivered demo order has an RestaurantEarning row with status=pending, correct commission split, and a review.

#### Rubric TRs
- **TR-Q1 Seed walkthrough (0–2): 2 = can walk login→browse→order→pay→delivered earning appears in earnings API.

### Completion Evidence
- Script exists and runs.
- Output of `seed_demo_data` printed (or run screenshot/log captured).
- DB query confirming object counts match.

---

## Review Issues

None yet. Populated during Review phase.
