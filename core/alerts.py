"""Alertas por email (educativo).

- Se disparan vía cron (Render) o vía endpoint seguro (token).
- Incluye un "procedimiento" dentro del mail para guiar al usuario.

NOTA: no es asesoramiento financiero.
"""

from __future__ import annotations

import os
from urllib.parse import urljoin

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .stats_engine import rank_assets


def _is_email_configured() -> bool:
    return bool(os.getenv("EMAIL_HOST") and os.getenv("EMAIL_HOST_USER") and os.getenv("EMAIL_HOST_PASSWORD"))


def send_daily_alert(base_url: str, dry_run: bool = False) -> tuple[bool, str]:
    """Envía un email con ranking y procedimiento.

    Returns: (ok, message)
    """

    to_email = os.getenv("ALERT_EMAIL_TO") or os.getenv("ADMIN_EMAIL")
    from_email = os.getenv("ALERT_FROM_EMAIL") or os.getenv("DEFAULT_FROM_EMAIL") or os.getenv("EMAIL_HOST_USER")

    if not to_email:
        return False, "ALERT_EMAIL_TO/ADMIN_EMAIL no configurado"

    if not _is_email_configured():
        return False, "Config SMTP incompleta (EMAIL_HOST/USER/PASSWORD)"

    window_days = int(os.getenv("ALERT_WINDOW_DAYS", "90"))
    top = rank_assets(window_days=window_days, limit=10)

    now = timezone.localtime()
    subject = f"[invpanel-pro] Alerta diaria ({now:%Y-%m-%d %H:%M})"

    ctx = {
        "base_url": base_url.rstrip("/") + "/",
        "login_url": urljoin(base_url.rstrip("/") + "/", "login/"),
        "window_days": window_days,
        "top": top,
        "generated_at": now,
        "disclaimer": (
            "Este mensaje es educativo e informativo. No constituye asesoramiento financiero. "
            "Cualquier decisión real debe ser verificada por vos y, si corresponde, por un asesor matriculado."
        ),
    }

    text_body = render_to_string("core/email_alert.txt", ctx)
    html_body = render_to_string("core/email_alert.html", ctx)

    if dry_run:
        # No envía email: solo valida y devuelve el cuerpo armado.
        return True, "DRY RUN OK (no se envió email).\n\n" + text_body

    msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=[to_email])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True, f"Enviado a {to_email}"
