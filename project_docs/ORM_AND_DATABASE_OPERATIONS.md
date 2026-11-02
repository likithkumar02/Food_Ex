# ORM and database operations

## Core models and query patterns

The project uses Django QuerySets and model methods rather than direct SQL in its runtime business logic. SQL files under `database/` are setup/sample/export artifacts, not evidence that the running app uses that exact schema. The configured database backend comes from `food_ex/settings/base.py`; SQLite is the source default, while MySQL is selected through environment configuration.

## ORM operations found in the application

| ORM method/pattern | Example location and meaning |
|---|---|
| `objects.create()` | `orders.services.create_order_from_cart` creates an `Order`, `OrderStatusEvent`, and `OrderItem` rows; `payments.services.PaymentService.process` creates a payment. Equivalent to `INSERT`. |
| `objects.get()` | `delivery.services.assign_ready_order` locks/reloads one order by primary key; `LocationSetting.load()` uses `get_or_create`. Equivalent to a filtered `SELECT`, raising `DoesNotExist` if absent. |
| `objects.filter()` | Used throughout for requester ownership, active state, role, restaurant, time range and related status. Equivalent to `SELECT ... WHERE`. |
| `.first()` / `.exists()` / `.count()` | Used for optional single row, existence checks, and aggregate counts. `first()` returns `None`; `exists()` produces an existence query. |
| `get_object_or_404()` | Used by page/API views to scope an object and return 404 if missing. The scoped queryset can include ownership (`user=request.user`) to prevent ID-based access to another user's resource. |
| `.save()` / `update_fields=` | Model updates, often limited to changed fields. Equivalent to `UPDATE`; model overrides such as `Order.save()` may also maintain fields/codes. |
| `.update()` | Used for bulk state changes such as resetting default addresses and marking earning status. Direct queryset update does not call each model's `save()` override or emit per-row model signals. |
| `.delete()` | Used for cart cleanup, account cascade deletion and deletion of owned cart/address/menu records. Database foreign-key `on_delete` rules define cascades/set-null behavior. |
| `select_related()` | Used for FK/one-to-one reads (`Order.restaurant`, cart item menu/restaurant, assignment order) to join-related rows in the SQL query. |
| `prefetch_related()` | Used for reverse/many-valued relations such as order items and menus, typically additional batched query. |
| `select_for_update()` | Used in atomic order/payment/delivery/admin paths to lock rows before state-changing decisions. Backend lock semantics differ; verify SQLite vs MySQL concurrency behavior separately. |
| `transaction.atomic` | Wraps checkout/order creation, review creation, delivery assignment transitions, payment/refund logic and selected admin changes. If an exception escapes, the transaction is rolled back. |
| `.aggregate()` / `.annotate()` | Restaurant service/dashboard calculations use `Sum`, `Count`, and `Avg`; querysets calculate revenue, commissions, order volume, top items and ratings. |
| `bulk_create()` | Order creation snapshots all cart items in one batch. `save()` methods on individual `OrderItem` objects are not called for every `bulk_create` row. |
| `update_or_create()` | `restaurant.services.record_order_earning` creates or refreshes one earning for a delivered order. |
| `get_or_create()` | Cart/profile/settings helpers lazily ensure one-to-one/profile/config rows exist. |
| `Q(...)` | Restaurant search and location filters combine OR/AND predicates. |

## Important query and write flows

### Cart-to-order transaction

`create_order_from_cart()` in `orders/services.py`:

1. Resolves an optional saved address scoped to the current user.
2. Locks the user's cart (`select_for_update`) and loads menu item + restaurant rows.
3. Rejects empty/mixed-restaurant carts, inactive/closed restaurants, unavailable menu items, invalid coordinates, excessive quantity, and below-minimum orders.
4. Resolves offer, calls `compute_order_totals()` using `Decimal`, and creates the order.
5. Adds a placed status event and bulk-creates order-item snapshots.
6. Increments offer use and deletes cart rows.

SQL concept: one transaction containing `SELECT ... FOR UPDATE`, validation `SELECT`s, several `INSERT`s, an offer `UPDATE`, and a cart-item `DELETE`.

### Payment transaction

`PaymentService.process()` locks the order and checks existing paid/COD-pending payments before creating a new record. A COD row is pending; a mock test payment is marked paid only when the configured provider is `"mock"`. A client-provided transaction ID is not treated as proof of payment.

### Delivery assignment transaction

`assign_ready_order()` locks the order and assignment, checks current state/timeout/attempt count, fetches online available partners with fresh coordinates, excludes busy/already-tried partners, calculates distance, and creates/reuses an assignment/attempt. Transition history and notifications are stored alongside state. The service can be reached from page/API polling and GPS/availability events; it is not a worker queue.

### Reporting and aggregation

Restaurant services use:

- `Sum("order_amount")`, `Sum("commission_amount")`, `Sum("restaurant_amount")`
- `Count("id")` and grouped `annotate(orders=Count(...), quantity=Sum(...))`
- `Avg("rating")` and `Avg("total_price")`

These are equivalent to SQL aggregate functions and `GROUP BY`. Dashboard revenue filters are not a bank ledger or settlement transfer.

## Raw SQL and migrations

- No application runtime raw SQL use was found in the scanned Python modules. SQL scripts exist in `database/` for database setup/sample/export workflows.
- The repository includes 97 migration files. Migrations are Django's versioned schema history; `makemigrations` compares model state against migration state, while `migrate` applies migrations to a configured database.
- `makemigrations --check --dry-run --settings=food_ex.settings.dev` currently reports a pending migration for `LocationSetting.tile_layer_url` and `tile_layer_attribution`. Do not create/apply this during documentation-only work; agree on the migration and deployment plan first.
- The actual deployed MySQL schema and applied migration records were not inspected. A local source model or SQL example is not proof of live schema.

## Error and consistency notes

- Decimal money values are rounded through `restaurant.models.quantize_money`; do not calculate authoritative totals in JavaScript.
- The order/payment/delivery paths use transactions and row locks, but lock guarantees depend on backend and database isolation configuration.
- Bulk updates and deletes can bypass model-level validation/signals.
- `CustomerAddress.is_default` is cleared via queryset update before creation; the model does not show a database uniqueness constraint enforcing only one default address per user.
- Order model history and status-event rows are both used. Verify the service's transition/event behavior when changing lifecycle code.

## Quick ORM demonstration

```python
orders = (
    Order.objects.filter(user=request.user)
    .select_related("restaurant")
    .prefetch_related("items")
)
```

This reads only the current customer's orders, joins each restaurant, and batches order items to avoid querying each relation separately. In SQL terms, it is a filtered order query plus a join and a separate prefetch query.
