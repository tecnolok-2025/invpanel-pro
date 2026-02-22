import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pywebpush import webpush, WebPushException

from .models import PushSubscription
from .utils import get_vapid_private_key_pem, get_vapid_claims_sub


@require_http_methods(["POST"])
@login_required
def subscribe(request):
    """Guarda/actualiza una suscripción Web Push para el usuario logueado."""
    try:
        data = json.loads(request.body.decode("utf-8"))
        endpoint = data["endpoint"]
        keys = data["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]
    except Exception:
        return HttpResponseBadRequest("Invalid subscription payload")

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
    )
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
@login_required
def unsubscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        endpoint = data["endpoint"]
    except Exception:
        return HttpResponseBadRequest("Invalid payload")
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({"ok": True})


@require_http_methods(["GET", "POST"])
@login_required
def test_push(request):
    """Pantalla de diagnóstico + endpoint POST para enviar push de prueba.

    - GET: muestra estado (suscripciones, VAPID configurado)
    - POST: envía notificación a suscripciones del usuario y responde JSON

    Importante: NO devolvemos 500 por configuración faltante para evitar
    "errores rojos" en el navegador y confusión del usuario.
    """

    if request.method == "GET":
        subs_count = PushSubscription.objects.filter(user=request.user).count()
        private_key_ok = bool(get_vapid_private_key_pem())
        claims_sub = (get_vapid_claims_sub() or "").strip()
        return render(
            request,
            "push/test.html",
            {
                "subs_count": subs_count,
                "private_key_ok": private_key_ok,
                "claims_sub": claims_sub,
            },
        )

    private_key_pem = get_vapid_private_key_pem()
    if not private_key_pem:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Push no configurado: falta VAPID_PRIVATE_KEY_PEM_B64 (y/o VAPID_CLAIMS_SUB). "
                    "Solución: correr tools/generate_vapid.py y cargar VAPID_PUBLIC_KEY, "
                    "VAPID_PRIVATE_KEY_PEM_B64 y VAPID_CLAIMS_SUB en Environment Variables (Render/Windows)."
                ),
            },
            status=200,
        )

    subs = PushSubscription.objects.filter(user=request.user)
    payload = json.dumps({"title": "InvPanel", "body": "Notificación de prueba ✅", "url": "/"})

    sent = 0
    for s in subs:
        subscription_info = {"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}}
        try:
            webpush(
                subscription_info,
                data=payload,
                vapid_private_key=private_key_pem,
                vapid_claims={"sub": get_vapid_claims_sub()},
            )
            sent += 1
        except WebPushException:
            # Limpieza si el endpoint murió
            PushSubscription.objects.filter(endpoint=s.endpoint).delete()

    return JsonResponse({"ok": True, "sent": sent})
