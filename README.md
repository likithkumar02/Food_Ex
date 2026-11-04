# Food_Ex

Food_Ex is a Django food-ordering application with three role-specific web portals and one shared Django REST API/database. The portals use server-rendered HTML, Bootstrap, and JavaScript; APIs use JWT bearer authentication. Local development defaults to SQLite. MySQL can be enabled through environment variables.

## Run on Windows

From the folder containing `manage.py`:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

To run the application with Docker and MySQL, follow
[docker/DOCKER_GUIDE.md](docker/DOCKER_GUIDE.md).

The project now keeps environment-specific Django settings under `food_ex/settings/`:
- `food_ex.settings.dev` for local development
- `food_ex.settings.prod` for production overrides

If you need a production run, set `DJANGO_SETTINGS_MODULE=food_ex.settings.prod` before starting the server.

Static assets are stored in namespaced `static/<app_name>/` folders in the app that owns them. The shared shell and dashboard styles are in `food_ex`, account behavior and styles are in `accounts`, and each domain app has its own stylesheet and any app-specific scripts. Django combines these assets through its staticfiles app finder; run `python manage.py collectstatic` when preparing production assets.

Open these local interfaces:

- Customer storefront: `http://127.0.0.1:8000/`
- Customer account: `/customer/login/` and `/customer/register/`
- Restaurant partner: `/restaurant/`
- Restaurant account: `/restaurant/login/` and `/restaurant/register/`
- Delivery partner: `/delivery/`
- Delivery account: `/delivery/login/` and `/delivery/register/`
- Django Admin: `/admin/`

Forgot-password requests use Django's single-use reset tokens. During development, email is printed to the runserver console because the configured backend is the console email backend. Authenticated users can also change their password from Account Settings.

The root homepage is customer-facing; its navigation links lead to restaurant and delivery portals. Portal registration sets the role on the server and creates the corresponding restaurant or delivery profile.

## Database

SQLite is the default and requires no database service. To use MySQL:

1. Install MySQL Server and create the database/user:

```sql
CREATE DATABASE food_ex CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'food_ex_user'@'localhost' IDENTIFIED BY 'use-a-private-password';
GRANT ALL PRIVILEGES ON food_ex.* TO 'food_ex_user'@'localhost';
```

2. In `.env`, set `USE_SQLITE=False` and configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`.
3. Run `python manage.py migrate`.

Never commit `.env`. Set a unique `SECRET_KEY`, `DEBUG=False`, production `ALLOWED_HOSTS`, and HTTPS `CSRF_TRUSTED_ORIGINS` before deployment.

## Deploy to PythonAnywhere

The project requires Django 5.x. PythonAnywhere's newer system image lists Python 3.13; use that version if it is available for your account, or select another version supported by your account and Django 5.2. Check the Python version options shown on your account before creating the web app.

1. Create a **manual configuration** web app on PythonAnywhere. In a Bash console, clone the GitHub repository and install its dependencies (replace `<github-user>` with the repository owner):

   ```bash
   git clone https://github.com/<github-user>/Food_Ex.git ~/Food_Ex
   cd ~/Food_Ex
   mkvirtualenv --python=/usr/bin/python3.13 food-ex-venv
   pip install -r requirements.txt
   ```

   Use the same Python version for the web app and virtual environment, and select `food-ex-venv` in the Web tab.

2. Create a private `.env` in the project root using `.env.example` as a guide. Set `SECRET_KEY` to a new, private value; set `DEBUG=False`, `ALLOWED_HOSTS` to your actual domain, and `CSRF_TRUSTED_ORIGINS` to its HTTPS origin. Never commit this file.

   The local `.env` currently selects SQLite, even though it also contains MySQL connection settings. To use MySQL on PythonAnywhere, first confirm that your account has a MySQL database available, then use the exact database name, username, password, and host shown in its database settings and set `USE_SQLITE=False`. Do not assume the local database name `food_ex` is the hosted database name. PythonAnywhere account database availability and credentials are account-specific; this project cannot inspect your account. `migrate` creates the schema but does not transfer existing data.

   Preserve the encryption key for any existing encrypted restaurant bank details. If those values were encrypted before `BANK_DATA_ENCRYPTION_KEY` was set, the current code used `SECRET_KEY` as the encryption key; keep that original value available as `BANK_DATA_ENCRYPTION_KEY` when migrating the data. Changing that key without re-encrypting the stored values makes them unreadable.

3. In the PythonAnywhere Web tab, edit the **web app's WSGI configuration file** (not just this repository's `food_ex/wsgi.py`) to point to the cloned project:

   ```python
   import os
   import sys

   project_home = "/home/<your-username>/Food_Ex"
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "food_ex.settings.prod")

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

   The project settings load `.env` from the project root. Confirm it exists and is readable by your account before reloading the web app.

4. In a Bash console, run migrations, create an administrator, and collect static files:

   ```bash
   cd ~/Food_Ex
   python manage.py check
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py collectstatic
   ```

   In the Web tab, set the virtualenv path, then map `/static/` to `/home/<your-username>/Food_Ex/staticfiles`.

