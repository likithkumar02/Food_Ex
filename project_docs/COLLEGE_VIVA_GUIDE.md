# Food_Ex college viva guide

Answers below are limited to behavior present in the source. When asked about an unimplemented item, state that it is planned or external rather than claiming it works.

## One-minute introduction

“Food_Ex is a Django-based online food ordering and delivery system. It provides customer, restaurant-partner, and delivery-partner portals with administrator tools. Customers browse restaurants, manage a cart, place orders, choose COD or a development test payment, and track delivery. Restaurant owners manage menus and process orders. Delivery partners accept assignments and update delivery progress with optional browser GPS. Django renders the pages and manages the ORM/database; Django REST Framework provides JSON APIs. The current payment implementation is mock/COD rather than a live gateway, and tracking is periodic HTTP polling.”

## Five-minute explanation

1. **Architecture:** Django project `food_ex` contains settings and root URLs; nine apps divide accounts, customers, restaurants, orders, payment, delivery, notifications and location.
2. **Presentation:** Django templates render HTML; Bootstrap/CSS styles it; JavaScript performs selected API requests, polling, form feedback and map updates.
3. **Authentication:** custom `accounts.User` adds a role to Django's `AbstractUser`; password hashing and password validators use Django; session auth and Simple JWT are both configured. Middleware supports separate customer/delivery/restaurant role identities.
4. **Database:** Django models map relationships. Cart and profile use one-to-one relations; orders have item snapshots and status events; assignments preserve offer attempts. Migrations version the schema.
5. **Order flow:** the server validates cart/address/restaurant availability, computes Decimal totals, creates order and snapshots atomically, then restaurant moves order through preparation.
6. **Delivery and GPS:** assignment service selects a nearby eligible partner with fresh coordinates and an expanding radius; partner accepts and progresses through pickup/delivery. Browser sends GPS; customer page polls the protected tracking endpoint.
7. **Payment and limitations:** COD remains pending; mock provider creates a server reference for tests. A real gateway and automated settlement transfer are not established. No WebSocket/background worker was found.

## Demonstration script

Use only a disposable local database and fictional accounts.

1. Show customer homepage and restaurant list. Explain that approved/active restaurants come from ORM filters.
2. Open a restaurant and add menu items. If an existing cart belongs to another restaurant, show the conflict choice.
3. Checkout with a saved or fictional address. Explain server-side total calculation and order-item snapshot.
4. Show the payment page. Choose COD for a safe demo; explain mock payment is development-only and not a real gateway.
5. Sign in as restaurant owner and accept/prepare/mark ready. Point out status event/timestamp.
6. Sign in as delivery partner, go online with test GPS if available, accept the request, and advance status.
7. Open customer tracking and explain polling/freshness. Do not claim GPS is exact or instantaneous.
8. Show a delivered-order review path if fixture data is available. Mention admin moderation.

## Difficult/defensible answers

- **“Is it real-time?”** “It refreshes via periodic HTTP polling; the code has no WebSocket implementation. Location updates also depend on browser permission and partner connectivity.”
- **“Is payment real?”** “No. COD and a development mock provider are implemented. The mock provider does not charge money; a production gateway must be integrated and verified.”
- **“Is MySQL proven?”** “Settings support MySQL and setup SQL exists, but this audit ran tests on SQLite. I would run migration and integration tests against a disposable MySQL database before claiming production parity.”
- **“Did AI write it?”** “I used AI assistance, but I am responsible for understanding and validating the code. I can explain the request flow, models, and tests, and I have documented limitations and items requiring follow-up.”
- **“Why not claim every feature is complete?”** “A model or route name is not proof of a functioning end-to-end feature. I traced the actual route, view, model and test evidence and marked provider-dependent or unverified behavior.”

## 100 likely viva questions with short answers

### Project and architecture (1–10)

