#!/bin/bash
set -e

echo "==> Creating data directory..."
mkdir -p /app/data

echo "==> Waiting for database..."
# انتظار قاعدة البيانات
sleep 5

echo "==> Running migrations..."
python manage.py migrate --noinput || echo "Migration failed, continuing..."

echo "==> Collecting static files..."
python manage.py collectstatic --noinput || true

echo "==> Setting up permissions..."
python manage.py setup_permissions || true

echo "==> Creating admin user..."
python manage.py create_admin || true

echo "==> Importing data from SQL (if available)..."
python manage.py import_from_sql || echo "No SQL data to import or already imported."

echo "==> Starting server on port ${PORT:-8000}..."
exec gunicorn hr_project.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
