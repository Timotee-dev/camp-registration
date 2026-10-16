import re

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


def normalise_ng_phone(raw: str) -> str:
    """Turn 0803..., 803..., +234803..., 234 803 ... into 2348031234567."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("234"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "789":
        raise ValidationError("Enter a valid Nigerian phone number, e.g. 08031234567.")
    return "234" + digits


class CampEvent(models.Model):
    """One camp meeting (e.g. 'Annual Camp Meeting 2026'). Only one should be active."""

    name = models.CharField(max_length=200)
    theme = models.CharField(max_length=255, blank=True)
    venue = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_open = models.BooleanField(default=True)
    is_active = models.BooleanField(
        default=True, help_text="The active camp is the one the public form registers people for."
    )
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for no limit.")
    code_prefix = models.CharField(
        max_length=6, default="CM", help_text="Prefix for registration codes, e.g. CM → CM26-0001."
    )
    contact_phone = models.CharField(max_length=30, blank=True)
    extra_info = models.TextField(blank=True, help_text="Shown on the form and in confirmation emails.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})

    def save(self, *args, **kwargs):
        # Keep exactly one active camp.
        if self.is_active:
            CampEvent.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).first()

    @property
    def is_full(self):
        return bool(self.capacity) and self.attendees.count() >= self.capacity

    @property
    def accepting(self):
        return self.registration_open and not self.is_full


class Attendee(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female")]

    event = models.ForeignKey(CampEvent, on_delete=models.PROTECT, related_name="attendees")
    reg_code = models.CharField(max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=15, help_text="Stored as 234XXXXXXXXXX")
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    arrival_date = models.DateField()
    special_needs = models.TextField(
        blank=True, help_text="Medical, dietary, accessibility or other needs."
    )

    email_status = models.CharField(max_length=20, default="pending")
    sms_status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "phone"], name="one_registration_per_phone"),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.reg_code})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def phone_display(self):
        return "0" + self.phone[3:] if self.phone.startswith("234") else self.phone

    def clean(self):
        if self.phone:
            self.phone = normalise_ng_phone(self.phone)
        ev = self.event if self.event_id else None
        if ev and self.arrival_date and not (ev.start_date <= self.arrival_date <= ev.end_date):
            raise ValidationError(
                {"arrival_date": f"Arrival must be between {ev.start_date:%d %b} and {ev.end_date:%d %b %Y}."}
            )

    def save(self, *args, **kwargs):
        if not self.reg_code:
            with transaction.atomic():
                self.reg_code = self._next_code()
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def _next_code(self):
        ev = self.event
        prefix = f"{ev.code_prefix.upper()}{ev.start_date:%y}-"
        last = (
            Attendee.objects.select_for_update()
            .filter(reg_code__startswith=prefix)
            .order_by("-reg_code")
            .values_list("reg_code", flat=True)
            .first()
        )
        n = int(last.split("-")[-1]) + 1 if last else 1
        return f"{prefix}{n:04d}"
