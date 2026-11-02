# Database Setup

This project is configured to use SQLite by default for local development.

For MySQL production or team testing:

1. Create the database manually:
   mysql -u root -p
   CREATE DATABASE food_ex CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

2. Update the .env file with your MySQL credentials.

3. In the project root, run:
   python manage.py migrate

4. Optionally, import the seed SQL file:
   mysql -u root -p food_ex < database/mysql_setup.sql

The project also supports switching back to SQLite by setting:
USE_SQLITE=True
