from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, ProfileForm, SignupForm, StyledPasswordChangeForm


def _safe_next(request, fallback="events:dashboard"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


def signup(request):
    if request.user.is_authenticated:
        return redirect("events:dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailBackend")
        messages.success(request, f"Welcome, {user.first_name.split()[0]}! Create your first event below.")
        return redirect(_safe_next(request))
    return render(request, "accounts/signup.html", {"form": form, "next": request.GET.get("next", "")})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    form = LoginForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user, backend="accounts.backends.EmailBackend")
        return redirect(_safe_next(request))
    return render(request, "accounts/login.html", {
        "form": form, "next": request.GET.get("next", ""), "reset_enabled": settings.PASSWORD_RESET_ENABLED,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def account_settings(request):
    u = request.user
    profile = ProfileForm(u, initial={"full_name": u.first_name, "email": u.email})
    pw = StyledPasswordChangeForm(u)
    if request.method == "POST":
        if request.POST.get("action") == "profile":
            profile = ProfileForm(u, request.POST)
            if profile.is_valid():
                profile.save()
                messages.success(request, "Profile updated.")
                return redirect("accounts:settings")
        elif request.POST.get("action") == "password":
            pw = StyledPasswordChangeForm(u, request.POST)
            if pw.is_valid():
                pw.save()
                update_session_auth_hash(request, pw.user)
                messages.success(request, "Password changed.")
                return redirect("accounts:settings")
    return render(request, "accounts/settings.html", {"profile": profile, "pw": pw})
