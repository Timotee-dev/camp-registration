# Nexform — free event registration forms

Anyone can sign up, create an event, choose the questions they want to ask, and share one link.
People who open the link see the event details, then answer **one question per page**, review their
answers and submit. The organiser sees every registration on the site and can download them as **Excel** or CSV.

Built with Django + Django REST Framework + vanilla JavaScript. Runs free on Render + Neon.

## What it does

**Organisers**
- Free account (email + password)
- Create events: name, description, venue, start/end, organiser, contact, form colour
- Form builder: short answer, paragraph, email, phone, number, date, multiple choice, dropdown,
  checkboxes, yes/no — with required, description/hint, reorder, duplicate, delete
- "No duplicates" on phone/email/text/number answers (e.g. one registration per phone number)
- Share page: copy link, WhatsApp share, ready-made message, QR code (SVG on screen, PNG download)
- Registrations table with search, detail view (prev/next, print, delete)
- Summary: registrations per day and charts for every choice question
- Download Excel (formatted, with a Summary sheet) or CSV at any time
- Open/close registration, auto-close date, maximum registrations, custom thank-you message
- Duplicate an event (for next year), delete an event

**People registering**
- Intro page with the event details and a Start button
- One question per page, progress bar, Back/Next, Enter to continue, A/B/C keys on desktop
- Choice questions advance automatically when tapped
- Checks each answer as they go (required, email, phone, number, date)
- Review page with Edit buttons before submitting
- Answers are kept on the device if the page is refreshed or closed
- Thank-you page with their registration number
- Works without JavaScript too (all questions on one page)

**Safety**
- Every answer is re-validated on the server
- Phone numbers are normalised (`0803…`, `+234 803…`, `234803…` all count as the same number)
- Duplicate prevention is enforced by the database, so it holds even with simultaneous submissions
- Spam honeypot + per-device rate limit
- Organisers can only ever see their own events

## Run locally (Windows)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000, click **Create a free account**, and create an event.

Run the tests: `python manage.py test`

## Deploy for free (Render + Neon)

Render's own free database is deleted after 30 days, so the database lives on **Neon** (free, no expiry, no card).

### 1. Free database with Neon
1. Sign up at **neon.tech** (GitHub login works).
2. Create a project (any name, region closest to your users, e.g. Frankfurt/EU for Nigeria).
3. On the project dashboard click **Connect**, and copy the connection string.
   It looks like `postgresql://user:password@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`.

### 2. Web service on Render
1. Render dashboard → **New + → Blueprint** → pick this repo.
2. When asked, paste:
   - `DATABASE_URL` — the Neon connection string
   - `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD` — optional, creates a site admin for `/admin/`
3. Click **Apply** and wait for "Your service is live".

Manual setup instead of Blueprint (**New + → Web Service**):

| Setting | Value |
|---|---|
| Build Command | `bash build.sh` |
| Start Command | `gunicorn config.wsgi:application --workers 2 --timeout 60` |
| Env: `PYTHON_VERSION` | `3.12.7` |
| Env: `SECRET_KEY` | click Generate |
| Env: `DEBUG` | `False` |
| Env: `DATABASE_URL` | your Neon connection string |

### Free-tier behaviour
- The free Render service sleeps after 15 minutes without visitors; the first visit after that takes about a minute.
  Open the link yourself shortly before you share it.
- Neon's free plan gives 1 GB of storage — that's hundreds of thousands of registrations.

### Optional: "Forgot password" emails
Set `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`. Without them the site works
fully; the "Forgot password" link is simply hidden. (Render's free plan blocks email ports, so this needs a paid
instance or an email provider that offers an SMTP port Render allows.)

## Project layout

```
config/            settings, root urls
accounts/          sign up, log in (by email), account settings
events/
  models.py        Event, Question, Submission, UniqueAnswer
  answers.py       server-side answer validation + phone normalising
  views.py         organiser dashboard, builder page, share, registrations, summary, export
  api.py           JSON API the form builder saves to (DRF)
  public.py        the public registration form + thank-you page
  exports.py       Excel / CSV
static/js/
  stepper.js       one-question-per-page form
  builder.js       form builder
  common.js        copy buttons, toasts, clickable rows
```
