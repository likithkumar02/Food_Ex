# Food_Ex Docker Guide

This guide runs the existing Django application with Docker Compose, Gunicorn,
and a separate MySQL 8.4 container. Docker's MySQL database, uploaded media,
and collected static files use named volumes so they survive container
recreation. This is a local development setup, not a production security
configuration.

## What the containers run

- `web`: Python 3.12, the existing Django apps and migrations, Gunicorn, and
  WhiteNoise for collected static assets.
- `db`: MySQL 8.4, with a health check. Compose waits for MySQL to be ready
  before starting Django.
- `mysql_data`: persistent MySQL database files.
- `media_data`: persistent Django uploads.
- `static_data`: persistent output from `collectstatic`.

The existing local `.env`, SQLite database, migrations, and media are not
replaced by these files. Docker uses its own MySQL volume. Local media is not
copied automatically: it contains a customer-profile image, so review files
and transfer only those appropriate for the Docker instance.

## Prerequisites

1. Install and start Docker Desktop for Windows, with the WSL 2 backend.
2. Open PowerShell in the folder containing `manage.py`.
3. Keep the existing `.env`. If there is no `.env`, create one from the example:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Add or edit the Docker variables in `.env`: `DJANGO_SECRET_KEY`,
   `DOCKER_DB_USER`, `DOCKER_DB_PASSWORD`, and `MYSQL_ROOT_PASSWORD`. Use a
   non-root Docker database user and private, non-placeholder passwords. The
   separate `DOCKER_DB_*` variables keep local MySQL credentials (including a
   local `root` account) from being used by the containers. Keep
   `BANK_DATA_ENCRYPTION_KEY` stable if you are moving records containing
   encrypted restaurant bank details. The current local `.env` has no separate
   bank encryption key, so existing encrypted bank fields use its `SECRET_KEY`.
   If importing that database, set `BANK_DATA_ENCRYPTION_KEY` in the Docker
   environment to the same existing secret value; never share or commit it.

The checked-in example keeps `USE_SQLITE=True` for ordinary local Django
development. Compose explicitly overrides it to use MySQL at `DB_HOST=db`.
For Windows-hosted MySQL outside Compose, use its host address (usually
`127.0.0.1`) instead of `db`.

## Start the application

```powershell
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f
```

- `build` creates the Django image and installs `requirements.txt`.
- `up -d` starts MySQL, waits for its health check, then runs migrations,
  collects static files, and starts Gunicorn in the background.
- `ps` shows container status.
- `logs -f` follows logs; press Ctrl+C to stop following them (containers keep
  running).

