from django.urls import path
from . import views

urlpatterns = [
    path("subscribe/", views.subscribe, name="push_subscribe"),
    path("unsubscribe/", views.unsubscribe, name="push_unsubscribe"),
    path("test/", views.test_push, name="push_test"),
]
