"""REST API (Django REST Framework).

POST /api/register/                 public – register for the active camp
GET  /api/camp/                     public – details of the active camp
GET  /api/attendees/?q=&gender=     staff  – list/search attendees
GET  /api/attendees/<id>/           staff  – one attendee
GET  /api/stats/                    staff  – headline numbers
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Attendee, CampEvent, normalise_ng_phone
from .notifications import send_confirmations_async


class CampSerializer(serializers.ModelSerializer):
    accepting = serializers.BooleanField(read_only=True)

    class Meta:
        model = CampEvent
        fields = ["id", "name", "theme", "venue", "start_date", "end_date", "accepting", "contact_phone", "extra_info"]


class AttendeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    event = serializers.StringRelatedField()
    phone = serializers.CharField(max_length=25)

    class Meta:
        model = Attendee
        fields = [
            "id", "reg_code", "event", "first_name", "last_name", "full_name", "gender", "phone", "email",
            "arrival_date", "special_needs", "email_status", "sms_status", "created_at",
        ]
        read_only_fields = ["id", "reg_code", "event", "email_status", "sms_status", "created_at"]

    def validate_phone(self, value):
        try:
            phone = normalise_ng_phone(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        event = self.context.get("event")
        if event and Attendee.objects.filter(event=event, phone=phone).exists():
            raise serializers.ValidationError("This phone number is already registered for this camp.")
        return phone

    def validate_arrival_date(self, d):
        ev = self.context.get("event")
        if ev and not (ev.start_date <= d <= ev.end_date):
            raise serializers.ValidationError(f"Must be between {ev.start_date} and {ev.end_date}.")
        return d

    def validate(self, attrs):
        for f in ("first_name", "last_name"):
            if f in attrs:
                attrs[f] = attrs[f].strip().title()
        if attrs.get("email"):
            attrs["email"] = attrs["email"].strip().lower()
        return attrs


class ActiveCampView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ev = CampEvent.active()
        if not ev:
            return Response({"detail": "No active camp."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CampSerializer(ev).data)


class RegisterView(generics.CreateAPIView):
    serializer_class = AttendeeSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "event": CampEvent.active()}

    def create(self, request, *args, **kwargs):
        event = CampEvent.active()
        if not event or not event.accepting:
            return Response({"detail": "Registration is closed."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        attendee = serializer.save(event=CampEvent.active())
        send_confirmations_async(attendee)


class AttendeeListView(generics.ListAPIView):
    serializer_class = AttendeeSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        ev_id = self.request.query_params.get("event")
        event = CampEvent.objects.filter(pk=ev_id).first() if ev_id else CampEvent.active()
        qs = Attendee.objects.filter(event=event).select_related("event")
        if q := self.request.query_params.get("q"):
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q)
                           | Q(reg_code__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        if g := self.request.query_params.get("gender"):
            qs = qs.filter(gender=g)
        if d := self.request.query_params.get("arrival_date"):
            qs = qs.filter(arrival_date=d)
        return qs


class AttendeeDetailView(generics.RetrieveAPIView):
    serializer_class = AttendeeSerializer
    permission_classes = [IsAdminUser]
    queryset = Attendee.objects.select_related("event")


class StatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        ev = CampEvent.active()
        if not ev:
            return Response({"detail": "No active camp."}, status=status.HTTP_404_NOT_FOUND)
        qs = Attendee.objects.filter(event=ev)
        return Response({
            "camp": ev.name,
            "total": qs.count(),
            "capacity": ev.capacity,
            "by_gender": {r["gender"]: r["n"] for r in qs.values("gender").annotate(n=Count("id"))},
            "by_arrival_date": {str(r["arrival_date"]): r["n"]
                                for r in qs.values("arrival_date").annotate(n=Count("id")).order_by("arrival_date")},
            "with_special_needs": qs.exclude(special_needs="").count(),
        })
