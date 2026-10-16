from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.SITE_NAME} — Admin"
admin.site.site_title = settings.SITE_NAME

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("registration.urls")),
]
