from django import forms
from django.core.exceptions import ValidationError

from .models import Attendee, normalise_ng_phone


class RegistrationForm(forms.ModelForm):
    # Honeypot: real people never see or fill this field.
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    # Allow spaces/+/dashes on input; normalised to 13 digits in clean_phone.
    phone = forms.CharField(
        label="Phone number", max_length=25,
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "08031234567"}),
    )

    class Meta:
        model = Attendee
        fields = ["first_name", "last_name", "gender", "phone", "email", "arrival_date", "special_needs"]
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "placeholder": "e.g. Tolu"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name", "placeholder": "e.g. Adeyemi"}),
            "gender": forms.RadioSelect,
            "phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "08031234567"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "Optional, for an email copy"}),
            "arrival_date": forms.DateInput(attrs={"type": "date"}),
            "special_needs": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Medical conditions, dietary needs, accessibility… (optional)"}
            ),
        }
        labels = {"phone": "Phone number", "email": "Email address", "special_needs": "Special needs"}

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields["gender"].choices = Attendee.GENDER_CHOICES
        if event:
            self.fields["arrival_date"].widget.attrs.update(
                min=event.start_date.isoformat(), max=event.end_date.isoformat()
            )
            self.fields["arrival_date"].initial = event.start_date

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Spam detected.")
        return ""

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip().title()

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip().title()

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()

    def clean_phone(self):
        phone = normalise_ng_phone(self.cleaned_data["phone"])
        if self.event and Attendee.objects.filter(event=self.event, phone=phone).exists():
            raise ValidationError(
                "This phone number is already registered for this camp. "
                "Use 'Find my registration' to see your code."
            )
        return phone

    def clean_arrival_date(self):
        d = self.cleaned_data["arrival_date"]
        ev = self.event
        if ev and not (ev.start_date <= d <= ev.end_date):
            raise ValidationError(f"Choose a date between {ev.start_date:%d %b} and {ev.end_date:%d %b %Y}.")
        return d

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.event = self.event
        if commit:
            obj.save()
        return obj


class LookupForm(forms.Form):
    phone = forms.CharField(
        label="Phone number you registered with",
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "08031234567"}),
    )

    def clean_phone(self):
        return normalise_ng_phone(self.cleaned_data["phone"])
