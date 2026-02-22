from django.urls import path
from . import views

urlpatterns = [
    path("", views.settings_home, name="settings_home"),
    path("notifications/", views.settings_notifications, name="settings_notifications"),
]
