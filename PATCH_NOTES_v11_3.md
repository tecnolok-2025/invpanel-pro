InvPanel-Pro v11.3 patch

Fix:
- Prevent Render 500 on /opportunities/ caused by NOT NULL constraints on core_recommendation.ai_action / ai_summary.
- Added safe defaults in Recommendation.objects.create() calls in core/reco_engine.py:
    ai_action="HOLD"
    ai_summary=""

Deploy:
- Commit & push this patch, then trigger a Render deploy (Clear build cache optional).