5. Uploaded media is not stored in Git. The local `media/` folder contains a customer-profile image, so do not upload or publicly map that folder as-is. Transfer only reviewed public menu and restaurant images separately, and configure `/media/` only for content intended to be public. Keep customer/private uploads out of public static-file mappings.

6. Reload the web app and inspect its error log. Confirm HTTPS, allowed hosts, CSRF origins, database connectivity, static assets, and media access are configured correctly.

See the [PythonAnywhere Django deployment guide](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/), [supported Python versions](https://help.pythonanywhere.com/pages/PythonVersions/), and [static files guide](https://help.pythonanywhere.com/pages/DjangoStaticFiles/). MySQL service availability and its connection details must be confirmed in your own account.

## Payment and delivery behavior

Set `PAYMENT_PROVIDER=mock` only for development. The mock provider creates its own transaction reference on the server. Cash on delivery creates a pending payment. Card/UPI gateway payments are rejected until a real provider is configured; a client-supplied transaction ID is never treated as proof of payment.

Restaurant owners can accept a paid or COD order, move it through preparation, then mark it ready. Dispatch offers each ready order to one online, available delivery partner with a fresh GPS location, choosing the nearest eligible partner within the configured search radius. A partner has 90 seconds by default to accept or reject; expired and rejected offers remain in the assignment-attempt history and are reassigned without losing that history. The search radius expands per offer up to its configured maximum. After five unsuccessful offers, the order is marked as needing assignment attention and an administrator can retry it from Django Admin.

From Restaurant Orders, an owner can also manually choose an online, available delivery partner for an order that is ready, searching, or needs assignment attention. This sends that partner a request; the assignment is not confirmed until the partner accepts it from the delivery dashboard. The partner then marks arrival at the restaurant, picks up the order, and advances it through delivery.

Assignment timeouts are processed when customer tracking or the delivery request feed is polled; partner location updates and coming online also trigger dispatch. This project does not require a separate background worker, but assignment progress depends on those app requests continuing. Configure the timeout, offer limit, and search radii in the Location Setting record in Django Admin. Delivery progression is enforced as partner acceptance → arrival at pickup → restaurant-ready handoff → pickup → out for delivery → delivered. Restaurants can cancel before pickup; cancellation releases the partner and closes the assignment. Customer tracking shows status timestamps and only exposes live partner GPS during an active delivery. ETA is omitted when valid coordinates are unavailable.

## API

Send JWTs as `Authorization: Bearer <access-token>`. Session authentication is also enabled for same-origin browser requests.

Authentication:

- `POST /api/auth/customer/register/`, `/api/auth/customer/login/`
- `POST /api/auth/restaurant/register/`, `/api/auth/restaurant/login/`
- `POST /api/auth/delivery/register/`, `/api/auth/delivery/login/`
- `POST /api/auth/token/refresh/`, `/api/auth/logout/`, `/api/auth/forgot-password/`
- `POST /api/auth/password/change/` (authenticated; requires old, new, and confirmation passwords)
- `GET/PUT /api/auth/profile/`

Catalog and menus:

- `GET /api/restaurants/?q=<search>`
- `GET /api/restaurants/<id>/` and `/api/restaurants/<id>/menu/`
- `GET/POST /api/restaurants/manage/menu/`
- `PUT/PATCH/DELETE /api/restaurants/manage/menu/<item-id>/`

Customer orders and payments:

- `GET/POST /api/cart/` (POST body: `menu_item_id`, optional `quantity`)
- `PATCH/DELETE /api/cart/items/<cart-item-id>/`
- `GET/POST /api/orders/` (POST creates an order from the authenticated user's cart)
- `GET /api/orders/<id>/`, `/api/orders/<id>/status/`
- `POST /api/payments/orders/<id>/pay/` (body: `payment_method` set to `test` or `cod`)
- `GET /api/customer/restaurants/<id>/reviews/`; POST to `/reviews/create/`

Restaurant orders:

- `GET /api/restaurant/dashboard/` or `/api/restaurant/orders/`
- `POST /api/restaurant/orders/<id>/accept/`, `/reject/`, `/preparing/`, or `/ready/`

Delivery:

- `GET /api/delivery/dashboard/`, `/requests/`, `/history/`
- `POST /api/delivery/online/`, `/offline/`
- `POST /api/delivery/requests/<assignment-id>/accept/` or `/reject/`
- `POST /api/delivery/<assignment-id>/pickup/`, `/out-for-delivery/`, or `/complete/`
- `POST /api/delivery/location/` with `assignment_id`, `latitude`, and `longitude`
- `GET /api/notifications/`; `PATCH /api/notifications/<id>/read/`

For separate frontend origins, set `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and `ALLOWED_HOSTS` to explicit comma-separated values. CORS is not required for the local same-origin portals. Do not use a wildcard origin with credentials.

## Verification

```powershell
python manage.py check
python manage.py migrate
python manage.py test
```
