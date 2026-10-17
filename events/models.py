import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o/1/l/i to avoid mix-ups


def new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


ACCENTS = [
    ("#1f4e3d", "Forest"),
    ("#2b4acb", "Royal blue"),
    ("#7c2d92", "Purple"),
    ("#b4232c", "Crimson"),
    ("#c2570c", "Orange"),
    ("#0f766e", "Teal"),
    ("#334155", "Slate"),
    ("#9d174d", "Wine"),
]


class Event(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    code = models.CharField(max_length=12, unique=True, default=new_code, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text="What the program is about. Shown before people start.")
    venue = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    organiser_name = models.CharField(max_length=150, blank=True)
    contact = models.CharField(max_length=150, blank=True, help_text="Phone or email for enquiries.")
    accent = models.CharField(max_length=7, choices=ACCENTS, default=ACCENTS[0][0])

    is_open = models.BooleanField(default=True)
    close_at = models.DateTimeField(null=True, blank=True)
    max_responses = models.PositiveIntegerField(null=True, blank=True)
    success_message = models.TextField(blank=True)

    response_counter = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_public_url(self):
        return reverse("public:form", args=[self.code])

    def active_questions(self):
        return self.questions.filter(is_archived=False)

    @property
    def response_count(self):
        if hasattr(self, "n_responses"):
            return self.n_responses
        return self.submissions.count()

    @property
    def status(self):
        """open | closed | full | ended | empty"""
        if not self.is_open:
            return "closed"
        if self.close_at and timezone.now() >= self.close_at:
            return "ended"
        if self.max_responses and self.response_count >= self.max_responses:
            return "full"
        if not self.active_questions().exists():
            return "empty"
        return "open"

    @property
    def accepting(self):
        return self.status == "open"


class Question(models.Model):
    SHORT, LONG, EMAIL, PHONE, NUMBER, DATE = "short_text", "long_text", "email", "phone", "number", "date"
    SINGLE, DROPDOWN, MULTI, YESNO = "single_choice", "dropdown", "multi_choice", "yes_no"
    TYPES = [
        (SHORT, "Short answer"),
        (LONG, "Paragraph"),
        (EMAIL, "Email"),
        (PHONE, "Phone number"),
        (NUMBER, "Number"),
        (DATE, "Date"),
        (SINGLE, "Multiple choice (pick one)"),
        (DROPDOWN, "Dropdown"),
        (MULTI, "Checkboxes (pick many)"),
        (YESNO, "Yes / No"),
    ]
    CHOICE_TYPES = {SINGLE, DROPDOWN, MULTI}
    UNIQUE_TYPES = {SHORT, EMAIL, PHONE, NUMBER}

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField(default=0)
    qtype = models.CharField(max_length=20, choices=TYPES, default=SHORT)
    label = models.CharField(max_length=300)
    help_text = models.CharField(max_length=300, blank=True)
    required = models.BooleanField(default=True)
    unique = models.BooleanField(default=False, help_text="Reject a registration if this answer was already used.")
    options = models.JSONField(default=list, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label

    @property
    def is_choice(self):
        return self.qtype in self.CHOICE_TYPES

    @property
    def choices(self):
        return ["Yes", "No"] if self.qtype == self.YESNO else list(self.options or [])


class Submission(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="submissions")
    number = models.PositiveIntegerField()
    answers = models.JSONField(default=dict)  # {"<question id>": "value" | ["a", "b"]}; empty answers omitted
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["event", "number"], name="unique_submission_number")]

    def __str__(self):
        return f"{self.event} #{self.number}"

    def answer_for(self, question):
        v = self.answers.get(str(question.id), "")
        return ", ".join(v) if isinstance(v, list) else v


class UniqueAnswer(models.Model):
    """Enforces 'no duplicate answers' at the database level, race-safe."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="unique_answers")
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="unique_answers")
    value = models.CharField(max_length=320)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["question", "value"], name="unique_answer_per_question")]
