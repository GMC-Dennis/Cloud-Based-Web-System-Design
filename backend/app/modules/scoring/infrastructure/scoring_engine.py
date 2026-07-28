import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple

import joblib
import pandas as pd
import shap
from pydantic import BaseModel, Field
from redis.asyncio import Redis

CACHE_TTL_SECONDS = 60 * 60 * 6  # fallback TTL; the real invalidation path is
                                  # app.core.cache.invalidate_score_cache, called
                                  # by ledger/chama write use-cases on every new event.

# Bucket widths for cache-key purposes only -- hashing raw floats would mean
# the cache key changes on almost every request (sales_velocity to the cent
# essentially never repeats), so bucketing collapses "close enough" feature
# vectors onto the same key. Tune against how much score staleness is
# acceptable for a cache hit.
BUCKET_WIDTHS = {
    "sales_velocity": 50.0,       # nearest 50 KES/day
    "receivables_days": 1.0,      # nearest day
    "chama_punctuality": 5.0,     # nearest 5 percentage points
    "margin_stability": 0.02,     # nearest 2 percentage points
}


class MerchantFeatures(BaseModel):
    """Strict schema for scoring inputs. Prevents a missing/mistyped feature name
    from silently producing a NaN instead of an error, and is the single source of
    truth for what the model expects -- kept in lockstep with FEATURE_NAMES in
    train_model.py, not just with whatever the DB happens to return."""

    sales_velocity: float = Field(ge=0)
    receivables_days: float = Field(ge=0)
    chama_punctuality: float = Field(ge=0, le=100)
    margin_stability: float = Field(ge=0, le=1)

    def bucketed(self) -> Dict[str, float]:
        return {name: round(value / BUCKET_WIDTHS[name]) * BUCKET_WIDTHS[name] for name, value in self.model_dump().items()}


class AlternativeCreditScorer:
    def __init__(self, model_path: str | Path, model_version: str, redis_client: Redis | None = None):
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names: list[str] = artifact["feature_names"]
        self.model_version = model_version
        self.redis = redis_client

        # shap.TreeExplainer does NOT support a CalibratedClassifierCV wrapper
        # (it needs direct access to raw tree structure, and CalibratedClassifierCV
        # internally holds several per-fold calibrated copies of the base
        # estimator, not one tree to introspect). Using the model-agnostic
        # shap.Explainer over predict_proba works for any sklearn estimator,
        # calibrated or not, at the cost of being slower than TreeExplainer --
        # acceptable here since scoring is cached and not on a hot path.
        background = artifact["background"]
        self.explainer = shap.Explainer(self.model.predict_proba, background)

    async def evaluate_merchant(self, user_id: str, features: MerchantFeatures) -> Tuple[int, str, Dict[str, float]]:
        bucketed = features.bucketed()
        cache_key = (
            f"score:{user_id}:{self.model_version}:"
            f"{hashlib.sha256(json.dumps(bucketed, sort_keys=True).encode()).hexdigest()[:16]}"
        )
        if self.redis is not None:
            cached = await self.redis.get(cache_key)
            if cached:
                credit_score, risk_tier, shap_dict = json.loads(cached)
                return credit_score, risk_tier, shap_dict

        df = pd.DataFrame([features.model_dump()])[self.feature_names]  # score on the true, unbucketed values

        pd_score = float(self.model.predict_proba(df)[0][1])

        # NOTE: linear PD->score mapping is a placeholder suitable for a pilot
        # with no real default history yet. Replace with a PDO (points-to-
        # double-odds) log-odds scaling once real defaults exist (TDD §5.2).
        credit_score = int(850 - (pd_score * 550))
        credit_score = max(300, min(850, credit_score))

        if credit_score >= 720:
            risk_tier = "LOW"
        elif credit_score >= 600:
            risk_tier = "MEDIUM"
        else:
            risk_tier = "HIGH"

        explanation = self.explainer(df)
        values = explanation.values[0]
        if values.ndim == 2:
            # predict_proba has 2 output columns (class 0, class 1); keep the
            # contribution to the "default" (class 1) probability.
            values = values[:, 1]
        shap_dict = {name: float(v) for name, v in zip(self.feature_names, values)}

        result = (credit_score, risk_tier, shap_dict)
        if self.redis is not None:
            await self.redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
        return result
