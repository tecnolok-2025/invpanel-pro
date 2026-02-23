from decimal import Decimal
from collections import defaultdict
from .models import Recommendation, Transaction

from django.db import IntegrityError

def _create_reco_safe(**kwargs):
    """Create Recommendation robustly across schema drift (fields added/removed)."""
    # Filter kwargs to existing model fields
    field_names = {f.name for f in Recommendation._meta.get_fields()}
    filtered = {k: v for k, v in kwargs.items() if k in field_names}

    # Ensure defaults for ai_* if those fields exist
    if "ai_action" in field_names and "ai_action" not in filtered:
        filtered["ai_action"] = "HOLD"
    if "ai_summary" in field_names and "ai_summary" not in filtered:
        filtered["ai_summary"] = ""

    try:
        return _create_reco_safe(**filtered)
    except TypeError:
        # In case schema changed between import time and runtime
        filtered.pop("ai_action", None)
        filtered.pop("ai_summary", None)
        return _create_reco_safe(**filtered)
    except IntegrityError:
        # If DB enforces NOT NULL and we missed defaults for any reason
        if "ai_action" in field_names:
            filtered["ai_action"] = filtered.get("ai_action") or "HOLD"
        if "ai_summary" in field_names:
            filtered["ai_summary"] = filtered.get("ai_summary") or ""
        return _create_reco_safe(**filtered)


def holdings_snapshot(portfolio):
    qty = defaultdict(Decimal)
    last_price = defaultdict(Decimal)

    txs = Transaction.objects.filter(portfolio=portfolio).select_related("asset").order_by("tx_date", "id")
    for tx in txs:
        sym = tx.asset.symbol
        if tx.tx_type == "BUY":
            qty[sym] += tx.quantity
            last_price[sym] = tx.price or last_price[sym]
        elif tx.tx_type == "SELL":
            qty[sym] -= tx.quantity
            last_price[sym] = tx.price or last_price[sym]

    values = {}
    total = Decimal("0")
    for sym, q in qty.items():
        if q == 0:
            continue
        v = (q * (last_price[sym] or Decimal("0"))).copy_abs()
        values[sym] = v
        total += v

    weights = {}
    if total > 0:
        for sym, v in values.items():
            weights[sym] = (v / total)

    return {"qty": dict(qty), "last_price": dict(last_price), "values": values, "total": total, "weights": weights}

def generate_recommendations(portfolio, max_items=10):
    snap = holdings_snapshot(portfolio)
    weights = snap["weights"]

    Recommendation.objects.filter(portfolio=portfolio, status="OPEN").delete()

    created = 0
    for sym, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        if w >= Decimal("0.35"):
            _create_reco_safe(
                portfolio=portfolio,
                code="CONCENTRATION_TOP_ASSET",
                severity="MED" if w < Decimal("0.50") else "HIGH",
                title=f"Concentración alta en {sym}",
                rationale="Un solo activo supera el umbral. Considerá diversificar para reducir riesgo específico.",
                evidence={"symbol": sym, "weight": float(w), "threshold": 0.35},
                ai_action="HOLD",  # v11.3: default to avoid NOT NULL
                ai_summary="",     # v11.3: default to avoid NOT NULL
            )
            created += 1
            if created >= max_items:
                return created

    if snap["total"] == 0:
        _create_reco_safe(
            portfolio=portfolio,
            code="EMPTY_PORTFOLIO",
            severity="LOW",
            title="Portafolio sin posiciones detectadas",
            rationale="Cargá movimientos BUY/SELL para obtener métricas y sugerencias con evidencia.",
            evidence={"total_value": float(snap["total"])},
            ai_action="HOLD",  # v11.3: default to avoid NOT NULL
            ai_summary="",     # v11.3: default to avoid NOT NULL
        )
        created += 1

    return created
