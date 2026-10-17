#!/usr/bin/env bash
# Render build command: bash build.sh
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create the admin account from env vars (DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD) if set.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --noinput || echo "Superuser already exists, skipping."
fi
