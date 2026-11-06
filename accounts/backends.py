import os

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Log in with email + password. Accounts store the lowercased email as the username too."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (kwargs.get("email") or username or "").strip().lower()
        if email == "admin":  # convenience on /admin/: "admin" = the account in DJANGO_SUPERUSER_EMAIL
            email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip().lower() or email
        if not email or not password:
            return None
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).order_by("id").first() \
            or User.objects.filter(username__iexact=email).first()
        if user is None:
            User().set_password(password)  # equalise timing for unknown emails
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
