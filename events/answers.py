"""Server-side validation of answers. The public form also validates in the browser,
but this is the source of truth — nothing reaches the database without passing here."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Question

MAX_SHORT, MAX_LONG = 300, 3000


def normalise_phone(raw: str) -> str:
    """'0803 123 4567', '+234 803-123-4567', '2348031234567' -> '08031234567'. Others -> '+<digits>'/'<digits>'."""
    s = (raw or "").strip()
    plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if not 7 <= len(digits) <= 15 or re.search(r"[^\d\s+\-().]", s):
        raise ValidationError("Enter a valid phone number, e.g. 08031234567.")
    if digits.startswith("234") and len(digits) == 13:
        return "0" + digits[3:]
    if len(digits) == 10 and digits[0] in "789" and not plus:
        return "0" + digits
    return ("+" if plus else "") + digits


def unique_key(question, value) -> str:
    """Value used for duplicate detection (case/space-insensitive)."""
    return " ".join(str(value).split()).lower()[:320]


def clean_answer(q: Question, raw):
    """Return the cleaned value ('' / [] if empty and optional) or raise ValidationError."""
    if q.qtype == Question.MULTI:
        values = [v.strip() for v in (raw or []) if v and v.strip()]
        if not values:
            if q.required:
                raise ValidationError("Please choose at least one option.")
            return []
        allowed = q.choices
        bad = [v for v in values if v not in allowed]
        if bad:
            raise ValidationError("Please choose from the options given.")
        return [o for o in allowed if o in values]  # keep option order, drop duplicates

    value = (raw or "").strip() if isinstance(raw, str) else ""
    if not value:
        if q.required:
            raise ValidationError("Please choose an option." if q.is_choice or q.qtype == Question.YESNO
                                  else "This question is required.")
        return ""

    t = q.qtype
    if t == Question.SHORT:
        value = " ".join(value.split())
        if len(value) > MAX_SHORT:
            raise ValidationError(f"Please keep this under {MAX_SHORT} characters.")
    elif t == Question.LONG:
        value = value.replace("\r\n", "\n")
        if len(value) > MAX_LONG:
            raise ValidationError(f"Please keep this under {MAX_LONG} characters.")
    elif t == Question.EMAIL:
        value = value.lower()
        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError("Enter a valid email address, e.g. name@example.com.")
    elif t == Question.PHONE:
        value = normalise_phone(value)
    elif t == Question.NUMBER:
        try:
            d = Decimal(value.replace(",", ""))
        except InvalidOperation:
            raise ValidationError("Enter a number.")
        if not d.is_finite() or abs(d) > Decimal("1e15"):
            raise ValidationError("Enter a valid number.")
        value = format(d.normalize(), "f") if d == d.to_integral() else str(d)
        if value == "-0":
            value = "0"
    elif t == Question.DATE:
        try:
            value = date.fromisoformat(value).isoformat()
        except ValueError:
            raise ValidationError("Enter a valid date.")
    elif t in (Question.SINGLE, Question.DROPDOWN, Question.YESNO):
        if value not in q.choices:
            raise ValidationError("Please choose from the options given.")
    return value


def raw_from_post(q: Question, post):
    name = f"q_{q.id}"
    return post.getlist(name) if q.qtype == Question.MULTI else post.get(name, "")
