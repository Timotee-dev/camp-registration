from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from events import views as event_views

admin.site.site_header = f"{settings.SITE_NAME} admin"
admin.site.site_title = settings.SITE_NAME

urlpatterns = [
    path("", event_views.home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("events.urls")),
    path("r/", include("events.public_urls")),
]
