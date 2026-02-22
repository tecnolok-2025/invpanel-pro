from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditEvent

def _ip(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        user=user,
        event_type="login",
        ip_address=_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:400] if request else ""),
        details={"path": getattr(request, "path", "")},
    )

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        user=user,
        event_type="logout",
        ip_address=_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:400] if request else ""),
        details={"path": getattr(request, "path", "")},
    )

@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    AuditEvent.objects.create(
        user=None,
        event_type="login_failed",
        ip_address=_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:400] if request else ""),
        details={"username": credentials.get("username"), "path": getattr(request, "path", "")},
    )
