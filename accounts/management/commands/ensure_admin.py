"""Create or promote the site admin from DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD.

- No account with that email: creates one (username = email) as a superuser.
- Account already exists (e.g. you signed up normally first): makes it a superuser.
  Its password is only changed if DJANGO_SUPERUSER_RESET_PASSWORD=true.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or promote the admin account from environment variables."

    def handle(self, *args, **options):
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()
        reset = os.getenv("DJANGO_SUPERUSER_RESET_PASSWORD", "").strip().lower() in {"1", "true", "yes"}
        if not email or not password:
            self.stdout.write("ensure_admin: DJANGO_SUPERUSER_EMAIL/PASSWORD not set, skipping.")
            return
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username__iexact=email).first()
        if user is None:
            User.objects.create_superuser(username=email, email=email, password=password, first_name="Admin")
            self.stdout.write(f"ensure_admin: created admin account {email}")
            return
        user.is_staff = user.is_superuser = user.is_active = True
        if reset:
            user.set_password(password)
        user.save()
        self.stdout.write(f"ensure_admin: {email} is now an admin" + (" (password reset)" if reset else ""))
