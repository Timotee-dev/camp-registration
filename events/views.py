import io
from datetime import timedelta

import segno
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import exports
from .forms import EventDetailsForm, EventRulesForm
from .models import Event, Question, Submission

STARTER_QUESTIONS = [
    {"qtype": Question.SHORT, "label": "Full name", "required": True},
    {"qtype": Question.PHONE, "label": "Phone number", "required": True},
    {"qtype": Question.EMAIL, "label": "Email address", "required": False},
    {"qtype": Question.LONG, "label": "Home address", "required": False},
]


def home(request):
    return render(request, "events/home.html")


def owned_event(request, pk):
    return get_object_or_404(Event, pk=pk, owner=request.user)


def public_link(request, event):
    return request.build_absolute_uri(event.get_public_url())


# ====================================================================== Dashboard
@login_required
def dashboard(request):
    events = (Event.objects.filter(owner=request.user)
              .annotate(n_responses=Count("submissions")).order_by("-created_at"))
    return render(request, "events/dash/dashboard.html", {"events": events})


@login_required
def event_create(request):
    initial = {"organiser_name": request.user.first_name}
    form = EventDetailsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.owner = request.user
            event.save()
            Question.objects.bulk_create(
                [Question(event=event, order=i, **q) for i, q in enumerate(STARTER_QUESTIONS)]
            )
        messages.success(request, "Event created. We've added some common questions — edit, remove or add your own.")
        return redirect("events:build", pk=event.pk)
    return render(request, "events/dash/create.html", {"form": form})


@login_required
def build(request, pk):
    event = owned_event(request, pk)
    from .api import serialize
    return render(request, "events/dash/build.html", {
        "event": event, "tab": "build", "questions": serialize(event),
        "types": Question.TYPES,
        "builder_config": {
            "types": dict(Question.TYPES),
            "choiceTypes": sorted(Question.CHOICE_TYPES),
            "uniqueTypes": sorted(Question.UNIQUE_TYPES),
        },
    })


@login_required
def share(request, pk):
    event = owned_event(request, pk)
    link = public_link(request, event)
    qr = segno.make(link, error="m")
    svg = qr.svg_inline(scale=6, border=2, dark="#111111")
    return render(request, "events/dash/share.html", {"event": event, "tab": "share", "link": link, "qr_svg": svg})


@login_required
def qr_png(request, pk):
    event = owned_event(request, pk)
    buf = io.BytesIO()
    segno.make(public_link(request, event), error="m").save(buf, kind="png", scale=16, border=3)
    resp = HttpResponse(buf.getvalue(), content_type="image/png")
    resp["Content-Disposition"] = f'attachment; filename="qr-{event.code}.png"'
    return resp


@login_required
def event_settings(request, pk):
    event = owned_event(request, pk)
    details = EventDetailsForm(instance=event, prefix="d")
    rules = EventRulesForm(instance=event, prefix="r")
    if request.method == "POST":
        which = request.POST.get("section")
        if which == "details":
            details = EventDetailsForm(request.POST, instance=event, prefix="d")
            if details.is_valid():
                details.save()
                messages.success(request, "Event details saved.")
                return redirect("events:settings", pk=pk)
        elif which == "rules":
            rules = EventRulesForm(request.POST, instance=event, prefix="r")
            if rules.is_valid():
                rules.save()
                messages.success(request, "Registration settings saved.")
                return redirect("events:settings", pk=pk)
    return render(request, "events/dash/settings.html",
                  {"event": event, "tab": "settings", "details": details, "rules": rules})


@login_required
@require_POST
def toggle_open(request, pk):
    event = owned_event(request, pk)
    event.is_open = not event.is_open
    event.save(update_fields=["is_open", "updated_at"])
    messages.success(request, "Registration is now open." if event.is_open else "Registration is now closed.")
    return redirect(request.POST.get("next") or reverse("events:responses", args=[pk]))


@login_required
@require_POST
def duplicate(request, pk):
    src = owned_event(request, pk)
    with transaction.atomic():
        copy = Event.objects.create(
            owner=request.user, title=f"{src.title} (copy)"[:200], description=src.description, venue=src.venue,
            starts_at=src.starts_at, ends_at=src.ends_at, organiser_name=src.organiser_name, contact=src.contact,
            accent=src.accent, max_responses=src.max_responses, success_message=src.success_message,
        )
        Question.objects.bulk_create([
            Question(event=copy, order=q.order, qtype=q.qtype, label=q.label, help_text=q.help_text,
                     required=q.required, unique=q.unique, options=q.options)
            for q in src.questions.filter(is_archived=False)
        ])
    messages.success(request, "Event duplicated (without its registrations). Update the name and dates.")
    return redirect("events:settings", pk=copy.pk)


