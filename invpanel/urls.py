from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from core import pwa_views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("settings/", include("panel_settings.urls")),
    path("push/", include("push.urls")),

    # PWA files at root (Safari iOS expects /sw.js and /manifest.webmanifest).
    # Served WITHOUT template rendering so they do not depend on context processors.
    path("manifest.webmanifest", pwa_views.manifest, name="pwa_manifest"),
    path("sw.js", pwa_views.service_worker, name="pwa_sw"),

    path("", include(("core.urls", "core"), namespace="core")),
]
