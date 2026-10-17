"""The public registration form people open from the shared link."""
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from .answers import clean_answer, raw_from_post, unique_key
from .models import Event, Submission, UniqueAnswer

HONEYPOT = "website_url"


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")


def _rate_limited(request, event):
    key = f"subrate:{event.pk}:{client_ip(request)}"
    n = cache.get(key, 0)
    if n >= settings.SUBMISSION_RATE_LIMIT:
        return True
    cache.set(key, n + 1, 600)
    return False


@never_cache
def form(request, code):
    event = get_object_or_404(Event.objects.select_related("owner"), code=code)
    questions = list(event.active_questions())
    is_owner = request.user.is_authenticated and request.user == event.owner

    if not event.accepting:
        return render(request, "events/public/closed.html", {"event": event, "is_owner": is_owner}, status=200)

    values, errors, form_error = {}, {}, ""
    if request.method == "POST":
        if request.POST.get(HONEYPOT):
            return redirect("public:thanks", code=code)  # silently drop bots

        cleaned = {}
        for q in questions:
            raw = raw_from_post(q, request.POST)
            values[q.id] = raw
            try:
                cleaned[q.id] = clean_answer(q, raw)
            except ValidationError as e:
                errors[q.id] = e.messages[0]

        # Friendly duplicate check before we try to save.
        for q in questions:
            if q.unique and q.id not in errors and cleaned.get(q.id) not in ("", [], None):
                if UniqueAnswer.objects.filter(question=q, value=unique_key(q, cleaned[q.id])).exists():
                    errors[q.id] = "This has already been used to register for this event."

        if not errors and _rate_limited(request, event):
            form_error = "Too many registrations from this device. Please wait a few minutes and try again."

        if not errors and not form_error:
            answers = {str(qid): v for qid, v in cleaned.items() if v not in ("", [], None)}
            try:
                with transaction.atomic():
                    locked = Event.objects.select_for_update().get(pk=event.pk)
                    if not locked.accepting:
                        return render(request, "events/public/closed.html", {"event": locked, "is_owner": is_owner})
                    locked.response_counter += 1
                    locked.save(update_fields=["response_counter"])
                    sub = Submission.objects.create(event=locked, number=locked.response_counter, answers=answers)
                    UniqueAnswer.objects.bulk_create([
                        UniqueAnswer(question=q, submission=sub, value=unique_key(q, cleaned[q.id]))
                        for q in questions if q.unique and answers.get(str(q.id))
                    ])
            except IntegrityError:
                # Someone registered the same unique answer a split-second earlier.
                for q in questions:
                    if q.unique and answers.get(str(q.id)) and UniqueAnswer.objects.filter(
                            question=q, value=unique_key(q, cleaned[q.id])).exists():
                        errors[q.id] = "This has already been used to register for this event."
                if not errors:
                    form_error = "Something went wrong saving your registration. Please submit again."
            else:
                done = request.session.get("submitted", {})
                done[code] = sub.number
                request.session["submitted"] = done
                return redirect("public:thanks", code=code)

    steps = [
        {"q": q, "value": values.get(q.id, [] if q.qtype == "multi_choice" else ""), "error": errors.get(q.id, "")}
        for q in questions
    ]
    return render(request, "events/public/form.html", {
        "event": event, "steps": steps, "total": len(steps), "has_errors": bool(errors or form_error),
        "form_error": form_error, "honeypot": HONEYPOT, "is_owner": is_owner,
        "minutes": max(1, round(len(steps) * 12 / 60)),
    })


@never_cache
def thanks(request, code):
    event = get_object_or_404(Event, code=code)
    number = request.session.get("submitted", {}).get(code)
    return render(request, "events/public/thanks.html", {"event": event, "number": number})