Open [http://localhost:8000/](http://localhost:8000/). The web container runs
the project's development settings (`DEBUG=True`) so development media routes
continue to work. Do not expose this configuration directly to the public
internet.

## Django management commands

The web container applies migrations and collects static files at startup.
These requested commands can also be run explicitly:

```powershell
docker compose -f docker/docker-compose.yml exec web python manage.py migrate
docker compose -f docker/docker-compose.yml exec web python manage.py createsuperuser
docker compose -f docker/docker-compose.yml exec web python manage.py collectstatic
```

`exec` runs a Django command inside the already-running web container. Create
an administrator once, then use `/admin/`.

## Database backup and restore

Backups contain private customer/order information and must stay outside the
repository. Create a private backup folder, for example:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\FoodExBackups"
```

### Export an existing Windows MySQL database

This project folder currently selects SQLite in its local `.env`, and MySQL
client tools were not available during the project audit. If your separate
Windows MySQL server contains the `food_ex` database, install/use its MySQL
client tools and first verify the host and account in your local configuration.
Create a unique backup filename; `mysqldump` prompts for the password rather
than putting it in the command:

```powershell
$backup = Join-Path "$env:USERPROFILE\FoodExBackups" ("food_ex_{0}.sql" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
mysqldump --host=127.0.0.1 --user=<mysql-user> --password --single-transaction --routines --triggers --events --default-character-set=utf8mb4 --result-file="$backup" food_ex
```

Replace `<mysql-user>` with your local MySQL username. If your server uses a
different host or port, supply the correct `--host` and `--port`. Keep the
resulting `$backup` path so you can select the file to import.

### Import into a new Docker database

Import only into a new, empty Docker database. Do not import over a Docker
database that already contains data. First start only MySQL, so Django has not
created tables in the target:

```powershell
$backup = Read-Host "Enter the full path to the verified food_ex backup file"
docker compose -f docker/docker-compose.yml up -d db
docker compose -f docker/docker-compose.yml cp "$backup" db:/tmp/food_ex.sql
docker compose -f docker/docker-compose.yml exec db sh -c 'mysql --user="$MYSQL_USER" --password="$MYSQL_PASSWORD" "$MYSQL_DATABASE" < /tmp/food_ex.sql'
docker compose -f docker/docker-compose.yml up -d
```

The final `up -d` starts Django after the import; its migrations run on
startup. The original Windows MySQL database is not modified.

### Back up and restore Docker MySQL

Create a backup from the running container and copy it out to the private
backup folder:

```powershell
$backup = Join-Path "$env:USERPROFILE\FoodExBackups" ("food_ex_docker_{0}.sql" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
docker compose -f docker/docker-compose.yml exec db sh -c 'mysqldump --user="$MYSQL_USER" --password="$MYSQL_PASSWORD" --single-transaction "$MYSQL_DATABASE" > /tmp/food_ex_backup.sql'
docker compose -f docker/docker-compose.yml cp db:/tmp/food_ex_backup.sql "$backup"
```

Restore only into a new, empty database/container after taking a separate
backup of any data you need to preserve. The import replaces table contents
with the dump's contents; it is not a merge operation. Use a separate Compose
project name to give the restored database its own new named volume, leaving
the normal `mysql_data` volume untouched:

```powershell
$backup = Read-Host "Enter the full path to the verified Docker database backup"
docker compose -f docker/docker-compose.yml -p food-ex-restore up -d db
docker compose -f docker/docker-compose.yml -p food-ex-restore cp "$backup" db:/tmp/food_ex.sql
docker compose -f docker/docker-compose.yml -p food-ex-restore exec db sh -c 'mysql --user="$MYSQL_USER" --password="$MYSQL_PASSWORD" "$MYSQL_DATABASE" < /tmp/food_ex.sql'
docker compose -f docker/docker-compose.yml -p food-ex-restore down
```

`down` preserves the restore project's volume. To start that restored instance
later, use the same `-p food-ex-restore` option; set `WEB_PORT` to a free port
if the regular app is already using 8000. Do not run imports against a database
whose existing records must be retained.

Never delete `mysql_data` to troubleshoot or reset the database. Do not use
`docker compose -f docker/docker-compose.yml down -v`; removing named volumes
permanently deletes the database and uploaded media.

## Uploaded media and static files

Django uploads are stored in the `media_data` named volume. Collected CSS,
JavaScript, and other Django static assets are stored in `static_data` and
served by WhiteNoise. Bootstrap or map assets loaded from external URLs still
require network access from the browser.

Uploads already present in the Windows `media` folder are deliberately excluded
from the build context. To transfer an individual reviewed, public restaurant
or menu image, first create its destination directory in the running container,
then copy only that file:

```powershell
docker compose -f docker/docker-compose.yml exec web mkdir -p /app/media/restaurants
docker compose -f docker/docker-compose.yml cp .\media\restaurants\<reviewed-image> web:/app/media/restaurants/<reviewed-image>
```

Do not copy `media/customer_profiles` or other private/customer uploads into a
publicly accessible media route. Keep a separate backup of important media;
database backups do not include uploaded files.

## Stop and inspect

```powershell
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f web
docker compose -f docker/docker-compose.yml logs -f db
docker compose -f docker/docker-compose.yml down
```

`down` stops and removes the containers but leaves named data volumes intact.
Do not add `-v` unless you intentionally want to permanently erase the Docker
database and uploaded media.

## Feature verification

Docker was not installed in the audit environment, so no Docker startup,
MySQL integration, or browser workflow is claimed as tested. After Docker
Desktop is installed and the containers are running, verify the site and API
manually, including customer registration/login/profile/browsing/cart/checkout/
orders; restaurant registration/profile/menu/order/earnings; delivery
registration/online status/assignment/pickup/status/GPS; Django admin; and
payment, review, static, media, and map behavior.

The project has automated Django tests; run them against the active Docker
database with:

```powershell
docker compose -f docker/docker-compose.yml exec web python manage.py test
```

GPS requires browser permission and a supported secure browser context (or
localhost). Map tiles and optional routing use external services and depend on
network/service availability.

## Troubleshooting

- Check `docker compose -f docker/docker-compose.yml ps` and
  `docker compose -f docker/docker-compose.yml logs -f db` if MySQL is not
  healthy. The web service waits for the database health check.
- Check `docker compose -f docker/docker-compose.yml logs -f web` for Django startup or migration errors.
- Confirm `.env` has non-placeholder credentials and that its DB name/user/
  password agree with the Compose settings.
- If changing MySQL initialization credentials after `mysql_data` already
  exists, MySQL does not recreate users or reset passwords automatically.
  Update credentials inside MySQL deliberately; do not delete the volume.
- Confirm port 8000 is not already in use, or set `WEB_PORT` in `.env` to a
  different host port.
