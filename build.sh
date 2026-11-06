#!/usr/bin/env bash
# Render build command: bash build.sh
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Optional: create (or promote) the site admin from DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD.
python manage.py ensure_admin
