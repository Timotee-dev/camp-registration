from django.contrib import admin

from .models import Attendee, CampEvent


@admin.register(CampEvent)
class CampEventAdmin(admin.ModelAdmin):
    list_display = ["name", "venue", "start_date", "end_date", "registration_open", "is_active", "registered"]
    list_editable = ["registration_open"]

    @admin.display(description="Registered")
    def registered(self, obj):
        return obj.attendees.count()


@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = ["reg_code", "first_name", "last_name", "gender", "phone", "arrival_date",
                    "email_status", "sms_status", "created_at"]
    list_filter = ["event", "gender", "arrival_date", "email_status", "sms_status"]
    search_fields = ["reg_code", "first_name", "last_name", "phone", "email"]
    readonly_fields = ["reg_code", "created_at"]
