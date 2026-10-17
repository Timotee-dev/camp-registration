from django.urls import path

from . import public

app_name = "public"

urlpatterns = [
    path("<str:code>/", public.form, name="form"),
    path("<str:code>/thanks/", public.thanks, name="thanks"),
]
