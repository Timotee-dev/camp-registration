from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Attendee, CampEvent


@override_settings(NOTIFY_SYNC=True, SMS_PROVIDER="console")
class RegistrationTests(TestCase):
    def setUp(self):
        self.ev = CampEvent.objects.create(
            name="Annual Camp Meeting 2026", venue="Camp Ground, Ede", theme="Arise and Shine",
            start_date=date(2026, 12, 20), end_date=date(2026, 12, 27), code_prefix="CM",
        )
        self.data = {
            "first_name": "tolu", "last_name": "adeyemi", "gender": "F", "phone": "0803 123 4567",
            "email": "Tolu@Example.com", "arrival_date": "2026-12-21", "special_needs": "Vegetarian",
        }

    def test_register_creates_code_and_sends_confirmations(self):
        r = self.client.post(reverse("registration:register"), self.data)
        a = Attendee.objects.get()
        self.assertRedirects(r, reverse("registration:success", args=[a.reg_code]))
        self.assertEqual(a.reg_code, "CM26-0001")
        self.assertEqual(a.phone, "2348031234567")
        self.assertEqual((a.first_name, a.email), ("Tolu", "tolu@example.com"))
        a.refresh_from_db()
        self.assertEqual((a.email_status, a.sms_status), ("sent", "sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("CM26-0001", mail.outbox[0].subject)
        page = self.client.get(r.url)
        self.assertContains(page, "CM26-0001")

    def test_codes_increment(self):
        self.client.post(reverse("registration:register"), self.data)
        self.client.post(reverse("registration:register"), {**self.data, "phone": "07011112222"})
        self.assertEqual(sorted(Attendee.objects.values_list("reg_code", flat=True)), ["CM26-0001", "CM26-0002"])

    def test_duplicate_phone_rejected_in_any_format(self):
        self.client.post(reverse("registration:register"), self.data)
        r = self.client.post(reverse("registration:register"), {**self.data, "phone": "+234 803 123 4567"})
        self.assertContains(r, "already registered")
        self.assertEqual(Attendee.objects.count(), 1)

    def test_invalid_phone_and_arrival_outside_camp(self):
        r = self.client.post(reverse("registration:register"),
                             {**self.data, "phone": "12345", "arrival_date": "2026-12-30"})
        self.assertContains(r, "valid Nigerian phone")
        self.assertContains(r, "Choose a date between")
        self.assertFalse(Attendee.objects.exists())

    def test_closed_and_full(self):
        self.ev.registration_open = False
        self.ev.save()
        self.assertContains(self.client.get(reverse("registration:register")), "Registration is closed")
        self.ev.registration_open, self.ev.capacity = True, 1
        self.ev.save()
        self.client.post(reverse("registration:register"), self.data)
        self.assertContains(self.client.get(reverse("registration:register")), "Registration is full")

    def test_success_page_private_to_registrant(self):
        self.client.post(reverse("registration:register"), self.data)
        other = self.client_class()
        r = other.get(reverse("registration:success", args=["CM26-0001"]))
        self.assertRedirects(r, reverse("registration:lookup"))

    def test_lookup_resends_without_revealing(self):
        self.client.post(reverse("registration:register"), self.data)
        mail.outbox.clear()
        r = self.client_class().post(reverse("registration:lookup"), {"phone": "08031234567"})
        self.assertContains(r, "0803****567")
        self.assertNotContains(r, "CM26-0001")
        self.assertEqual(len(mail.outbox), 1)

    def test_email_failure_is_recorded_not_raised(self):
        with mock.patch("registration.notifications.send_confirmation_email", side_effect=OSError("smtp down")):
            r = self.client.post(reverse("registration:register"), self.data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Attendee.objects.get().email_status, "failed")

    def test_no_email_status(self):
        self.client.post(reverse("registration:register"), {**self.data, "email": ""})
        self.assertEqual(Attendee.objects.get().email_status, "no_email")

    def test_honeypot(self):
        self.client.post(reverse("registration:register"), {**self.data, "website": "spam.com"})
        self.assertFalse(Attendee.objects.exists())


@override_settings(NOTIFY_SYNC=True, SMS_PROVIDER="console")
class StaffTests(TestCase):
    def setUp(self):
        self.ev = CampEvent.objects.create(name="Camp 2026", venue="Ede",
                                           start_date=date(2026, 12, 20), end_date=date(2026, 12, 27))
        for i, (g, d) in enumerate([("M", 20), ("F", 21), ("F", 21)]):
            Attendee.objects.create(event=self.ev, first_name=f"P{i}", last_name="Test", gender=g,
                                    phone=f"2348030000{i:03d}", arrival_date=date(2026, 12, d),
                                    special_needs="Diabetic" if i == 0 else "")
        self.staff = User.objects.create_user("staff", password="pw-12345!", is_staff=True)

    def test_dashboard_requires_staff(self):
        r = self.client.get(reverse("registration:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("registration:login"), r.url)

    def test_dashboard_stats_and_filters(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("registration:dashboard"))
        self.assertEqual(r.context["stats"]["total"], 3)
        self.assertEqual(r.context["stats"]["female"], 2)
        r = self.client.get(reverse("registration:dashboard"), {"gender": "F", "arrival": "2026-12-21"})
        self.assertEqual(r.context["filtered_count"], 2)
        r = self.client.get(reverse("registration:dashboard"), {"q": "08030000001"})
        self.assertEqual(r.context["filtered_count"], 1)

    def test_exports(self):
        self.client.force_login(self.staff)
        csv = self.client.get(reverse("registration:export", args=["csv"]), {"needs": "1"})
        body = csv.content.decode("utf-8-sig")
        self.assertIn("Diabetic", body)
        self.assertEqual(body.strip().count("\n"), 1)  # header + 1 row
        xlsx = self.client.get(reverse("registration:export", args=["xlsx"]))
        self.assertEqual(xlsx.status_code, 200)
        self.assertTrue(xlsx.content.startswith(b"PK"))

    def test_resend_and_toggle(self):
        self.client.force_login(self.staff)
        a = Attendee.objects.first()
        self.client.post(reverse("registration:resend", args=[a.pk]), {"channel": "sms"})
        a.refresh_from_db()
        self.assertEqual(a.sms_status, "sent")
        self.client.post(reverse("registration:toggle", args=[self.ev.pk]))
        self.ev.refresh_from_db()
        self.assertFalse(self.ev.registration_open)


@override_settings(NOTIFY_SYNC=True, SMS_PROVIDER="console")
class ApiTests(TestCase):
    def setUp(self):
        self.ev = CampEvent.objects.create(name="Camp 2026", venue="Ede",
                                           start_date=date(2026, 12, 20), end_date=date(2026, 12, 27))

    def test_public_register_and_staff_only_list(self):
        r = self.client.post("/api/register/", {"first_name": "ade", "last_name": "bello", "gender": "M",
                                                "phone": "09012345678", "arrival_date": "2026-12-20"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["reg_code"], "CM26-0001")
        self.assertEqual(self.client.get("/api/attendees/").status_code, 403)
        self.client.force_login(User.objects.create_user("s", password="x", is_staff=True))
        self.assertEqual(self.client.get("/api/attendees/").json()["count"], 1)
        self.assertEqual(self.client.get("/api/stats/").json()["total"], 1)

    def test_only_one_active_camp(self):
        CampEvent.objects.create(name="Camp 2027", venue="Ede",
                                 start_date=date(2027, 12, 20), end_date=date(2027, 12, 27))
        self.assertEqual(CampEvent.objects.filter(is_active=True).count(), 1)
        self.assertEqual(CampEvent.active().name, "Camp 2027")
