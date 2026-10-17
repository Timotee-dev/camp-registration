from django import forms

from .models import ACCENTS, Event

DT = "%Y-%m-%dT%H:%M"


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format=DT, **kwargs)


class EventDetailsForm(forms.ModelForm):
    """Used when creating an event and on the Settings tab (details section)."""

    class Meta:
        model = Event
        fields = ["title", "description", "venue", "starts_at", "ends_at", "organiser_name", "contact", "accent"]
        labels = {
            "title": "Event name",
            "description": "About the event",
            "venue": "Venue / location",
            "starts_at": "Starts",
            "ends_at": "Ends",
            "organiser_name": "Organised by",
            "contact": "Enquiries contact",
            "accent": "Colour",
        }
        help_texts = {
            "description": "Shown on the first page before people start registering. Line breaks are kept.",
            "organiser_name": "Your name, church, school or organisation.",
            "contact": "A phone number or email people can reach for questions.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Youth Camp Meeting 2026", "autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Theme, what to expect, what to bring…"}),
            "venue": forms.TextInput(attrs={"placeholder": "e.g. Camp Ground, Ede, Osun State"}),
            "starts_at": DateTimeLocalInput(),
            "ends_at": DateTimeLocalInput(),
            "organiser_name": forms.TextInput(attrs={"placeholder": "e.g. RCCG Youth Fellowship"}),
            "contact": forms.TextInput(attrs={"placeholder": "e.g. 0803 000 1111"}),
            "accent": forms.RadioSelect(choices=ACCENTS),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("starts_at", "ends_at"):
            self.fields[f].input_formats = [DT, "%Y-%m-%d %H:%M", "%Y-%m-%d"]

    def clean_title(self):
        t = " ".join(self.cleaned_data["title"].split())
        if not t:
            raise forms.ValidationError("Give your event a name.")
        return t

    def clean(self):
        d = super().clean()
        s, e = d.get("starts_at"), d.get("ends_at")
        if s and e and e < s:
            self.add_error("ends_at", "The end can't be before the start.")
        return d


class EventRulesForm(forms.ModelForm):
    """Settings tab: who can register and what they see afterwards."""

    class Meta:
        model = Event
        fields = ["is_open", "close_at", "max_responses", "success_message"]
        labels = {
            "is_open": "Accepting registrations",
            "close_at": "Close automatically on",
            "max_responses": "Maximum registrations",
            "success_message": "Message after registering",
        }
        help_texts = {
            "close_at": "Optional. Registration closes at this date and time.",
            "max_responses": "Optional. Leave blank for no limit.",
            "success_message": "Optional. e.g. 'See you there! Bring a Bible and bedding.'",
        }
        widgets = {
            "close_at": DateTimeLocalInput(),
            "max_responses": forms.NumberInput(attrs={"min": 1, "placeholder": "No limit"}),
            "success_message": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["close_at"].input_formats = [DT, "%Y-%m-%d %H:%M", "%Y-%m-%d"]

    def clean_max_responses(self):
        v = self.cleaned_data.get("max_responses")
        if v is not None and v < 1:
            raise forms.ValidationError("Must be at least 1, or leave blank for no limit.")
        return v