1. **What is Food_Ex?** A Django food-ordering and delivery application with role-specific portals.
2. **What problem does it address?** Connecting customers, restaurants and delivery partners through an order workflow.
3. **What are the main roles?** Customer, restaurant owner, delivery partner and admin.
4. **What is Django?** A Python web framework providing URL routing, views, templates, ORM, auth and admin.
5. **What is DRF used for?** JSON APIs, serializers, authentication, permissions and API views.
6. **Is the frontend a separate SPA?** No; it is primarily server-rendered Django templates with JavaScript enhancements.
7. **What does a Django view do?** Receives a request, runs application logic and returns a response.
8. **What does the root URL config do?** Routes page and API prefixes to the app URL modules.
9. **Why split functionality into apps?** To organize domain responsibilities and reduce coupling.
10. **Does a running database prove the model?** No; models/migrations and deployed schema must be checked separately.

### Django and authentication (11–20)

11. **What is `accounts.User`?** A custom user model extending Django `AbstractUser`.
12. **Where is the role stored?** In `User.role`.
13. **How are passwords stored?** As Django password hashes, not plaintext.
14. **What is a session?** Server-associated login state represented by a browser cookie.
15. **What is JWT?** A signed token used by DRF authentication for API requests.
16. **Why use both session and JWT?** Browser pages use sessions; API clients can use JWT.
17. **What does middleware do?** It processes requests/responses globally; role middleware resolves portal identities.
18. **How are password changes validated?** Through Django password forms/validators and serializer/view checks.
19. **What is CSRF?** Protection against forged state-changing browser requests using a user's session.
20. **Can a client choose its registration role?** Role-specific API views fix it server-side.

### Templates and frontend (21–30)

21. **What is template inheritance?** Child templates fill blocks in a shared parent layout.
22. **What is a template context?** Data a view passes to the template for rendering.
23. **What is `{% static %}`?** A Django tag that generates static asset URLs.
24. **Why use Bootstrap?** It provides responsive layout and reusable UI components.
25. **What is Fetch API used for here?** Browser JavaScript sends HTTP requests to JSON endpoints.
26. **Where are auth tokens stored by the auth script?** In `sessionStorage`.
27. **Does the project use `localStorage`?** No use was found in the scanned JavaScript.
28. **How are form messages shown?** Django messages and template error context.
29. **What is a template include?** A reusable fragment such as shared message rendering.
30. **Why are there duplicate restaurant templates?** Project-level templates may override app templates due loader search order.

### Database and ORM (31–40)

31. **What is an ORM?** A layer mapping model objects and QuerySets to database operations.
32. **What is a foreign key?** A many-to-one relationship and database reference to another row.
33. **What is one-to-one?** A relationship allowing one related row per object.
34. **Why is Cart one-to-one with User?** The model defines one cart per user.
35. **Why snapshot order item price?** To preserve the purchase price if the menu changes later.
36. **What does `select_related` do?** Joins single-valued related rows in the SQL query.
37. **What does `prefetch_related` do?** Loads collections in separate batched queries.
38. **What does `transaction.atomic` provide?** All-or-nothing behavior for grouped writes.
39. **What does `select_for_update` do?** Requests row locks during a transaction on supported DBs.
40. **What is a migration?** A versioned schema change generated/applied by Django.

### Restaurants and customers (41–50)

41. **When is a restaurant listed?** It must be approved and active.
42. **How does a restaurant owner manage a menu?** Through owner-scoped pages and APIs.
43. **What does `is_open` control?** Manual availability for ordering.
44. **Can a cart contain multiple restaurants?** No; the application rejects the conflict.
45. **What is the maximum cart quantity per item?** 20.
46. **How is a customer profile connected?** One-to-one to the user.
47. **How are saved addresses connected?** Many addresses can belong to a user.
48. **Can customers review any order?** No; only their own delivered order.
49. **Can an order be reviewed twice?** The one-to-one review relation prevents it.
50. **What happens to hidden reviews in public list?** They are filtered out.

### Orders and payment (51–60)

