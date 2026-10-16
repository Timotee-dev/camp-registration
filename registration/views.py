from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import exports
from .forms import LookupForm, RegistrationForm
from .models import Attendee, CampEvent
from .notifications import send_confirmations, send_confirmations_async


# ====================================================================== Public
def register(request):
    event = CampEvent.active()
    if event is None or not event.accepting:
        return render(request, "registration/closed.html", {"event": event})

    form = RegistrationForm(request.POST or None, event=event)
    if request.method == "POST" and form.is_valid():
        attendee = form.save()
        send_confirmations_async(attendee)
        request.session["last_reg"] = attendee.pk
        return redirect("registration:success", code=attendee.reg_code)
    return render(request, "registration/register.html", {"form": form, "event": event})


def success(request, code):
    attendee = get_object_or_404(Attendee.objects.select_related("event"), reg_code=code)
    # Only the person who just registered (same browser session) sees the full slip.
    if request.session.get("last_reg") != attendee.pk and not request.user.is_staff:
        return redirect("registration:lookup")
    return render(request, "registration/success.html", {"a": attendee, "ev": attendee.event})


def lookup(request):
    """Re-sends the code to the phone/email on file instead of revealing it on screen."""
    event = CampEvent.active()
    form = LookupForm(request.POST or None)
    sent_to = None
    if request.method == "POST" and form.is_valid() and event:
        phone = form.cleaned_data["phone"]
        attendee = Attendee.objects.filter(event=event, phone=phone).first()
        masked = f"0{phone[3:6]}****{phone[-3:]}"
        if attendee is None:
            form.add_error("phone", "No registration found for that number at this camp.")
        elif cache.get(f"resend:{phone}"):
            sent_to = masked
            messages.info(request, "We already re-sent your code a few minutes ago. Please check your SMS/email.")
        else:
            cache.set(f"resend:{phone}", True, 600)
            send_confirmations_async(attendee)
            sent_to = masked
    return render(request, "registration/lookup.html", {"form": form, "event": event, "sent_to": sent_to})


# ====================================================================== Dashboard
def _filtered_attendees(request, event):
    qs = Attendee.objects.filter(event=event).select_related("event")
    q = request.GET.get("q", "").strip()
    if q:
        digits = "".join(c for c in q if c.isdigit())
        cond = (
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(email__icontains=q) | Q(reg_code__icontains=q)
        )
        if len(digits) >= 4:
            cond |= Q(phone__contains=digits.lstrip("0"))
        qs = qs.filter(cond)
    if g := request.GET.get("gender"):
        qs = qs.filter(gender=g)
    if d := request.GET.get("arrival"):
        qs = qs.filter(arrival_date=d)
    if request.GET.get("needs") == "1":
        qs = qs.exclude(special_needs="")
    if s := request.GET.get("notify"):
        if s == "failed":
            qs = qs.filter(Q(email_status="failed") | Q(sms_status="failed"))
    return qs


def _selected_event(request):
    events = CampEvent.objects.all()
    ev_id = request.GET.get("event")
    event = events.filter(pk=ev_id).first() if ev_id else None
    return event or CampEvent.active() or events.first(), events


@staff_member_required(login_url="registration:login")
def dashboard(request):
    event, events = _selected_event(request)
    if event is None:
        return render(request, "registration/dashboard_empty.html")

    all_qs = Attendee.objects.filter(event=event)
    today = timezone.localdate()
    stats = {
        "total": all_qs.count(),
        "male": all_qs.filter(gender="M").count(),
        "female": all_qs.filter(gender="F").count(),
        "today": all_qs.filter(created_at__date=today).count(),
        "needs": all_qs.exclude(special_needs="").count(),
        "failed": all_qs.filter(Q(email_status="failed") | Q(sms_status="failed")).count(),
    }
    by_arrival = list(all_qs.values("arrival_date").annotate(n=Count("id")).order_by("arrival_date"))
    peak = max((r["n"] for r in by_arrival), default=1)
    for r in by_arrival:
        r["pct"] = round(r["n"] * 100 / peak)

    last7 = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        last7.append({"day": day, "n": all_qs.filter(created_at__date=day).count()})
    peak7 = max((d["n"] for d in last7), default=0) or 1
    for d in last7:
        d["pct"] = round(d["n"] * 100 / peak7)

    qs = _filtered_attendees(request, event)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "registration/dashboard.html", {
        "event": event, "events": events, "stats": stats, "by_arrival": by_arrival, "last7": last7,
        "page": page, "filtered_count": qs.count(), "querystring": params.urlencode(),
        "arrival_dates": [r["arrival_date"] for r in by_arrival],
        "capacity_pct": round(stats["total"] * 100 / event.capacity) if event.capacity else None,
    })


@staff_member_required(login_url="registration:login")
def attendee_detail(request, pk):
    a = get_object_or_404(Attendee.objects.select_related("event"), pk=pk)
    return render(request, "registration/attendee_detail.html", {"a": a, "ev": a.event})


@staff_member_required(login_url="registration:login")
@require_POST
def resend(request, pk):
    a = get_object_or_404(Attendee, pk=pk)
    channel = request.POST.get("channel", "both")
    channels = ("email", "sms") if channel == "both" else (channel,)
    result = send_confirmations(a, channels)
    pretty = ", ".join(f"{k.split('_')[0]}: {v.replace('_', ' ')}" for k, v in result.items())
    messages.success(request, f"Resent to {a.full_name} — {pretty or 'nothing to send'}.")
    return redirect(request.POST.get("next") or reverse("registration:attendee", args=[pk]))


@staff_member_required(login_url="registration:login")
@require_POST
def toggle_registration(request, pk):
    ev = get_object_or_404(CampEvent, pk=pk)
    ev.registration_open = not ev.registration_open
    ev.save(update_fields=["registration_open"])
    messages.success(request, f"Registration is now {'OPEN' if ev.registration_open else 'CLOSED'}.")
    return redirect(f"{reverse('registration:dashboard')}?event={ev.pk}")


@staff_member_required(login_url="registration:login")
def export(request, fmt):
    event, _ = _selected_event(request)
    if event is None:
        return redirect("registration:dashboard")
    qs = _filtered_attendees(request, event).order_by("reg_code")
    if fmt == "xlsx":
        return exports.to_xlsx(event, qs)
    return exports.to_csv(event, qs)
