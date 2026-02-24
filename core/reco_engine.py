from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import logging
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import IntegrityError
from django.utils import timezone

from .models import AssetPrice, Recommendation, Transaction

logger = logging.getLogger(__name__)


def diagnose_generation(portfolio) -> Dict:
    """Devuelve un diagnóstico breve para entender por qué 'Generar' podría dar 0."""

    today = timezone.localdate()
    snap = _holdings_snapshot(portfolio)
    holdings: Dict[str, Decimal] = snap["holdings"]
    symbols = sorted(holdings.keys())
    prices = _latest_prices(symbols) if symbols else {}

    stale = 0
    for sym, p in prices.items():
        age = (today - p["date"]).days
        if age > 14:
            stale += 1

    open_count = Recommendation.objects.filter(
        portfolio=portfolio, status=Recommendation.Status.OPEN
    ).count()

    return {
        "portfolio_id": portfolio.id,
        "portfolio_name": getattr(portfolio, "name", ""),
        "tx_count": int(snap.get("tx_count") or 0),
        "holdings_count": int(len(holdings)),
        "negative_positions": snap.get("negative") or [],
        "symbols": symbols,
        "prices_available": int(len(prices)),
        "prices_missing": int(max(0, len(symbols) - len(prices))),
        "prices_stale_gt_14d": int(stale),
        "open_opportunities": int(open_count),
    }


@dataclass(frozen=True)
class RecoDef:
    """Definición de una oportunidad a crear."""

    code: str
    severity: str
    title: str
    rationale: str
    evidence: Dict


@dataclass(frozen=True)
class RecoGenerationResult:
    created: int
    reason: str = ""


# ---------------------------------------------------------------------------
# Helpers (safe creation)


def _create_reco_safe(
    *,
    portfolio,
    code: str,
    severity: str,
    title: str,
    rationale: str,
    evidence: Dict,
    status: str,
) -> Tuple[Optional[Recommendation], bool]:
    """Crea una Recommendation de forma segura.

    Devuelve: (obj | None, created: bool)

    - Si ya existe una OPEN con el mismo code, no duplica.
    - Si ocurre un IntegrityError (p. ej. migraciones inconsistentes), no rompe la app.
    """

    try:
        exists_open = Recommendation.objects.filter(
            portfolio=portfolio, code=code, status=Recommendation.Status.OPEN
        ).exists()
        if exists_open:
            return None, False

        rec = Recommendation.objects.create(
            portfolio=portfolio,
            code=code,
            severity=severity,
            title=title,
            rationale=rationale,
            evidence=evidence or {},
            status=status,
        )
        return rec, True
    except IntegrityError as e:
        # No romper la app: registrar para diagnóstico.
        logger.warning("Reco create IntegrityError (code=%s): %s", code, str(e))
        return None, False
    except Exception as e:
        # Nunca romper por recomendaciones. Registrar para diagnóstico.
        logger.exception("Reco create Exception (code=%s): %s", code, str(e))
        return None, False


# ---------------------------------------------------------------------------
# Portfolio snapshots for simple, explainable rule-based engine


def _holdings_snapshot(portfolio) -> Dict:
    """Snapshot simple de holdings desde transacciones."""

    holdings: Dict[str, Decimal] = {}
    neg_symbols: List[str] = []

    qs = (
        Transaction.objects.filter(portfolio=portfolio)
        .select_related("asset")
        .order_by("-tx_date", "-id")[:800]
    )

    for t in qs:
        sym = (t.asset.symbol or "UNK").upper().strip()
        qty = Decimal(t.quantity or 0)
        if t.tx_type == "BUY":
            holdings[sym] = holdings.get(sym, Decimal("0")) + qty
        elif t.tx_type == "SELL":
            holdings[sym] = holdings.get(sym, Decimal("0")) - qty

    # normalizar / filtrar
    cleaned: Dict[str, Decimal] = {}
    for sym, qty in holdings.items():
        if qty < Decimal("-0.000001"):
            neg_symbols.append(sym)
        if qty > Decimal("0.000001"):
            cleaned[sym] = qty

    return {
        "holdings": cleaned,
        "tx_count": qs.count() if hasattr(qs, "count") else len(qs),
        "negative": sorted(set(neg_symbols)),
    }


