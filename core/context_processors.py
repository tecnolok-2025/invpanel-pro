from __future__ import annotations

from typing import Dict


def nav_badges(request) -> Dict[str, int]:
    """Badges for navigation.

    CRÍTICO: este context processor NO debe romper nunca.
    Si falla, puede generar pantallas en blanco (y romper PWA).

    Hoy el proyecto usa principalmente:
    - Oportunidades (Recommendation) en estado OPEN -> badge rojo del menú.
    """

    try:
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return {"nav_alerts_count": 0, "nav_opps_count": 0, "nav_app_badge": 0}

        from .models import Recommendation

        try:
            open_status = Recommendation.Status.OPEN
        except Exception:
            open_status = "OPEN"

        open_count = int(
            Recommendation.objects.filter(portfolio__owner=user, status=open_status).count()
        )

        # ALERTAS (email/push) hoy no tienen un inbox propio persistido; dejamos 0 para no confundir.
        alerts_count = 0

        return {
            "nav_alerts_count": alerts_count,
            "nav_opps_count": open_count,
            "nav_app_badge": open_count,
        }
    except Exception:
        return {"nav_alerts_count": 0, "nav_opps_count": 0, "nav_app_badge": 0}
