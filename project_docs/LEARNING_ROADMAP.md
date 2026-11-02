# Beginner learning roadmap

The sequence builds from request handling and templates toward database workflows and GPS. Use fictional data only. At the end of each session, explain the flow aloud without reading the answer.

| Session | Files to open | Concepts and functions | Small output to test | Explain before moving on |
|---|---|---|---|---|
| 1. Project map | `README.md`, `manage.py`, `food_ex/settings/base.py` | Django project/app, settings, installed apps, middleware, URL config, database backend. | Run `python manage.py check`. | What is a project vs an app? How does settings select SQLite/MySQL? |
| 2. First request | `food_ex/urls.py`, `food_ex/views.py`, `food_ex/templates/home.html` | URL pattern, view, model query, context, template rendering. | Open `/` and inspect a location query parameter. | Trace browser → URL → view → template. |
| 3. HTML inheritance | `food_ex/templates/base.html`, `food_ex/templates/portals/customer_base.html`, `templates/includes/messages.html` | Blocks, inheritance, includes, static files, CSRF form token, Bootstrap. | Find the parent/base and one included message region. | Why do child templates override blocks? |
| 4. Authentication | `accounts/models.py`, `accounts/forms.py`, `accounts/serializers.py`, `accounts/views.py` | Custom user, password hashing, validators, form vs serializer, role. | Run account registration tests. | How does the app prevent client role escalation? |
| 5. Sessions and permissions | `accounts/middleware.py`, `accounts/session_utils.py`, `accounts/decorators.py`, `accounts/api_views.py` | Django session, JWT, DRF authentication, CSRF, role ownership. | Run role-specific tests; inspect API login result shape (never copy tokens). | Why are there two authentication mechanisms? |
| 6. Restaurant/menu | `restaurant/models.py`, `restaurant/forms.py`, `restaurant/serializers.py`, `restaurant/views.py` | Foreign keys, validation, approved/active state, image upload. | Inspect menu list and management pages. | Why is a new restaurant not immediately orderable? |
| 7. ORM fundamentals | `customer/models.py`, `restaurant/models.py`, `orders/models.py` | `filter`, `get_or_create`, `select_related`, `prefetch_related`, FK and one-to-one. | Use Django shell only against a disposable local DB. | Give one SQL equivalent for a queryset. |
| 8. Cart and totals | `orders/api_views.py`, `orders/views.py`, `orders/services.py` | Constraints, Decimal money, validation, transaction, row lock, snapshot. | Run order/cart tests. | Why must totals be computed by server? |
| 9. Order state | `orders/services.py`, `orders/models.py`, `orders/tests.py` | Legal transitions, status timestamps, `OrderStatusEvent`, cancellation/refund hooks. | Draw allowed state transitions from code. | What prevents skipping a state? |
| 10. Payment | `payments/models.py`, `payments/services.py`, `payments/api_views.py` | COD pending vs mock paid, idempotency, server-generated references, transaction. | Run payment tests with mock setting; never use real payment data. | What is not implemented about real card payments? |
| 11. Delivery | `delivery/models.py`, `delivery/services.py`, `delivery/api_views.py`, `delivery/tests.py` | Assignment attempts, stale location, distance, timeout, partner ownership. | Run delivery tests; trace one assignment/rejection/retry. | Why keep attempt history? |
| 12. Location UI | `location/static/location/js/location.js`, `location/static/location/js/restaurant-location.js`, `location/api_views.py` | Browser permission, JS callbacks, Leaflet, CSRF, coordinate validation. | Use browser only with location permission; verify manual fallback. | Which layer decides if a coordinate is valid? |
| 13. Customer tracking | `orders/static/orders/js/order-live-tracking.js`, `location/api_views.py`, `orders/templates/orders/detail.html` | Polling, freshness, phases, tracking ownership, route/ETA. | Observe polling in browser network tools with test account. | Why is polling not the same as WebSocket? |
| 14. Tests and migration | `*/tests.py`, `location/migrations/`, `location/models.py` | TestCase, fixtures, migrations, migration drift. | Run full tests and dry-run migration check. | What did the migration check find and why is it not applied automatically? |
| 15. Viva rehearsal | All docs, then source code | Architecture, feature workflow, limitations, AI-assisted development honesty. | Demonstrate a fictional customer order and explain each backend step. | Can you answer without inventing features? |

## Study method for each source function

For a function, write down:

1. Which route or caller invokes it?
2. What inputs can the browser/user control?
3. What validation/authorization happens before a write?
4. Which model rows are read or changed?
5. What does it return or redirect to?
6. Which failure path is most important?

Start with `orders.services.create_order_from_cart`, then `orders.services.transition_restaurant_order`, `payments.services.PaymentService.process`, `delivery.services.assign_ready_order`, and `location.api_views.OrderDeliveryLocationAPIView.get`.
