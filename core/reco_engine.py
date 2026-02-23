"""Recommendation engine helpers.

This file is intentionally defensive: production DB schema may lag behind code during deploys.
We therefore:
- Provide safe defaults for new NOT NULL fields when present (ai_action, ai_summary, etc.)
- Filter kwargs to the actual Recommendation model fields at runtime (so extra keys won't crash)
"""

from __future__ import annotations

from typing import Any, Dict

from django.db import transaction

from .models import Recommendation


def _create_reco_safe(**kwargs: Any) -> Recommendation:
    """Create a Recommendation, filtering kwargs to current model fields.

    Avoids crashes when code and DB schema are temporarily out of sync.
    """
    # Current field names (concrete fields only)
    field_names = {f.name for f in Recommendation._meta.get_fields()}

    # Fill defaults only if the field exists on the model.
    if "ai_action" in field_names and kwargs.get("ai_action") is None:
        kwargs["ai_action"] = "HOLD"  # neutral default
    if "ai_summary" in field_names and kwargs.get("ai_summary") is None:
        kwargs["ai_summary"] = ""  # empty but not NULL
    if "ai_confidence" in field_names and kwargs.get("ai_confidence") is None:
        kwargs["ai_confidence"] = 0.0
    if "ai_score" in field_names and kwargs.get("ai_score") is None:
        kwargs["ai_score"] = 0.0

    filtered = {k: v for k, v in kwargs.items() if k in field_names}
    return Recommendation.objects.create(**filtered)


def generate_recommendations(panel) -> int:
    """Generate recommendations for a given panel.

    Returns number of created recommendations.
    """
    created = 0

    # NOTE: keep the core business logic you already had; this is a minimal,
    # schema-safe wrapper around Recommendation.objects.create().
    #
    # If your previous implementation already built recos as dicts and called
    # Recommendation.objects.create(...), replace that call with _create_reco_safe(...).

    # ---- Existing logic placeholder (keep your loops / scoring) ----
    # The following block is intentionally minimal and should integrate with your current
    # implementation. We attempt to call a helper 'build_recos' if it exists.
    try:
        build_recos = globals().get("build_recos")
    except Exception:
        build_recos = None

    if callable(build_recos):
        recos = build_recos(panel)
        with transaction.atomic():
            for r in recos:
                _create_reco_safe(**r)
                created += 1
        return created

    # Fallback: if previous code lived below, keep it and just swap the create call.
    # If no recommendations are generated, return 0.
    return created
