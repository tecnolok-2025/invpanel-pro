from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

@dataclass
class AIEval:
    score: int
    confidence: int
    action: str
    summary: str
    reasons: Dict[str, Any]

def _client() -> Optional["OpenAI"]:
    if not settings.OPENAI_API_KEY:
        return None
    if OpenAI is None:
        return None
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def evaluate_recommendation(rec, portfolio_snapshot: Dict[str, Any], price_snapshot: Dict[str, Any]) -> AIEval:
    """Evalúa una Recommendation usando IA (OpenAI API).

    Importante:
    - No garantiza resultados.
    - Devuelve una estructura estable para gobernanza del sistema.
    """
    client = _client()
    if client is None:
        return AIEval(
            score=0,
            confidence=0,
            action="NEEDS_DATA",
            summary="IA no configurada (falta OPENAI_API_KEY).",
            reasons={"error": "missing_openai_api_key"},
        )

    schema = {
        "name": "invpanel_ai_eval",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                "action": {"type": "string", "enum": ["ENTER", "EXIT", "HOLD", "IGNORE", "NEEDS_DATA"]},
                "summary": {"type": "string"},
                "reasons": {"type": "object"},
            },
            "required": ["score", "confidence", "action", "summary", "reasons"],
        },
        "strict": True,
    }

    system = (
        "Sos un analista cuantitativo y de riesgo. "
        "Evaluás una oportunidad de inversión para un usuario minorista. "
        "No prometas ganancias. Priorizá protección de capital. "
        "Si faltan datos (precio, histórico, posición), devolvé NEEDS_DATA."
    )

    user = {
        "recommendation": {
            "code": rec.code,
            "severity": rec.severity,
            "title": rec.title,
            "rationale": rec.rationale,
            "evidence": rec.evidence,
            "status": rec.status,
        },
        "portfolio": portfolio_snapshot,
        "prices": price_snapshot,
        "constraints": {
            "currency": getattr(rec.portfolio, "base_currency", "ARS"),
            "horizon": "short_to_mid",
            "risk_policy": "conservative_by_default",
        },
    }

    resp = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        response_format={"type": "json_schema", "json_schema": schema},
    )

    raw = resp.output_text or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        # Fallback: si el SDK devuelve algo distinto
        data = {}

    return AIEval(
        score=int(data.get("score", 0)),
        confidence=int(data.get("confidence", 0)),
        action=str(data.get("action", "NEEDS_DATA")),
        summary=str(data.get("summary", ""))[:800],
        reasons=data.get("reasons", {}) if isinstance(data.get("reasons", {}), dict) else {"raw": data.get("reasons")},
    )
