from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from push.utils import get_vapid_public_key


@login_required
def settings_home(request):
    return render(request, "settings/home.html")


@login_required
@ensure_csrf_cookie
def settings_notifications(request):
    return render(request, "settings/notifications.html", {
        "VAPID_PUBLIC_KEY": get_vapid_public_key()
    })
