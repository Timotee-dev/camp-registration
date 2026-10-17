from django.db import connection
from django.http import HttpResponse


def _db_status():
    """Short, non-secret description of database health (no hostnames or passwords)."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        from django.db.migrations.executor import MigrationExecutor
        pending = MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
        tables = set(connection.introspection.table_names())
        missing = [t for t in ("events_event", "events_question", "events_submission", "auth_user", "django_session")
                   if t not in tables]
        vendor = connection.vendor
        if missing or pending:
            return f"db: CONNECTED ({vendor}) but NOT MIGRATED. missing tables: {', '.join(missing) or '-'}; " \
                   f"pending migrations: {len(pending)}"
        from django.contrib.auth import get_user_model
        from django.conf import settings as dj_settings
        with connection.cursor() as c:
            c.execute("SELECT DISTINCT app FROM django_migrations")
            recorded = {r[0] for r in c.fetchall()}
        ours = {a.rsplit(".", 1)[-1] for a in dj_settings.INSTALLED_APPS} | {"auth", "contenttypes", "sessions", "admin"}
        foreign = sorted(recorded - ours)
        users = get_user_model().objects.count()
        from events.models import Event
        line = f"db: ok ({vendor}); users: {users}; events: {Event.objects.count()}"
        if foreign:
            line += f"; WARNING shared with another project (apps: {', '.join(foreign)})"
        return line
    except Exception as e:  # noqa: BLE001
        import re
        from django.conf import settings
        msg = str(e).splitlines()[0][:200] if str(e) else ""
        # never reveal credentials or hosts
        msg = re.sub(r"[\w.-]+@[\w.-]+", "<redacted>", msg)
        msg = re.sub(r'"[\w.-]+\.(neon\.tech|render\.com|amazonaws\.com)[^"]*"', "<host>", msg)
        engine = settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1]
        return f"db: ERROR ({engine}) {type(e).__name__}: {msg}".strip()


class HealthCheckMiddleware:
    """Answers Render's health check at /healthz before host/HTTPS checks can reject it.
    /healthz?db=1 also reports whether the database is reachable and migrated."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/healthz/lasterror"):
            return HttpResponse(last_error_text(), content_type="text/plain")
        if request.path == "/healthz" or request.path.startswith("/healthz/db"):
            body = "ok"
            if request.GET.get("db") or request.path.startswith("/healthz/db"):
                body += "\n" + _db_status()
            return HttpResponse(body, content_type="text/plain")
        return self.get_response(request)


# ---------------------------------------------------------------- last error (redacted) for diagnosis
import os as _os
import re as _re
import traceback as _tb

from django.core.signals import got_request_exception
from django.dispatch import receiver

_LAST_ERR = "/tmp/nexform_last_error.txt"


def _redact(s):
    s = _re.sub(r"[\w.+-]+@[\w.-]+", "<email>", s)
    s = _re.sub(r"postgres(ql)?://\S+", "<db-url>", s)
    return s[:300]


@receiver(got_request_exception)
def _remember_error(sender, request=None, **kwargs):
    import sys
    etype, exc, tb = sys.exc_info()
    if exc is None:
        return
    frames = [f for f in _tb.extract_tb(tb)]
    ours = [f for f in frames if "/site-packages/" not in f.filename and "/dist-packages/" not in f.filename] or frames
    where = " <- ".join(f"{_os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in reversed(ours[-4:]))
    last = frames[-1] if frames else None
    deep = f"{_os.path.basename(last.filename)}:{last.lineno}" if last else ""
    path = getattr(request, "path", "?")
    try:
        with open(_LAST_ERR, "w") as fh:
            fh.write(f"path: {path}\nerror: {etype.__name__}: {_redact(str(exc))}\nwhere: {where}\nraised in: {deep}\n")
    except OSError:
        pass


def last_error_text():
    try:
        with open(_LAST_ERR) as fh:
            return fh.read()
    except OSError:
        return "no errors recorded since last restart\n"
