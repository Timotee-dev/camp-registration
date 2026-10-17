"""JSON API used by the form builder page.

GET  /api/events/<id>/questions/   -> {"questions": [...]}
PUT  /api/events/<id>/questions/   body {"questions": [...]} -> saves the whole list in order

Questions omitted from a PUT are deleted, or archived (hidden but kept in exports)
if people have already answered them.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .answers import unique_key
from .models import Event, Question, Submission, UniqueAnswer

MAX_QUESTIONS = 100
MAX_OPTIONS = 100


class QuestionIn(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    qtype = serializers.ChoiceField(choices=[t for t, _ in Question.TYPES])
    label = serializers.CharField(max_length=300, allow_blank=True, trim_whitespace=True)
    help_text = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    required = serializers.BooleanField(default=True)
    unique = serializers.BooleanField(default=False)
    options = serializers.ListField(child=serializers.CharField(max_length=200, allow_blank=True),
                                    required=False, default=list, max_length=MAX_OPTIONS)

    def validate(self, d):
        d["label"] = " ".join(d["label"].split())
        if not d["label"]:
            raise serializers.ValidationError({"label": "Every question needs a question text."})
        if d["qtype"] in Question.CHOICE_TYPES:
            opts = [" ".join(o.split()) for o in d.get("options", [])]
            opts = [o for o in opts if o]
            if not opts:
                raise serializers.ValidationError({"options": "Add at least one option."})
            lowered = [o.lower() for o in opts]
            if len(set(lowered)) != len(lowered):
                raise serializers.ValidationError({"options": "Two options have the same text."})
            d["options"] = opts
        else:
            d["options"] = []
        if d["qtype"] not in Question.UNIQUE_TYPES:
            d["unique"] = False
        return d


def sync_unique_index(q):
    """Keep the duplicate-check index in line with the question's 'unique' setting.
    Turning 'unique' on indexes answers already received, so later duplicates of them are caught."""
    UniqueAnswer.objects.filter(question=q).delete()
    if not q.unique:
        return
    key = str(q.id)
    rows = [
        UniqueAnswer(question=q, submission_id=sid, value=unique_key(q, ans[key]))
        for sid, ans in Submission.objects.filter(event_id=q.event_id).order_by("number").values_list("id", "answers")
        if ans.get(key) not in (None, "", [])
    ]
    UniqueAnswer.objects.bulk_create(rows, ignore_conflicts=True)


def answer_counts(event):
    counts = {}
    for answers in Submission.objects.filter(event=event).values_list("answers", flat=True):
        for k in answers:
            counts[k] = counts.get(k, 0) + 1
    return counts


def serialize(event):
    counts = answer_counts(event)
    return [
        {
            "id": q.id, "qtype": q.qtype, "label": q.label, "help_text": q.help_text,
            "required": q.required, "unique": q.unique, "options": q.options or [],
            "answers": counts.get(str(q.id), 0),
        }
        for q in event.questions.filter(is_archived=False)
    ]


class QuestionsView(APIView):
    def get_event(self, request, pk):
        return get_object_or_404(Event, pk=pk, owner=request.user)

    def get(self, request, pk):
        return Response({"questions": serialize(self.get_event(request, pk))})

    def put(self, request, pk):
        event = self.get_event(request, pk)
        items = request.data.get("questions") if isinstance(request.data, dict) else None
        if not isinstance(items, list):
            return Response({"detail": "Expected {'questions': [...]}."}, status=status.HTTP_400_BAD_REQUEST)
        if len(items) > MAX_QUESTIONS:
            return Response({"detail": f"A form can have at most {MAX_QUESTIONS} questions."},
                            status=status.HTTP_400_BAD_REQUEST)

        ser = QuestionIn(data=items, many=True)
        if not ser.is_valid():
            raw = ser.errors
            pairs = raw.items() if isinstance(raw, dict) else enumerate(raw)  # DRF returns a dict or a list
            errors = sorted(({"index": int(i), "errors": e} for i, e in pairs if e), key=lambda x: x["index"])
            return Response({"detail": "Some questions need fixing.", "errors": errors},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            Event.objects.select_for_update().filter(pk=event.pk).first()
            existing = {q.id: q for q in event.questions.filter(is_archived=False)}
            counts = answer_counts(event)
            kept = set()
            for order, d in enumerate(ser.validated_data):
                qid = d.pop("id", None)
                q = existing.get(qid) if qid else None
                if q is None:
                    q = Question(event=event)
                for k, v in d.items():
                    setattr(q, k, v)
                q.order = order
                q.save()
                sync_unique_index(q)
                kept.add(q.id)
            for qid, q in existing.items():
                if qid in kept:
                    continue
                if counts.get(str(qid)):
                    q.is_archived = True
                    q.unique = False
                    q.save(update_fields=["is_archived", "unique"])
                    sync_unique_index(q)
                else:
                    q.delete()
            event.save(update_fields=["updated_at"])

        return Response({"questions": serialize(event)})
