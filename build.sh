#!/usr/bin/env bash
# Render build command: bash build.sh
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Optional: create a site admin (for /admin/) from env vars, once.
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  DJANGO_SUPERUSER_USERNAME="$DJANGO_SUPERUSER_EMAIL" python manage.py createsuperuser --noinput \
    || echo "Admin account already exists, skipping."
fi
