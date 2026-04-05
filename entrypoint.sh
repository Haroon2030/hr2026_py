#!/bin/bash
set -e

echo "==> Creating data directory..."
mkdir -p /app/data

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Setting up permissions..."
python manage.py setup_permissions || true

echo "==> Starting server..."
exec gunicorn hr_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