@login_required
def delete_event(request, pk):
    event = owned_event(request, pk)
    if request.method == "POST":
        if request.POST.get("confirm", "").strip().lower() != "delete":
            messages.error(request, "Type DELETE to confirm.")
            return redirect("events:delete", pk=pk)
        title = event.title
        event.delete()
        messages.success(request, f"“{title}” and all its registrations were deleted.")
        return redirect("events:dashboard")
    return render(request, "events/dash/delete.html", {"event": event, "tab": "settings"})


# ====================================================================== Responses
def _search(event, qs, q):
    q = (q or "").strip().lower()
    if not q:
        return qs, ""
    if q.lstrip("#").isdigit():
        by_number = qs.filter(number=int(q.lstrip("#")))
    else:
        by_number = qs.none()
    digits = "".join(c for c in q if c.isdigit())
    ids = [s.id for s in qs.only("id", "answers") if _matches(s.answers, q, digits)]
    return (qs.filter(id__in=ids) | by_number), q


def _matches(answers, q, digits):
    for v in answers.values():
        text = " ".join(v) if isinstance(v, list) else str(v)
        low = text.lower()
        if q in low:
            return True
        if len(digits) >= 4 and digits.lstrip("0") and digits.lstrip("0") in "".join(c for c in low if c.isdigit()):
            return True
    return False


@login_required
def responses(request, pk):
    event = owned_event(request, pk)
    cols = exports.export_columns(event)
    base = event.submissions.all()
    qs, q = _search(event, base, request.GET.get("q"))
    qs = qs.order_by("-number")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    rows = [(s, [s.answer_for(c) for c in cols]) for s in page.object_list]
    today = timezone.localdate()
    stats = {
        "total": base.count(),
        "today": base.filter(created_at__date=today).count(),
        "week": base.filter(created_at__date__gte=today - timedelta(days=6)).count(),
    }
    return render(request, "events/dash/responses.html", {
        "event": event, "tab": "responses", "cols": cols, "rows": rows, "page": page, "q": q,
        "stats": stats, "filtered": qs.count(), "link": public_link(request, event),
    })


@login_required
def response_detail(request, pk, number):
    event = owned_event(request, pk)
    s = get_object_or_404(Submission, event=event, number=number)
    items = [(c, s.answer_for(c)) for c in exports.export_columns(event)]
    prev = event.submissions.filter(number__lt=number).order_by("-number").values_list("number", flat=True).first()
    nxt = event.submissions.filter(number__gt=number).order_by("number").values_list("number", flat=True).first()
    return render(request, "events/dash/response_detail.html",
                  {"event": event, "tab": "responses", "s": s, "items": items, "prev": prev, "next": nxt})


@login_required
@require_POST
def response_delete(request, pk, number):
    event = owned_event(request, pk)
    s = get_object_or_404(Submission, event=event, number=number)
    s.delete()
    messages.success(request, f"Registration #{number} deleted.")
    return redirect("events:responses", pk=pk)


@login_required
def summary(request, pk):
    event = owned_event(request, pk)
    subs = event.submissions.all()
    cols = exports.export_columns(event)
    choice_qs = [q for q in cols if q.qtype in Question.CHOICE_TYPES | {Question.YESNO}]
    tallies = exports.summarise(event, subs, choice_qs)

    days = list(subs.values_list("created_at", flat=True))
    by_day = {}
    for dt in days:
        d = timezone.localtime(dt).date()
        by_day[d] = by_day.get(d, 0) + 1
    today = timezone.localdate()
    last14 = [(today - timedelta(days=i), by_day.get(today - timedelta(days=i), 0)) for i in range(13, -1, -1)]
    peak = max((n for _, n in last14), default=0) or 1
    trend = [(d, n, round(n * 100 / peak)) for d, n in last14]

    completion = []
    total = subs.count()
    counts = {}
    for a in subs.values_list("answers", flat=True):
        for k in a:
            counts[k] = counts.get(k, 0) + 1
    for q in cols:
        if not q.required:
            n = counts.get(str(q.id), 0)
            completion.append((q, n, round(n * 100 / total) if total else 0))

    return render(request, "events/dash/summary.html", {
        "event": event, "tab": "summary", "tallies": tallies, "trend": trend, "total": total,
        "completion": completion,
    })


@login_required
def export(request, pk, fmt):
    event = owned_event(request, pk)
    subs = event.submissions.all()
    if fmt == "xlsx":
        return exports.to_xlsx(event, subs)
    if fmt == "csv":
        return exports.to_csv(event, subs)
    raise Http404
