"""Motor de estadística simple (educativo).

Este módulo NO descarga datos de internet.
Trabaja con series históricas cargadas por el usuario (AssetPrice).

Métricas:
- retorno del periodo
- volatilidad anualizada (aprox.)
- Sharpe simple (rf=0)
- max drawdown

Importante: esto NO es asesoramiento financiero.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from datetime import date, timedelta

from django.db.models import QuerySet

from .models import Asset, AssetPrice


@dataclass
class AssetMetrics:
    asset: Asset
    start: date
    end: date
    n: int
    period_return: float
    vol_ann: float
    sharpe: float
    max_drawdown: float


def _max_drawdown(prices: list[float]) -> float:
    peak = prices[0]
    max_dd = 0.0
    for p in prices[1:]:
        if p > peak:
            peak = p
        dd = (p / peak) - 1.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def compute_metrics(asset: Asset, window_days: int = 90) -> AssetMetrics | None:
    qs: QuerySet[AssetPrice] = AssetPrice.objects.filter(asset=asset).order_by("date")
    if not qs.exists():
        return None

    # recortar ventana
    last = qs.last().date
    start_cut = last - timedelta(days=window_days)
    qs = qs.filter(date__gte=start_cut)

    rows = list(qs.values_list("date", "close"))
    if len(rows) < 2:
        return None

    dates = [r[0] for r in rows]
    prices = [float(r[1]) for r in rows]

    # retornos diarios simples
    rets = []
    for i in range(1, len(prices)):
        p0 = prices[i - 1]
        p1 = prices[i]
        if p0 == 0:
            continue
        rets.append((p1 / p0) - 1.0)

    if len(rets) < 2:
        return None

    period_return = (prices[-1] / prices[0]) - 1.0

    # anualización aproximada (252 días hábiles)
    avg = mean(rets)
    vol = pstdev(rets)
    vol_ann = vol * sqrt(252)
    sharpe = 0.0
    if vol_ann > 1e-12:
        sharpe = (avg * 252) / vol_ann

    max_dd = _max_drawdown(prices)

    return AssetMetrics(
        asset=asset,
        start=dates[0],
        end=dates[-1],
        n=len(prices),
        period_return=period_return,
        vol_ann=vol_ann,
        sharpe=sharpe,
        max_drawdown=max_dd,
    )


def rank_assets(window_days: int = 90, limit: int = 20) -> list[AssetMetrics]:
    out: list[AssetMetrics] = []
    for a in Asset.objects.all().order_by("symbol"):
        m = compute_metrics(a, window_days=window_days)
        if m:
            out.append(m)

    # orden principal: Sharpe (desc), secundario: retorno (desc)
    out.sort(key=lambda x: (x.sharpe, x.period_return), reverse=True)
    return out[:limit]