def _latest_prices(symbols: Iterable[str]) -> Dict[str, Dict]:
    """Último precio por símbolo.

    Nota: AssetPrice referencia Asset por FK, no guarda symbol directo.
    """

    out: Dict[str, Dict] = {}
    for sym in symbols:
        p = (
            AssetPrice.objects.filter(asset__symbol=sym)
            .select_related("asset")
            .order_by("-date")
            .first()
        )
        if p:
            out[sym] = {
                "date": p.date,
                "close": Decimal(p.close),
                "currency": getattr(p.asset, "currency", ""),
                "asset_type": getattr(p.asset, "asset_type", ""),
                "name": getattr(p.asset, "name", ""),
            }
    return out


# ---------------------------------------------------------------------------
# Rule-based generator (fast, explainable)


def build_recos(portfolio) -> Tuple[List[RecoDef], str]:
    """Genera oportunidades con reglas simples y auditables.

    Prioridades de diseño:
    - Siempre devolver algo útil (aunque el portafolio esté vacío).
    - Reglas simples: concentración / moneda / precios faltantes / precios viejos.
    - Explicaciones claras en castellano.

    Retorna: ([RecoDef...], reason_if_empty)
    """

    today = timezone.localdate()

    snap = _holdings_snapshot(portfolio)
    holdings: Dict[str, Decimal] = snap["holdings"]
    tx_count: int = int(snap["tx_count"] or 0)
    negatives: List[str] = snap["negative"]

    recos: List[RecoDef] = []

    # 0) Calidad de datos: ventas > compras
    if negatives:
        sym = negatives[0]
        recos.append(
            RecoDef(
                code=f"DATA-NEG-{sym}-{portfolio.id}",
                severity=Recommendation.Severity.HIGH,
                title=f"Inconsistencia: posición negativa en {sym}",
                rationale=(
                    "Detecté una posición negativa (vendiste más de lo que compraste) para este símbolo. "
                    "Esto suele indicar carga incompleta de transacciones o un error en el tipo (BUY/SELL). "
                    "Mientras exista esta inconsistencia, cualquier cálculo de exposición o concentración puede ser incorrecto."
                ),
                evidence={
                    "tipo": "calidad_datos",
                    "simbolo": sym,
                    "nota": "Revisar transacciones BUY/SELL del portafolio.",
                },
            )
        )

    # 1) Portafolio sin datos
    if tx_count == 0:
        recos.append(
            RecoDef(
                code=f"SETUP-EMPTY-{portfolio.id}",
                severity=Recommendation.Severity.MED,
                title="Portafolio sin movimientos cargados",
                rationale=(
                    "Para que el botón ‘Generar’ produzca oportunidades reales, primero necesitás cargar tu portafolio: "
                    "agregá Activos (símbolos) y luego registrá transacciones (BUY/SELL) dentro del portafolio. "
                    "Si tu objetivo es solo aprender el flujo, usá ‘Generar DEMO’."
                ),
                evidence={
                    "tipo": "setup",
                    "tx_count": tx_count,
                    "siguiente_paso": "Ir a Portafolios → abrir tu portafolio → cargar transacciones.",
                },
            )
        )

    # 2) Hay transacciones pero no hay holdings (p.ej. todo vendido)
    if tx_count > 0 and not holdings:
        recos.append(
            RecoDef(
                code=f"SETUP-NOHOLD-{portfolio.id}",
                severity=Recommendation.Severity.LOW,
                title="Sin posiciones abiertas (holdings = 0)",
                rationale=(
                    "Hay movimientos cargados, pero hoy no tenés posiciones netas positivas (todo quedó en cero). "
                    "Si esto es correcto, no hay mucho para alertar. Si no es correcto, revisá BUY/SELL o cantidades." 
                ),
                evidence={"tipo": "estado_portafolio", "tx_count": tx_count},
            )
        )

    # 3) Si hay holdings, aplicar reglas de exposición
    if holdings:
        symbols = sorted(holdings.keys())
        prices = _latest_prices(symbols)

        missing_prices = [s for s in symbols if s not in prices]
        if missing_prices:
            recos.append(
                RecoDef(
                    code=f"PRICES-MISSING-{portfolio.id}",
                    severity=Recommendation.Severity.MED,
                    title="Faltan precios cargados para algunos activos",
                    rationale=(
                        "Para calcular concentración, riesgo y alertas con más precisión, el sistema necesita precios históricos (CSV) "
                        "para cada símbolo. Te faltan precios para: "
                        f"{', '.join(missing_prices[:10])}" + ("…" if len(missing_prices) > 10 else "") + ". "
                        "Podés cargarlos en Análisis (PRO) → Cargar precios (CSV)."
                    ),
                    evidence={"tipo": "precios", "missing": missing_prices},
                )
            )

        # Valuación (solo símbolos con precios)
        values: Dict[str, Decimal] = {}
        total = Decimal("0")
        stale: List[Dict] = []

        for sym, qty in holdings.items():
            p = prices.get(sym)
            if not p:
                continue
            close = Decimal(p["close"])
            v = (qty * close)
            values[sym] = v
            total += v
            age = (today - p["date"]).days
            if age > 14:
                stale.append({"symbol": sym, "age_days": age, "date": str(p["date"]), "close": float(close)})

        if total <= Decimal("0"):
            # No se pudo valuar (no hay precios para ninguno, o todo 0)
            recos.append(
                RecoDef(
                    code=f"PRICES-ALLMISSING-{portfolio.id}",
                    severity=Recommendation.Severity.MED,
                    title="No hay precios suficientes para generar alertas de exposición",
                    rationale=(
                        "Detecté posiciones, pero no pude valorarlas porque faltan precios históricos. "
                        "Cargá al menos un CSV por símbolo para habilitar reglas de concentración/moneda/antigüedad."
                    ),
                    evidence={"tipo": "precios", "holdings": {k: float(v) for k, v in holdings.items()}},
                )
            )
            return recos, ""

        # 3a) Concentración
        weights = {sym: (v / total) for sym, v in values.items() if total > 0}
        top_sym = max(weights, key=lambda k: weights[k])
        top_w = weights[top_sym]
        if top_w >= Decimal("0.55"):
            recos.append(
                RecoDef(
                    code=f"CONC-HIGH-{top_sym}-{portfolio.id}",
                    severity=Recommendation.Severity.HIGH,
                    title=f"Alta concentración en {top_sym} ({(top_w*100):.1f}%)",
                    rationale=(
                        "Una sola posición concentra más de la mitad del valor estimado del portafolio. "
                        "Esto incrementa el riesgo específico (lo que pase con ese activo domina el resultado). "
                        "Acción sugerida: revisar si está alineado con tu perfil; considerar diversificar o rebalancear gradualmente."
                    ),
                    evidence={
                        "tipo": "concentracion",
                        "top": top_sym,
                        "top_weight": float(top_w),
                        "weights": {k: float(v) for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:8]},
                    },
                )
            )
        elif top_w >= Decimal("0.35"):
            recos.append(
                RecoDef(
                    code=f"CONC-MED-{top_sym}-{portfolio.id}",
                    severity=Recommendation.Severity.MED,
                    title=f"Concentración moderada en {top_sym} ({(top_w*100):.1f}%)",
                    rationale=(
                        "La posición principal pesa más de un tercio del portafolio. "
                        "No siempre es malo, pero conviene monitorearlo y definir un rango objetivo (p. ej. 20–35%) según tu estrategia."
                    ),
                    evidence={
                        "tipo": "concentracion",
                        "top": top_sym,
                        "top_weight": float(top_w),
                        "weights": {k: float(v) for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:8]},
                    },
                )
            )

        # 3b) Moneda (exposición por currency del Asset)
        currency_values: Dict[str, Decimal] = {}
        for sym, v in values.items():
            cur = (prices.get(sym, {}).get("currency") or "?").upper()
            currency_values[cur] = currency_values.get(cur, Decimal("0")) + v

        base = (getattr(portfolio, "base_currency", "ARS") or "ARS").upper()
        # Si hay exposición relevante a monedas distintas de la base
        other = {cur: val for cur, val in currency_values.items() if cur and cur != base}
        if other:
            # top other currency
            top_cur = max(other, key=lambda c: other[c])
            w = other[top_cur] / total
            if w >= Decimal("0.25"):
                recos.append(
                    RecoDef(
                        code=f"FX-{top_cur}-{portfolio.id}",
                        severity=Recommendation.Severity.MED,
                        title=f"Exposición relevante a moneda {top_cur} ({(w*100):.1f}%)",
                        rationale=(
                            f"Tu portafolio base está en {base}, pero una parte importante está valuada en {top_cur}. "
                            "Esto puede ser intencional (cobertura) o un riesgo adicional (tipo de cambio). "
                            "Acción sugerida: revisar si esta exposición es deseada y si tenés un rango objetivo."
                        ),
                        evidence={
                            "tipo": "moneda",
                            "base_currency": base,
                            "currency_weights": {k: float(v / total) for k, v in currency_values.items()},
                        },
                    )
                )

        # 3c) Precios viejos
        if stale:
            stale_sorted = sorted(stale, key=lambda x: x["age_days"], reverse=True)
            recos.append(
                RecoDef(
                    code=f"PRICES-STALE-{portfolio.id}",
                    severity=Recommendation.Severity.LOW,
                    title="Hay precios históricos desactualizados (más de 14 días)",
                    rationale=(
                        "Para que los cálculos y el ranking PRO sean representativos, conviene actualizar históricos "
                        "cuando hay huecos o datos viejos. Podés volver a subir el CSV del símbolo o completar fechas faltantes."
                    ),
                    evidence={"tipo": "precios", "stale": stale_sorted[:10]},
                )
            )

        # 3d) Muchas posiciones pequeñas
        small = [sym for sym, w in weights.items() if w < Decimal("0.01")]
        if len(symbols) >= 10 and len(small) >= 5:
            recos.append(
                RecoDef(
                    code=f"CLEANUP-SMALL-{portfolio.id}",
                    severity=Recommendation.Severity.LOW,
                    title="Muchas posiciones muy pequeñas (<1%)",
                    rationale=(
                        "Tenés varias posiciones que pesan menos del 1% cada una. Esto puede complicar el seguimiento sin aportar mucho impacto. "
                        "Acción sugerida: revisar si conviene simplificar (consolidar) o si forman parte de una estrategia diversificada." 
                    ),
                    evidence={"tipo": "estructura", "small_positions": small[:20], "count": len(small)},
                )
            )

    return recos, ""


def generate_recommendations(panel) -> RecoGenerationResult:
    """Genera oportunidades para un portafolio.

    `panel` se usa como nombre histórico; es un Portfolio.
    """

    recos, reason_if_empty = build_recos(panel)

    if not recos:
        return RecoGenerationResult(created=0, reason=reason_if_empty or "No se encontraron condiciones para generar oportunidades.")

    created = 0
    failed = 0
    for r in recos:
        _, ok = _create_reco_safe(
            portfolio=panel,
            code=r.code,
            severity=r.severity,
            title=r.title,
            rationale=r.rationale,
            evidence=r.evidence,
            status=Recommendation.Status.OPEN,
        )
        if ok:
            created += 1
        else:
            failed += 1

    if created == 0:
        # Lo más común: ya existían OPEN con los mismos códigos.
        # También puede indicar un problema de DB/migraciones (ver logs si hay warnings).
        reason = "No se generaron nuevas oportunidades (probablemente ya existían oportunidades OPEN iguales)."
        if failed:
            reason += " Además, hubo errores al crear oportunidades (ver logs en Render)."
        return RecoGenerationResult(created=0, reason=reason)

    return RecoGenerationResult(created=created, reason="")
