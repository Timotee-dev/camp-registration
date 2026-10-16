# Camp Meeting Registration

A Django + DRF system for registering people to attend a camp meeting.

- **Public form** (mobile-first): name, gender, phone, email (optional), arrival date, special needs
- **Registration codes** like `CM26-0001`, unique per camp
- **Confirmations** by SMS (Termii) and email, sent in the background — a failed send never blocks registration
- **Staff dashboard**: live stats, arrivals by day, 7-day trend, search/filter, resend confirmations, open/close registration
- **Export** to Excel (with a Summary sheet) or CSV — exports respect the current filters
- **"Find my registration"**: re-sends the code to the phone/email on file (never shows it on screen to strangers)
- **REST API** for a future mobile app or check-in tool
- Duplicate protection (one registration per phone per camp, in any format: `0803…`, `+234 803…`), capacity limit, honeypot spam trap

## Run locally (Windows)

```bash
cd campreg
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then edit .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

1. Go to `http://127.0.0.1:8000/admin/` → **Camp events** → add your camp (name, venue, dates, optional capacity).
2. The public form is live at `http://127.0.0.1:8000/`.
3. Staff dashboard: `http://127.0.0.1:8000/staff/`.

With `EMAIL_HOST` empty and `SMS_PROVIDER=console`, emails and SMS are printed in the terminal, so you can test without spending credits.

Run the tests: `python manage.py test registration`

## Staff accounts

Anyone who should see the dashboard needs a user with **Staff status** ticked (create them in `/admin/` → Users). Superusers can also edit camps and attendees in the admin.

## Email (Gmail)

Turn on 2-step verification on the Gmail account, create an **App password**, and set:

```
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<16-char app password>
DEFAULT_FROM_EMAIL=Camp Meeting <you@gmail.com>
```

## SMS (Termii)

1. Sign up at termii.com, fund the wallet, and register a **Sender ID** (approval takes a day or two; until then, use the `generic` channel with an approved ID).
2. Set `SMS_PROVIDER=termii`, `TERMII_API_KEY`, `TERMII_SENDER_ID`.
3. Use `TERMII_CHANNEL=dnd` if many attendees have DND activated (costs more but delivers).

Phones are stored as `234XXXXXXXXXX`, the format Termii expects.

## Deploy on Render

`render.yaml` sets up a web service plus a free Postgres database.

1. Push this folder to GitHub.
2. Render → **New → Blueprint** → pick the repo.
3. Fill in the secret env vars it asks for (Termii key, email settings).
4. After the first deploy, open the Render **Shell** and run `python manage.py createsuperuser`.

## API

| Method | URL | Access | Purpose |
|---|---|---|---|
| GET | `/api/camp/` | public | Active camp details |
| POST | `/api/register/` | public (20/hour per IP) | Register |
| GET | `/api/attendees/?q=&gender=&arrival_date=` | staff | List/search |
| GET | `/api/attendees/<id>/` | staff | One attendee |
| GET | `/api/stats/` | staff | Totals, gender, arrivals |

## Running a new camp next year

Add a new Camp event in the admin. Saving it as **active** automatically deactivates the old one; past camps stay in the database and can be viewed from the dashboard's camp selector.

## Project layout

```
config/                 settings, urls
registration/
  models.py             CampEvent, Attendee (code generation, phone normalising)
  forms.py              public form + lookup
  views.py              public pages, dashboard, resend, export
  api.py                DRF endpoints
  notifications.py      email + SMS (Termii)
  exports.py            Excel / CSV
  templates/registration/
static/css/app.css
```
