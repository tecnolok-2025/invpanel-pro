from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO, TextIOWrapper

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.management import call_command
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

def logout_any(request):
    """Logout que acepta GET y POST.

    Render/usuarios a veces navegan /logout/ por GET (por historial, links viejos o PWA).
    Django por defecto responde 405 a GET. Esta vista evita pantallas en blanco/confusión,
    manteniendo el flujo simple: cerrar sesión y volver a /login/.
    """
    logout(request)
    return redirect("/login/")

from django.db.models import Q
from django.conf import settings

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, PageBreak
from reportlab.lib.units import cm

from .alerts import send_daily_alert
from .forms import (
    AdvanceDaysForm,
    AssetForm,
    PortfolioForm,
    PriceUploadForm,
    SimTradeForm,
    SimulationForm,
    TransactionForm,
)
from .price_engine import price_for

from .models import (
    Asset,
    AssetPrice,
    AuditEvent,
    Portfolio,
    Recommendation,
    SimPosition,
    SimTrade,
    Simulation,
    Transaction,
)
from .reco_engine import generate_recommendations, diagnose_generation, _create_reco_safe
from .stats_engine import rank_assets
from .ai_engine import evaluate_recommendation


# ---------------------------------------------------------------------------
# Helpers


def _audit(request, event_type: str, details: dict):
    try:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:400]
        AuditEvent.objects.create(
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            event_type=event_type,
            ip_address=ip,
            user_agent=ua,
            details=details or {},
        )
    except Exception:
        # Auditing must never break the app.
        pass



def _portfolio_snapshot(portfolio: Portfolio) -> dict:
    # Snapshot simple para IA: holdings aproximadas desde transacciones
    qs = Transaction.objects.filter(portfolio=portfolio).order_by("-tx_date")[:200]
    holdings = {}
    cash = {}
    for t in qs:
        sym = getattr(t.asset, "symbol", "UNK")
        qty = float(t.quantity or 0)
        if t.tx_type == "BUY":
            holdings[sym] = holdings.get(sym, 0.0) + qty
        elif t.tx_type == "SELL":
            holdings[sym] = holdings.get(sym, 0.0) - qty
        elif t.tx_type == "DEPOSIT":
            cash[sym] = cash.get(sym, 0.0) + float(t.price or 0)
        elif t.tx_type == "WITHDRAW":
            cash[sym] = cash.get(sym, 0.0) - float(t.price or 0)

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "base_currency": portfolio.base_currency,
        "holdings": holdings,
        "cash": cash,
        "last_tx_count": qs.count() if hasattr(qs, "count") else len(qs),
    }


def _price_snapshot_for_portfolio(portfolio: Portfolio) -> dict:
    # Usa el último AssetPrice por símbolo si existe
    symbols = list(
        Asset.objects.filter(transaction__portfolio=portfolio).values_list("symbol", flat=True).distinct()
    )
    snap = {}
    for sym in symbols[:50]:
        # AssetPrice referencia Asset por FK (no hay campo symbol directo)
        p = AssetPrice.objects.filter(asset__symbol=sym).order_by("-date").first()
        if p:
            snap[sym] = {"date": str(p.date), "close": float(p.close)}
    return snap

def _get_or_create_default_portfolio(user) -> Portfolio:
    p = Portfolio.objects.filter(owner=user).order_by("id").first()
    if p:
        return p
    return Portfolio.objects.create(owner=user, name="Mi Portafolio", base_currency="ARS")


# ---------------------------------------------------------------------------
# Dashboard


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    portfolios = Portfolio.objects.filter(owner=request.user).order_by("-created_at")[:5]
    sims = Simulation.objects.filter(owner=request.user).order_by("-created_at")[:5]
    return render(request, "core/dashboard.html", {"portfolios": portfolios, "sims": sims})


# ---------------------------------------------------------------------------
# Portfolios


