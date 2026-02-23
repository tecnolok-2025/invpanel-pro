from decimal import Decimal
from collections import defaultdict
from .models import Recommendation, Transaction

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
            Recommendation.objects.create(
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
        Recommendation.objects.create(
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