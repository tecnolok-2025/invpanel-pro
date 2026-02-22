from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("portfolios/", views.portfolios, name="portfolios"),
    path("portfolios/<int:portfolio_id>/", views.portfolio_detail, name="portfolio_detail"),
    path("assets/", views.assets, name="assets"),

    path("simulator/", views.simulator, name="simulator"),
    path("simulator/<int:sim_id>/", views.sim_detail, name="sim_detail"),

    path("analytics/", views.analytics, name="analytics"),
    path("prices/upload/", views.prices_upload, name="prices_upload"),
    path("prices/history/", views.prices_history, name="prices_history"),

    path("alerts/", views.alerts_inbox, name="alerts_inbox"),
    path("alerts/test/", views.test_alerts, name="test_alerts"),
    path("alerts/run/", views.run_alerts, name="run_alerts"),

    path("opportunities/", views.opportunities, name="opportunities"),
    path("opportunities/db/", views.opportunities_db, name="opportunities_db"),

    path("manual/", views.manual, name="manual"),
    path("manual/pdf/", views.manual_pdf, name="manual_pdf"),

    path("api/badges/", views.badges_api, name="badges_api"),
    path("healthz/", views.healthz, name="healthz"),
]
