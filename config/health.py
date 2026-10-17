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
        return f"db: ok ({vendor})"
    except Exception as e:  # noqa: BLE001
        msg = str(e).splitlines()[0][:160] if type(e).__name__ == "ProgrammingError" else ""
        return f"db: ERROR {type(e).__name__} {msg}".strip()


class HealthCheckMiddleware:
    """Answers Render's health check at /healthz before host/HTTPS checks can reject it.
    /healthz?db=1 also reports whether the database is reachable and migrated."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            body = "ok"
            if request.GET.get("db"):
                body += "\n" + _db_status()
            return HttpResponse(body, content_type="text/plain")
        return self.get_response(request)
