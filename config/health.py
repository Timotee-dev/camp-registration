from django.http import HttpResponse


class HealthCheckMiddleware:
    """Answers Render's health check at /healthz before host/HTTPS checks can reject it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