@login_required
@require_http_methods(["GET", "POST"])
def portfolios(request):
    qs = Portfolio.objects.filter(owner=request.user).order_by("-created_at")
    form = PortfolioForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.owner = request.user
        p.save()
        _audit(request, "portfolio_create", {"portfolio_id": p.id})
        messages.success(request, "Portafolio creado.")
        return redirect("core:portfolio_detail", portfolio_id=p.id)

    return render(request, "core/portfolios.html", {"items": qs, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def portfolio_detail(request, portfolio_id: int):
    portfolio = get_object_or_404(Portfolio, id=portfolio_id, owner=request.user)

    # Campo correcto: tx_date
    tx_qs = Transaction.objects.filter(portfolio=portfolio).order_by("-tx_date", "-id")
    tx_form = TransactionForm(request.POST or None)

    if request.method == "POST" and tx_form.is_valid():
        tx = tx_form.save(commit=False)
        tx.portfolio = portfolio
        tx.save()
        _audit(request, "tx_create", {"portfolio_id": portfolio.id, "tx_id": tx.id})
        messages.success(request, "Movimiento agregado.")
        return redirect("core:portfolio_detail", portfolio_id=portfolio.id)

    recs = Recommendation.objects.filter(portfolio=portfolio).order_by("-created_at")[:50]

    return render(
        request,
        "core/portfolio_detail.html",
        {
            "portfolio": portfolio,
            "tx": tx_qs,
            "tx_form": tx_form,
            "recs": recs,
        },
    )


# ---------------------------------------------------------------------------
# Assets


@login_required
@require_http_methods(["GET", "POST"])
def assets(request):
    qs = Asset.objects.all().order_by("symbol")
    form = AssetForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        a = form.save()
        _audit(request, "asset_create", {"asset_id": a.id, "symbol": a.symbol})
        messages.success(request, "Activo creado.")
        return redirect("core:assets")

    return render(request, "core/assets.html", {"items": qs, "form": form})


# ---------------------------------------------------------------------------
# Simulator (training)


@login_required
@require_http_methods(["GET", "POST"])
def simulator(request):
    sims = Simulation.objects.filter(owner=request.user).order_by("-created_at")
    form = SimulationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        sim = form.save(commit=False)
        sim.owner = request.user
        sim.save()
        _audit(request, "sim_create", {"sim_id": sim.id})
        messages.success(request, "Simulación creada.")
        return redirect("core:sim_detail", sim_id=sim.id)

    return render(request, "core/simulator.html", {"items": sims, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def sim_detail(request, sim_id: int):
    """Detalle de simulación (entrenamiento).

    IMPORTANTE: es educativo, NO opera con dinero real.
    """
    sim = get_object_or_404(Simulation, id=sim_id, owner=request.user)

    trade_form = SimTradeForm(request.POST or None)
    adv_form = AdvanceDaysForm(request.POST or None)

    def _current_price(symbol: str) -> Decimal:
        symbol = (symbol or "").strip().upper()
        base = 100.0
        try:
            last = (
                AssetPrice.objects.filter(asset__symbol=symbol)
                .order_by("-date")
                .values_list("close", flat=True)
                .first()
            )
            if last is not None:
                base = float(last)
        except Exception:
            pass
        # Precio determinístico por día/seed, usando base si existe histórico.
        return price_for(symbol, day=int(sim.current_day), seed=int(sim.seed or 1), base=base)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()

        if action == "trade" and trade_form.is_valid():
            symbol = trade_form.cleaned_data["symbol"].strip().upper()
            side = trade_form.cleaned_data["side"]
            qty = trade_form.cleaned_data["quantity"]
            px = trade_form.cleaned_data.get("price") or _current_price(symbol)

            # posición actual
            pos, _ = SimPosition.objects.get_or_create(
                simulation=sim,
                symbol=symbol,
                defaults={"quantity": Decimal("0"), "avg_price": Decimal("0")},
            )

            if side == "BUY":
                cost = (qty * px)
                if sim.virtual_cash < cost:
                    messages.error(request, "Cash insuficiente para comprar en la simulación.")
                    return redirect("core:sim_detail", sim_id=sim.id)

                # promedio ponderado
                new_qty = pos.quantity + qty
                if pos.quantity > 0 and pos.avg_price > 0:
                    pos.avg_price = ((pos.quantity * pos.avg_price) + (qty * px)) / new_qty
                else:
                    pos.avg_price = px
                pos.quantity = new_qty

                sim.virtual_cash = sim.virtual_cash - cost
                sim.save(update_fields=["virtual_cash"])
                pos.save(update_fields=["quantity", "avg_price", "updated_at"])

            else:  # SELL
                if pos.quantity < qty:
                    messages.error(request, "No podés vender más unidades de las que tenés en la simulación.")
                    return redirect("core:sim_detail", sim_id=sim.id)

                proceeds = (qty * px)
                pos.quantity = pos.quantity - qty
                if pos.quantity <= 0:
                    pos.quantity = Decimal("0")
                    pos.avg_price = Decimal("0")
                pos.save(update_fields=["quantity", "avg_price", "updated_at"])

                sim.virtual_cash = sim.virtual_cash + proceeds
                sim.save(update_fields=["virtual_cash"])

            t = SimTrade.objects.create(
                simulation=sim,
                symbol=symbol,
                side=side,
                quantity=qty,
                price=px,
                day=int(sim.current_day),
            )
            _audit(request, "sim_trade", {"sim_id": sim.id, "trade_id": t.id, "symbol": symbol, "side": side})
            messages.success(request, "Operación registrada en la simulación.")
            return redirect("core:sim_detail", sim_id=sim.id)

        if action == "advance" and adv_form.is_valid():
            days = int(adv_form.cleaned_data["days"])
            sim.current_day = int(sim.current_day) + days
            sim.save(update_fields=["current_day"])
            _audit(request, "sim_advance", {"sim_id": sim.id, "days": days})
            messages.success(request, f"Se avanzó {days} día(s).")
            return redirect("core:sim_detail", sim_id=sim.id)

    positions = SimPosition.objects.filter(simulation=sim).order_by("symbol")
    trades = SimTrade.objects.filter(simulation=sim).order_by("-id")[:200]

    rows = []
    total_positions = Decimal("0")
    for p in positions:
        px = _current_price(p.symbol)
        val = (p.quantity or Decimal("0")) * px
        total_positions += val
        rows.append(
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_price": p.avg_price,
                "price": px,
                "value": val,
            }
        )

    total_value = (sim.virtual_cash or Decimal("0")) + total_positions

    return render(
        request,
        "core/simulator_detail.html",
        {
            "sim": sim,
            "trade_form": trade_form,
            "adv_form": adv_form,
            "rows": rows,
            "trades": trades,
            "total_value": total_value,
            "cash": sim.virtual_cash,
        },
    )


@login_required
@require_http_methods(["GET"])
def analytics(request):
    try:
        window = int(request.GET.get("window") or 90)
    except Exception:
        window = 90
    window = max(7, min(window, 3650))

    ranked = rank_assets(window_days=window)

    return render(request, "core/analytics.html", {"ranked": ranked, "window": window})


@login_required
@require_http_methods(["GET", "POST"])
def prices_upload(request):
    """Carga de históricos (CSV) para el módulo Análisis (PRO).

    Soporta 2 formatos:

    A) Por activo seleccionado (más simple)
       - Seleccionás el activo en el combo
       - CSV: date,close   (o fecha,precio)

    B) Multi-activo (sin seleccionar activo)
       - Dejás el combo vacío
       - CSV: date,symbol,close   (y opcional name)

    Separador aceptado: coma o punto y coma.
    """

    form = PriceUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        asset_selected = form.cleaned_data.get("asset")
        up = form.cleaned_data["csv_file"]

        # Normalizar lectura (soporta UTF-8 / Windows-1252 con fallback)
        wrapper = TextIOWrapper(up.file, encoding="utf-8", errors="ignore")
        sample = wrapper.read(2048)
        wrapper.seek(0)

        # Detectar separador de forma robusta
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ";" if sample.count(";") > sample.count(",") else ","

        reader = csv.DictReader(wrapper, delimiter=delimiter)
        inserted = 0
        updated = 0
        skipped = 0

        def _parse_date(s: str):
            s = (s or "").strip()
            if not s:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(s, fmt).date()
                except Exception:
                    pass
            return None

        def _parse_decimal(s: str):
            s = (s or "").strip()
            if not s:
                return None
            # 123,45 -> 123.45 (si no hay punto)
            if "," in s and "." not in s:
                s = s.replace(",", ".")
            try:
                return Decimal(s)
            except Exception:
                return None

        for row in reader:
            # DictReader devuelve None keys si el CSV no tiene header claro
            if not isinstance(row, dict):
                skipped += 1
                continue

            # normalizar claves a minúsculas
            r = {str(k).strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k is not None}

            d = _parse_date(r.get("date") or r.get("fecha"))
            if not d:
                skipped += 1
                continue

            close = _parse_decimal(r.get("close") or r.get("precio") or r.get("price"))
            if close is None:
                skipped += 1
                continue

            if asset_selected:
                asset = asset_selected
            else:
                sym = (r.get("symbol") or r.get("ticker") or "").strip().upper()
                if not sym:
                    skipped += 1
                    continue
                name = (r.get("name") or "").strip()
                asset, _ = Asset.objects.get_or_create(symbol=sym, defaults={"name": name or sym})

            obj, created = AssetPrice.objects.update_or_create(
                asset=asset,
                date=d,
                defaults={"close": close},
            )
            if created:
                inserted += 1
            else:
                updated += 1

        if inserted or updated:
            messages.success(
                request,
                f"Históricos cargados: +{inserted} nuevos, {updated} actualizados. Omitidos: {skipped}.",
            )
        else:
            messages.warning(request, f"No se cargaron filas válidas. Omitidos: {skipped}.")

        return redirect("core:prices_history")

    return render(request, "core/prices_upload.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def prices_history(request):
    """Históricos: tabla simple para verificar que se cargaron precios."""

    qs = AssetPrice.objects.select_related("asset").order_by("-date")

    symbol = (request.GET.get("symbol") or "").strip().upper()
    date_from = (request.GET.get("from") or "").strip()
    date_to = (request.GET.get("to") or "").strip()

    if symbol:
        qs = qs.filter(asset__symbol=symbol)

    def _parse(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None

    df = _parse(date_from)
    dt = _parse(date_to)
    if df:
        qs = qs.filter(date__gte=df)
    if dt:
        qs = qs.filter(date__lte=dt)

    return render(
        request,
        "core/prices_history.html",
        {"rows": qs[:1000], "symbol": symbol, "date_from": date_from, "date_to": date_to},
    )


# ---------------------------------------------------------------------------
# Opportunities (recommendations) + "DB" screen


@login_required
@require_http_methods(["GET", "POST"])
def opportunities(request):
    """Inbox de oportunidades (recomendaciones) — muestra solo OPEN."""

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()

        # Generar oportunidades a partir del motor (si hay portafolio)
        if action == "generate":
            p = _get_or_create_default_portfolio(request.user)

            # Diagnóstico previo (ayuda muchísimo cuando da 0)
            diag = diagnose_generation(p)
            logger.info(
                "Reco generate requested | user=%s portfolio_id=%s tx=%s holdings=%s prices=%s missing=%s open=%s",
                getattr(request.user, "username", ""),
                diag.get("portfolio_id"),
                diag.get("tx_count"),
                diag.get("holdings_count"),
                diag.get("prices_available"),
                diag.get("prices_missing"),
                diag.get("open_opportunities"),
            )

            res = generate_recommendations(p)
            # Compatibilidad: puede ser int (legacy) o un objeto con created/reason
            created = int(getattr(res, "created", res))
            reason = str(getattr(res, "reason", "") or "")

            _audit(
                request,
                "reco_generate",
                {"portfolio_id": p.id, "created": created, "reason": reason, "diag": diag},
            )

            # Guardamos diagnóstico para UI (se muestra en la pantalla de oportunidades)
            request.session["last_generate_diag"] = {
                "created": created,
                "reason": reason,
                "diag": diag,
                "ts": timezone.now().isoformat(),
            }

            if created > 0:
                messages.success(request, f"Oportunidades generadas: {created}.")
            else:
                # Si la app está en modo viejo y reason queda vacío, avisar para diagnóstico.
                if not reason:
                    reason = (
                        "(Diagnóstico) El motor de generación parece estar en modo básico/antiguo. "
                        "Asegurate de haber desplegado la Rev 11 (mirá el título arriba)."
                    )

                # Si ya hay OPEN, probablemente evita duplicados
                if diag.get("open_opportunities"):
                    reason += f" Ya tenés {diag.get('open_opportunities')} oportunidad(es) OPEN. Revisá 'Base de datos'."

                # Si no hay OPEN y no crea nada, probablemente hubo errores en DB/migraciones
                if not diag.get("open_opportunities"):
                    reason += " Si esto se repite, mirá los logs en Render: debería aparecer una línea 'Reco create IntegrityError' o 'Reco create Exception'."

                messages.warning(request, f"Oportunidades generadas: 0. {reason}")
            return redirect("core:opportunities")

        # Generar DEMO (sin depender de holdings)
        if action in ("demo", "seed_demo"):
            p = _get_or_create_default_portfolio(request.user)
            already = Recommendation.objects.filter(portfolio=p, status=Recommendation.Status.OPEN).exists()
            if already:
                messages.info(request, "Ya existen oportunidades abiertas. No se generó DEMO.")
                return redirect("core:opportunities")

            demo_defs = [
                ("FND-ALPHA", Recommendation.Severity.HIGH, "Rotación defensiva (demo)",
                 "Sugerencia DEMO: reforzar instrumentos defensivos para reducir volatilidad.",
                 {"fuente": "demo", "nota": "Ejemplo para probar badges y estados"}),
                ("FND-BETA", Recommendation.Severity.MED, "Oportunidad táctica (demo)",
                 "Sugerencia DEMO: diversificar sectores y ajustar exposición de riesgo en forma gradual.",
                 {"fuente": "demo", "nota": "Ejemplo para probar Aceptar/Ignorar"}),
                ("FND-GAMMA", Recommendation.Severity.LOW, "Rebalanceo sugerido (demo)",
                 "Sugerencia DEMO: rebalanceo de posiciones para alinear con el perfil de riesgo.",
                 {"fuente": "demo", "nota": "Ejemplo para probar pantalla Base de datos"}),
            ]

            created = 0
            for code, sev, title, rationale, evidence in demo_defs:
                _, ok = _create_reco_safe(
                    portfolio=p,
                    code=f"{code}-{p.id}",
                    severity=sev,
                    title=title,
                    rationale=rationale,
                    evidence=evidence,
                    status=Recommendation.Status.OPEN,
                )
                if ok:
                    created += 1

            _audit(request, "reco_demo_seed", {"portfolio_id": p.id, "created": created})
            messages.success(request, f"Se generaron {created} oportunidades DEMO.")
            return redirect("core:opportunities")

        # Evaluar con IA (lote)
        if action in ("ai_eval", "ai_evaluate"):
            p = _get_or_create_default_portfolio(request.user)
            qs = Recommendation.objects.filter(portfolio=p, status=Recommendation.Status.OPEN).order_by("-created_at")
            limit = max(1, int(getattr(settings, "AI_MAX_EVAL_PER_CLICK", 5)))
            evaluated = 0
            snap = _portfolio_snapshot(p)
            psnap = _price_snapshot_for_portfolio(p)
            for rec2 in qs[:limit]:
                ev = evaluate_recommendation(rec2, snap, psnap)
                rec2.ai_score = ev.score
                rec2.ai_confidence = ev.confidence
                rec2.ai_action = ev.action
                rec2.ai_summary = ev.summary
                rec2.ai_reasons = ev.reasons
                rec2.ai_evaluated_at = timezone.now()
                rec2.save(update_fields=["ai_score","ai_confidence","ai_action","ai_summary","ai_reasons","ai_evaluated_at","updated_at"])
                evaluated += 1
            _audit(request, "ai_eval_batch", {"portfolio_id": p.id, "evaluated": evaluated})
            messages.success(request, f"IA evaluó {evaluated} oportunidades (máx {limit}).")
            return redirect("core:opportunities")

        # Acciones sobre una oportunidad
        rid = request.POST.get("rid") or request.POST.get("rec_id")
        if rid:
            rec = get_object_or_404(Recommendation, id=rid, portfolio__owner=request.user)
            note = (request.POST.get("note") or "").strip()

            if action == "accept":
                if getattr(settings, "AI_GOVERNANCE_REQUIRED", True) and getattr(settings, "OPENAI_API_KEY", ""):
                    min_score = int(getattr(settings, "AI_MIN_SCORE", 70))
                    allow_override = bool(getattr(settings, "AI_ALLOW_MANUAL_OVERRIDE", False))
                    action_ok = (rec.ai_action or "").upper() == "ENTER"
                    score_ok = (rec.ai_score is not None) and int(rec.ai_score) >= min_score
                    if (not action_ok or not score_ok) and not allow_override:
                        messages.error(
                            request,
                            f"Bloqueado por IA: se requiere acción ENTER y score ≥ {min_score}. Usá \"Evaluar con IA\" y reintentá."
                        )
                        return redirect("core:opportunities")

                rec.status = Recommendation.Status.ACCEPTED
                if note:
                    rec.decision_note = note[:240]
                rec.save(update_fields=["status", "decision_note", "updated_at"])
                _audit(request, "reco_accept", {"rec_id": rec.id})
                messages.success(request, "Oportunidad marcada como ACEPTADA.")

            elif action in ("ignore", "dismiss"):
                rec.status = Recommendation.Status.IGNORED
                if note:
                    rec.decision_note = note[:240]
                rec.save(update_fields=["status", "decision_note", "updated_at"])
                _audit(request, "reco_ignore", {"rec_id": rec.id})
                messages.success(request, "Oportunidad marcada como IGNORADA.")

        return redirect("core:opportunities")

    recs = (
        Recommendation.objects.select_related("portfolio")
        .filter(portfolio__owner=request.user, status=Recommendation.Status.OPEN)
        .order_by("-created_at")
    )

    last_generate_diag = request.session.pop("last_generate_diag", None)

    return render(request, "core/opportunities.html", {
        "recs": recs,
        "open_count": recs.count(),
        "last_generate_diag": last_generate_diag,
        "openai_configured": bool(getattr(settings, "OPENAI_API_KEY", "")),
        "ai_governance": bool(getattr(settings, "AI_GOVERNANCE_REQUIRED", True)),
        "ai_min_score": int(getattr(settings, "AI_MIN_SCORE", 70)),
    })


@login_required
@require_http_methods(["GET", "POST"])
def opportunities_db(request):
    """Pantalla Base de datos: ver TODAS las oportunidades guardadas y operar por fecha/estado."""

    qs = (
        Recommendation.objects.select_related("portfolio")
        .filter(portfolio__owner=request.user)
        .order_by("-created_at")
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        rid = request.POST.get("rid")

        # IA (batch)
        if action in ("ai_eval", "ai_evaluate"):
            p = _get_or_create_default_portfolio(request.user)
            qs_open = Recommendation.objects.filter(portfolio=p, status=Recommendation.Status.OPEN).order_by("-created_at")
            limit = max(1, int(getattr(settings, "AI_MAX_EVAL_PER_CLICK", 5)))
            snap = _portfolio_snapshot(p)
            psnap = _price_snapshot_for_portfolio(p)
            evaluated = 0
            for rec2 in qs_open[:limit]:
                ev = evaluate_recommendation(rec2, snap, psnap)
                rec2.ai_score = ev.score
                rec2.ai_confidence = ev.confidence
                rec2.ai_action = ev.action
                rec2.ai_summary = ev.summary
                rec2.ai_reasons = ev.reasons
                rec2.ai_evaluated_at = timezone.now()
                rec2.save(update_fields=["ai_score","ai_confidence","ai_action","ai_summary","ai_reasons","ai_evaluated_at","updated_at"])
                evaluated += 1
            messages.success(request, f"IA evaluó {evaluated} oportunidades OPEN.")
            return redirect("core:opportunities_db")

        # IA (una)
        if action in ("ai_one", "ai_eval_one") and rid:
            rec = get_object_or_404(Recommendation, id=rid, portfolio__owner=request.user)
            snap = _portfolio_snapshot(rec.portfolio)
            psnap = _price_snapshot_for_portfolio(rec.portfolio)
            ev = evaluate_recommendation(rec, snap, psnap)
            rec.ai_score = ev.score
            rec.ai_confidence = ev.confidence
            rec.ai_action = ev.action
            rec.ai_summary = ev.summary
            rec.ai_reasons = ev.reasons
            rec.ai_evaluated_at = timezone.now()
            rec.save(update_fields=["ai_score","ai_confidence","ai_action","ai_summary","ai_reasons","ai_evaluated_at","updated_at"])
            messages.success(request, "IA evaluó la oportunidad seleccionada.")
            return redirect("core:opportunities_db")

        if rid and action in ("send", "accept", "ignore", "reopen"):
            rec = get_object_or_404(Recommendation, id=rid, portfolio__owner=request.user)
            note = (request.POST.get("note") or "").strip()

            if action in ("send", "accept"):
                if getattr(settings, "AI_GOVERNANCE_REQUIRED", True) and getattr(settings, "OPENAI_API_KEY", ""):
                    min_score = int(getattr(settings, "AI_MIN_SCORE", 70))
                    allow_override = bool(getattr(settings, "AI_ALLOW_MANUAL_OVERRIDE", False))
                    action_ok = (rec.ai_action or "").upper() == "ENTER"
                    score_ok = (rec.ai_score is not None) and int(rec.ai_score) >= min_score
                    if (not action_ok or not score_ok) and not allow_override:
                        messages.error(request, f"Bloqueado por IA: se requiere ENTER y score ≥ {min_score}.")
                        return redirect("core:opportunities_db")

                rec.status = Recommendation.Status.ACCEPTED
                if note:
                    rec.decision_note = note[:240]
                rec.save(update_fields=["status","decision_note","updated_at"])
                messages.success(request, "Enviada al portafolio (ACEPTADA).")

            elif action == "ignore":
                rec.status = Recommendation.Status.IGNORED
                if note:
                    rec.decision_note = note[:240]
                rec.save(update_fields=["status","decision_note","updated_at"])
                messages.success(request, "Marcada como IGNORADA.")

            elif action == "reopen":
                rec.status = Recommendation.Status.OPEN
                if note:
                    rec.decision_note = note[:240]
                rec.save(update_fields=["status","decision_note","updated_at"])
                messages.success(request, "Reabierta (OPEN).")

        return redirect("core:opportunities_db")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    date_from = (request.GET.get("from") or "").strip()
    date_to = (request.GET.get("to") or "").strip()

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(code__icontains=q))

    valid_status = set()
    try:
        valid_status = {Recommendation.Status.OPEN, Recommendation.Status.ACCEPTED, Recommendation.Status.IGNORED}
    except Exception:
        valid_status = {"OPEN", "ACCEPTED", "IGNORED"}

    if status in valid_status:
        qs = qs.filter(status=status)

    def _parse(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None

    df = _parse(date_from)
    dt = _parse(date_to)
    if df:
        qs = qs.filter(created_at__date__gte=df)
    if dt:
        qs = qs.filter(created_at__date__lte=dt)

    return render(
        request,
        "core/opportunities_db.html",
        {"items": qs[:500], "q": q, "status": status, "date_from": date_from, "date_to": date_to, "openai_configured": bool(getattr(settings, "OPENAI_API_KEY", "")), "ai_governance": bool(getattr(settings, "AI_GOVERNANCE_REQUIRED", True)), "ai_min_score": int(getattr(settings, "AI_MIN_SCORE", 70))},
    )

# ---------------------------------------------------------------------------
# Alerts (email)


@login_required
@require_http_methods(["GET"])
def alerts_inbox(request):
    """Endpoint legacy /alerts/ -> redirige a /opportunities/."""
    return redirect("core:opportunities")


@staff_member_required
@require_http_methods(["GET"])
def test_alerts(request):
    """Envía un email de prueba al staff, si el sistema de correo está configurado."""
    try:
        send_daily_alert(dry_run=True)
        messages.success(request, "Test OK: se ejecutó el envío (modo dry_run).")
    except Exception as e:
        messages.error(request, f"Error en test_alerts: {e}")
    return redirect("core:dashboard")


@staff_member_required
@require_http_methods(["GET"])
def run_alerts(request):
    """Corre el comando de envío de alertas (real)."""
    try:
        send_daily_alert(dry_run=False)
        messages.success(request, "Alertas ejecutadas.")
    except Exception as e:
        messages.error(request, f"Error en run_alerts: {e}")
    return redirect("core:dashboard")


# ---------------------------------------------------------------------------
# Manual (in-app) + PDF


def _manual_sections():
    # Manual operativo (Rev 11) — pensado para uso real, con procedimientos por botón.
    # Formato: secciones + bullets (sirve para HTML y PDF).
    return [
        ("1) Qué es InvPanel PRO (y qué NO es)", [
            "InvPanel PRO es un panel web personal para gestionar un portafolio y registrar decisiones sobre ‘Oportunidades’ (recomendaciones).",
            "Se puede usar desde PC o desde el celular como ‘app’ (PWA: se instala como ícono).",
            "MUY IMPORTANTE: el sistema NO compra ni vende en ningún broker. No mueve dinero. No toca tus cuentas. Solo registra información y estados.",
            "Cómo pensarlo: tablero + bitácora (historial) para ordenar y justificar decisiones.",
        ]),

        ("2) Cómo entrar y cómo ubicarte (primer uso)", [
            "Paso 1 — Entrar: abrí la URL del sistema y logueate con tu usuario y contraseña.",
            "Paso 2 — Menú superior: Panel · Portafolios · Activos · Oportunidades · Análisis (PRO) · Manual.",
            "Paso 3 — Versión: en el título superior figura ‘Rev 11’. Si ves otro número, no estás en la versión esperada.",
            "Paso 4 — Mensajes: después de tocar un botón, arriba aparece una caja: verde = OK, roja = error, azul = informativa, naranja = advertencia.",
            "Paso 5 — Numerito rojo: si aparece en ‘Oportunidades’ (menú), significa que hay oportunidades OPEN (pendientes).",
        ]),

        ("3) Primera prueba guiada (sin datos reales)", [
            "Objetivo: ver tarjetas, botones, numeritos y flujo completo sin depender de tu portafolio.",
            "Paso 1: entrá a Oportunidades.",
            "Paso 2: tocá ‘Generar DEMO’.",
            "Qué deberías ver: mensaje verde + 3 tarjetas + OPEN=3.",
            "Paso 3: en una tarjeta, opcionalmente escribí una nota y tocá ‘Aceptar’.",
            "Qué deberías ver: mensaje verde, la tarjeta desaparece (deja de ser OPEN) y el numerito rojo baja.",
            "Paso 4: en otra tarjeta tocá ‘Ignorar’.",
            "Paso 5: tocá ‘Base de datos’ para ver el historial y verificar estados ACCEPTED / IGNORED.",
        ]),

        ("4) Pantalla Oportunidades — qué estás viendo", [
            "Esta pantalla es tu ‘inbox’. Solo muestra oportunidades en estado OPEN.",
            "‘Abiertas (OPEN)’: cuántas oportunidades te quedan pendientes.",
            "Bloque IA: si IA está configurada, puede completar score/resumen. Si NO está configurada, el sistema funciona igual.",
        ]),

        ("5) Botones de Oportunidades — procedimiento paso a paso", [
            "Botón ‘Generar DEMO’ (aprender):",
            "  1) Tocá ‘Generar DEMO’.",
            "  2) Esperá que la página recargue sola.",
            "  3) Confirmá: mensaje verde + tarjetas demo + OPEN aumenta.",
            "  4) Si no genera DEMO: suele ser porque ya tenías oportunidades OPEN (no duplica).",
            "Botón ‘Generar’ (motor real):",
            "  1) Tocá ‘Generar’.",
            "  2) Esperá recarga y mirá el mensaje.",
            "  3) Si genera >0: aparecen nuevas tarjetas OPEN.",
            "  4) Si genera 0: el sistema muestra una explicación. Causas típicas: portafolio vacío, holdings en 0, faltan precios, precios viejos, o ya existían oportunidades OPEN iguales (evita duplicados).",
            "Botón ‘Diagnóstico’ (cuando algo no cierra):",
            "  1) Tocá ‘Diagnóstico’.",
            "  2) Se abre una ventana con datos (tx_count, holdings_count, prices_missing, open_opportunities).",
            "  3) Interpretación rápida: tx_count=0 → no hay movimientos; prices_missing>0 → faltan precios; open_opportunities>0 → ya hay oportunidades OPEN y por eso ‘Generar’ suele devolver 0.",
            "Botón ‘Evaluar con IA’ (opcional):",
            "  1) Solo sirve si IA figura como ‘configurada’.",
            "  2) Tocá ‘Evaluar con IA’ → recarga → se completa el bloque IA en cada tarjeta.",
            "Botón ‘Base de datos’ (historial):",
            "  1) Entrá para ver todo (OPEN + cerradas).",
            "  2) Usá filtros por estado y buscador por texto.",
        ]),

        ("6) Botones dentro de una tarjeta — qué tocar y qué esperar", [
            "‘Ver evidencia’: abre los datos que justifican la oportunidad.",
            "‘Nota (opcional)’: escribí tu criterio. Queda guardado en el historial.",
            "‘Aceptar’: pasa a ACCEPTED. Desaparece de OPEN. Baja el numerito rojo.",
            "‘Ignorar’: pasa a IGNORED. Desaparece de OPEN. Baja el numerito rojo.",
        ]),

        ("7) Cómo funciona el motor ‘Generar’ (reglas simples)", [
            "El motor ‘Generar’ usa reglas simples y auditables (rápidas, no ‘finanzas complejas’).",
            "Reglas típicas: concentración (una posición muy grande), exposición por moneda, faltan precios históricos, precios desactualizados, muchas posiciones pequeñas.",
            "Si apretás ‘Generar’ varias veces: no debería duplicar oportunidades iguales; por eso a veces devuelve 0.",
            "En Rev 11, cuando ‘Generar’ da 0, el sistema deja un diagnóstico y también escribe líneas útiles en los logs de Render para ver la causa real (por ejemplo, si falló por un tema de base de datos/migraciones).",
        ]),

        ("8) Portafolios — dejar el portafolio listo", [
            "Paso 1: Portafolios → Crear nuevo → nombre → Guardar.",
            "Paso 2: Cargar transacciones BUY/SELL (movimientos).",
            "Paso 3 (recomendado): Cargar precios históricos (CSV) para calcular porcentajes y concentración.",
        ]),

        ("9) Activos — catálogo de símbolos", [
            "Activos es tu catálogo de instrumentos/símbolos (para portafolio y para cargar CSV).",
            "Si al cargar precios el combo Asset está vacío: creá al menos un Activo.",
            "Paso a paso: Activos → Agregar → símbolo/nombre/tipo/moneda → Guardar.",
        ]),

        ("10) Análisis (PRO) y carga de precios (CSV)", [
            "Análisis (PRO) calcula métricas usando históricos de precios que cargás por CSV.",
            "Caso simple (1 símbolo): Análisis (PRO) → Cargar precios → elegir Asset → subir CSV date,close → procesar.",
            "Caso multi-símbolo: CSV date,symbol,close.",
        ]),

        ("11) Ícono tipo app (PWA) y numeritos rojos en el ícono", [
            "El numerito rojo dentro de la app (menú Oportunidades) es el indicador confiable.",
            "El numerito en el ÍCONO de la app depende del sistema/navegador (API de ‘badges’). Suele funcionar mejor en Android/Chrome y en escritorio con Chromium. En iPhone (Safari/PWA) puede NO aparecer aunque todo esté bien.",
            "Si no ves el numerito en el ícono: no significa fallo. Usá el contador de ‘Oportunidades’ en el menú y/o el badge dentro de la interfaz.",
        ]),

        ("12) Problemas comunes (Troubleshooting)", [
            "Pantalla en blanco: suele ser cache del Service Worker. Solución: borrar datos del sitio (cache/storage) y recargar; o reinstalar la PWA.",
            "‘Error cliente’ al tocar botones: suele ser CSRF / dominios. Revisá ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS en Render.",
            "‘Generar’ devuelve 0: mirá el mensaje. Luego tocá ‘Diagnóstico’ para ver números concretos (tx_count, holdings_count, prices_missing, open_opportunities).",
            "Si sigue sin cerrar: revisá logs en Render. En Rev 11 deberían aparecer mensajes ‘Reco create IntegrityError’ o ‘Reco create Exception’ si algo impide crear oportunidades.",
            "Render ‘No open HTTP ports’: health check en /healthz/.",
        ]),

        ("13) Checklist de Render (variables recomendadas)", [
            "ALLOWED_HOSTS: invpanel-pro.onrender.com (y tu dominio propio si lo tenés).",
            "CSRF_TRUSTED_ORIGINS: https://invpanel-pro.onrender.com (y https://tudominio si corresponde).",
            "OPENAI_API_KEY (opcional): solo si querés IA.",
            "SECRET_KEY: obligatorio.",
            "ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_EMAIL: para el usuario admin inicial.",
        ]),
    ]


def _manual_content() -> str:
    # Render simple (markdown-like) para HTML
    out = []
    for title, bullets in _manual_sections():
        out.append(f"## {title}")
        for b in bullets:
            out.append(f"- {b}")
        out.append("")
    return "\n".join(out)

@login_required
@require_http_methods(["GET"])
def manual(request):
    return render(request, "core/manual.html", {"sections": _manual_sections()})


@login_required
@require_http_methods(["GET"])
def manual_pdf(request):
    """Descarga del manual en PDF."""

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Manual InvPanel PRO",
        author="InvPanel PRO",
    )

    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    body.spaceBefore = 6
    body.spaceAfter = 6

    story = [
        Paragraph("Manual de Operación — InvPanel PRO (Rev 11)", h1),
        Paragraph(f"Generado: {timezone.now().strftime('%Y-%m-%d %H:%M')}", body),
        Spacer(1, 12),
    ]

    for title, bullets in _manual_sections():
        story.append(Paragraph(title, h2))
        items = [ListItem(Paragraph(x, body)) for x in bullets]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=14))
        story.append(Spacer(1, 12))

    story.append(Paragraph("Notas", h2))
    story.append(Paragraph("Este documento es un instructivo operativo. No reemplaza asesoramiento profesional.", body))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="Manual_InvPanel_PRO.pdf"'
    return resp


# ---------------------------------------------------------------------------
# Health check


@require_http_methods(["GET"])
def healthz(request):
    return JsonResponse({"ok": True, "ts": timezone.now().isoformat()})


# ---------------------------------------------------------------------------
# API (Badges)


@login_required
@require_http_methods(["GET"])
def badges_api(request):
    """Devuelve contadores para refrescar badges sin recargar la página."""
    try:
        from .models import Recommendation
        try:
            open_status = Recommendation.Status.OPEN
        except Exception:
            open_status = "OPEN"
        open_count = int(Recommendation.objects.filter(portfolio__owner=request.user, status=open_status).count())
    except Exception:
        open_count = 0
    return JsonResponse({"ok": True, "opps_open": open_count, "app_badge": open_count})


@login_required
@require_http_methods(["GET"])
def reco_diag_api(request):
    """Diagnóstico rápido del botón 'Generar' en Oportunidades."""
    portfolio, _ = _get_or_create_default_portfolio(request.user)
    diag = diagnose_generation(portfolio)
    diag["ok"] = True
    return JsonResponse(diag)