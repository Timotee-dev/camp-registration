from django.contrib.auth import views as auth_views
from django.urls import path

from . import api, views

app_name = "registration"

urlpatterns = [
    # Public
    path("", views.register, name="register"),
    path("registered/<str:code>/", views.success, name="success"),
    path("find-my-registration/", views.lookup, name="lookup"),
    # Staff
    path("staff/login/", auth_views.LoginView.as_view(template_name="registration/login.html",
                                                       redirect_authenticated_user=True), name="login"),
    path("staff/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("staff/", views.dashboard, name="dashboard"),
    path("staff/attendee/<int:pk>/", views.attendee_detail, name="attendee"),
    path("staff/attendee/<int:pk>/resend/", views.resend, name="resend"),
    path("staff/camp/<int:pk>/toggle/", views.toggle_registration, name="toggle"),
    path("staff/export/<str:fmt>/", views.export, name="export"),
    # API
    path("api/camp/", api.ActiveCampView.as_view(), name="api-camp"),
    path("api/register/", api.RegisterView.as_view(), name="api-register"),
    path("api/attendees/", api.AttendeeListView.as_view(), name="api-attendees"),
    path("api/attendees/<int:pk>/", api.AttendeeDetailView.as_view(), name="api-attendee"),
    path("api/stats/", api.StatsView.as_view(), name="api-stats"),
]
