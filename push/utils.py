import os
import base64
import binascii

_PLACEHOLDER_PREFIXES = ("PEGAR_", "PEGA_", "PASTE_", "INSERT_")


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip()
    return (not v) or any(v.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def get_vapid_public_key() -> str:
    v = os.environ.get("VAPID_PUBLIC_KEY", "").strip().strip('"').strip("'")
    if _is_placeholder(v):
        return ""
    return v


def get_vapid_private_key_pem() -> str:
    """Devuelve la clave privada VAPID en PEM, decodificada desde base64.

    Espera VAPID_PRIVATE_KEY_PEM_B64 = base64(PEM).
    Si la variable está vacía o contiene texto placeholder, devuelve "".
    Si la base64 es inválida, devuelve "" (para evitar 500 confusos).
    """
    b64 = os.environ.get("VAPID_PRIVATE_KEY_PEM_B64", "").strip().strip('"').strip("'")
    if _is_placeholder(b64):
        return ""
    try:
        return base64.b64decode(b64, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ""


def get_vapid_claims_sub() -> str:
    v = os.environ.get("VAPID_CLAIMS_SUB", "mailto:admin@example.com").strip()
    if _is_placeholder(v):
        return "mailto:admin@example.com"
    return v
