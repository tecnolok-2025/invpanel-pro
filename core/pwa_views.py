from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse


def _file_response(path: Path, content_type: str) -> HttpResponse:
    """Serve small static PWA files from disk without template rendering.

    This avoids running template context processors for /sw.js and /manifest.webmanifest,
    which can otherwise break PWA startup when a context processor raises.
    """
    if not path.exists():
        return HttpResponse("Not found", status=404)
    resp = FileResponse(open(path, "rb"), content_type=content_type)
    # Prevent aggressive caching so mobile clients pick up SW/manifest updates quickly
    resp['Cache-Control'] = 'no-cache'
    return resp


def manifest(request):
    path = Path(settings.BASE_DIR) / "core" / "static" / "pwa" / "manifest.webmanifest"
    return _file_response(path, "application/manifest+json")


def service_worker(request):
    path = Path(settings.BASE_DIR) / "core" / "static" / "pwa" / "sw.js"
    # iOS Safari expects JS content-type
    return _file_response(path, "application/javascript")
