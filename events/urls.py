from django.urls import path

from . import api, views

app_name = "events"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("new/", views.event_create, name="create"),
    path("<int:pk>/build/", views.build, name="build"),
    path("<int:pk>/share/", views.share, name="share"),
    path("<int:pk>/share/qr.png", views.qr_png, name="qr_png"),
    path("<int:pk>/settings/", views.event_settings, name="settings"),
    path("<int:pk>/toggle/", views.toggle_open, name="toggle"),
    path("<int:pk>/duplicate/", views.duplicate, name="duplicate"),
    path("<int:pk>/delete/", views.delete_event, name="delete"),
    path("<int:pk>/responses/", views.responses, name="responses"),
    path("<int:pk>/responses/<int:number>/", views.response_detail, name="response"),
    path("<int:pk>/responses/<int:number>/delete/", views.response_delete, name="response_delete"),
    path("<int:pk>/summary/", views.summary, name="summary"),
    path("<int:pk>/export/<str:fmt>/", views.export, name="export"),
    path("api/<int:pk>/questions/", api.QuestionsView.as_view(), name="api_questions"),
]
