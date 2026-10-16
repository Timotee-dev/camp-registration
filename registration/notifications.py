"""Email + SMS confirmations. Failures are logged and recorded, never raised to the registrant."""
import logging
import threading

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

log = logging.getLogger("registration")


# ------------------------------------------------------------------ SMS
def send_sms(phone: str, message: str) -> bool:
    provider = settings.SMS_PROVIDER
    if provider == "termii":
        if not settings.TERMII_API_KEY:
            log.warning("SMS_PROVIDER=termii but TERMII_API_KEY is empty; SMS skipped.")
            return False
        resp = requests.post(
            f"{settings.TERMII_BASE_URL}/api/sms/send",
            json={
                "api_key": settings.TERMII_API_KEY,
                "to": phone,
                "from": settings.TERMII_SENDER_ID,
                "sms": message,
                "type": "plain",
                "channel": settings.TERMII_CHANNEL,
            },
            timeout=15,
        )
        if resp.ok:
            return True
        log.error("Termii SMS failed (%s): %s", resp.status_code, resp.text[:300])
        return False

    # console provider (development)
    log.info("[SMS to %s] %s", phone, message)
    return True


def sms_text(attendee) -> str:
    ev = attendee.event
    text = (
        f"Hi {attendee.first_name}, you're registered for {ev.name} "
        f"({ev.start_date:%d %b}-{ev.end_date:%d %b}) at {ev.venue}. "
        f"Your code: {attendee.reg_code}. Arrival: {attendee.arrival_date:%d %b}."
    )
    if ev.contact_phone:
        text += f" Enquiries: {ev.contact_phone}"
    return text


# ------------------------------------------------------------------ Email
def send_confirmation_email(attendee) -> bool:
    if not attendee.email:
        return False
    ctx = {"a": attendee, "ev": attendee.event, "site_name": settings.SITE_NAME,
           "organiser": settings.ORGANISER_NAME}
    subject = f"Registration confirmed – {attendee.event.name} ({attendee.reg_code})"
    msg = EmailMultiAlternatives(
        subject,
        render_to_string("registration/email/confirmation.txt", ctx),
        settings.DEFAULT_FROM_EMAIL,
        [attendee.email],
    )
    msg.attach_alternative(render_to_string("registration/email/confirmation.html", ctx), "text/html")
    msg.send()
    return True


# ------------------------------------------------------------------ Orchestration
def send_confirmations(attendee, channels=("email", "sms")):
    """Send the chosen confirmations and save a status on the attendee."""
    from .models import Attendee

    updates = {}
    if "email" in channels:
        if not attendee.email:
            updates["email_status"] = "no_email"
        else:
            try:
                updates["email_status"] = "sent" if send_confirmation_email(attendee) else "failed"
            except Exception:  # noqa: BLE001 – SMTP errors vary widely
                log.exception("Email to %s failed", attendee.email)
                updates["email_status"] = "failed"
    if "sms" in channels:
        try:
            updates["sms_status"] = "sent" if send_sms(attendee.phone, sms_text(attendee)) else "failed"
        except Exception:  # noqa: BLE001
            log.exception("SMS to %s failed", attendee.phone)
            updates["sms_status"] = "failed"
    if updates:
        Attendee.objects.filter(pk=attendee.pk).update(**updates)
        for k, v in updates.items():
            setattr(attendee, k, v)
    return updates


def send_confirmations_async(attendee):
    """Don't make the registrant wait on SMTP/SMS gateways."""
    if getattr(settings, "NOTIFY_SYNC", False):
        return send_confirmations(attendee)
    threading.Thread(target=send_confirmations, args=(attendee,), daemon=True).start()
