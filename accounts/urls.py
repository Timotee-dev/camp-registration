from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.account_settings, name="settings"),
]

if settings.PASSWORD_RESET_ENABLED:
    urlpatterns += [
        path("password-reset/", auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            success_url=reverse_lazy("accounts:password_reset_done")), name="password_reset"),
        path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"), name="password_reset_done"),
        path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete")), name="password_reset_confirm"),
        path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
    ]
