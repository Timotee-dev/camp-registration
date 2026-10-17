from django.contrib import admin

from .models import Event, Question, Submission


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ["order", "qtype", "label", "required", "unique", "is_archived"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "code", "is_open", "response_counter", "created_at"]
    search_fields = ["title", "code", "owner__email"]
    readonly_fields = ["code", "response_counter"]
    inlines = [QuestionInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["event", "number", "created_at"]
    list_filter = ["event"]
    readonly_fields = ["event", "number", "answers", "created_at"]