51. **Where are totals calculated?** In `orders.services.compute_order_totals`.
52. **Why use Decimal?** To avoid binary floating-point rounding in currency.
53. **What is an order status event?** A record of a transition, actor, reason and timestamp.
54. **What is the initial order status?** `placed`.
55. **Who accepts/prepares an order?** The owning restaurant partner.
56. **What happens when checkout succeeds?** Order and item snapshots are created, and cart items are cleared.
57. **What does COD payment status begin as?** Pending.
58. **Is the mock payment provider a real gateway?** No; it only creates a reference for development.
59. **Can the client supply proof of payment?** No; payment state is set server-side.
60. **What if card/UPI is unconfigured?** The service rejects it.

### Delivery and location (61–70)

61. **How is a delivery partner chosen?** Eligible online/available partners with fresh GPS are filtered and nearest selected.
62. **Why store assignment attempts?** To preserve accept/reject/timeout history and support retries.
63. **What is the delivery progression?** Accept → arrival → pickup → out for delivery → delivered.
64. **What happens when an offer times out?** It is recorded and reassignment is attempted by a later request.
65. **Is there a separate worker?** No background worker was found; app requests trigger dispatch refresh.
66. **How does browser GPS work?** `navigator.geolocation` requires permission and returns coordinate fixes.
67. **What library draws maps?** Leaflet via `FoodExMap`.
68. **Is customer tracking WebSocket-based?** No, it polls every few seconds.
69. **How does backend validate coordinates?** Location service checks numeric finite values and legal ranges.
70. **Can stale GPS be shown as live?** The API provides freshness data; the client distinguishes delayed fixes.

### API, security and errors (71–80)

71. **What is a serializer?** DRF component for parsing/validating input and representing output.
72. **What is `IsAuthenticated`?** Permission requiring a logged-in principal.
73. **How is object ownership enforced?** Querysets filter by current user/owner/assigned partner.
74. **What does a 401 mean?** Authentication missing or invalid.
75. **What does a 403 mean?** Authenticated but not authorized by role/ownership.
76. **What does a 404 often mean in owner-scoped views?** Object absent or not owned by requester.
77. **Why use 409 for cart/review conflicts?** The request conflicts with current resource state.
78. **What does CORS control?** Which browser origins may access cross-origin APIs.
79. **Why not allow wildcard CORS with credentials?** It weakens origin boundaries and browsers reject wildcard credentials.
80. **What security issue did the audit note in admin map JS?** Dynamic values are inserted through `innerHTML`; escape/safe DOM construction is recommended.

### Testing, deployment and project ownership (81–90)

81. **How many tests passed in this audit?** 174 Django tests passed.
82. **Did the Django check pass?** Yes, no issues were identified.
83. **Was migration check clean?** No; it proposed two `LocationSetting` tile-field changes.
84. **Was MySQL tested?** No; audit tests used SQLite.
85. **How do you run tests?** `python manage.py test`.
86. **Why use `DEBUG=False` in production?** To avoid exposing debugging internals and enable production behavior.
87. **Where should secrets be stored?** Environment/secret management, never committed.
88. **Is email delivery production-ready?** Base settings use console email backend.
89. **What must be done before deployment?** Configure strong secrets, HTTPS/security flags, database, host/CORS/CSRF, email and real providers.
90. **How do you honestly discuss AI assistance?** Explain which tools helped, then show personal understanding, tests and limitations.

### Project-specific and future work (91–100)

91. **What is the most important transaction?** Checkout/order creation, which creates the order, event, item snapshots and clears cart.
92. **What is the purpose of `PlatformSetting`?** Store shared commission, GST and delivery-fee defaults.
93. **Does `RestaurantEarning` send payouts?** No; it records calculated amounts.
94. **What does `LocationSetting` configure?** Map defaults, GPS freshness/throttle and assignment thresholds.
95. **Why is `OrderStatusEvent` useful?** It gives an audit timeline beyond the current status field.
96. **What is a limitation of polling?** More repeated requests and delayed updates compared with push.
97. **What happens when location permission is denied?** The user should use manual address entry; UI reports the denial.
98. **What is one migration issue?** Location tile defaults differ between model and migrations.
99. **What is one production improvement?** Integrate and test a real payment provider using secure server-side verification.
100. **What is the first document to study?** `PROJECT_OVERVIEW.md`, alongside `food_ex/urls.py` and `food_ex/views.py`.
