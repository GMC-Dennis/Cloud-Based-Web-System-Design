"""Train the alternative-credit-scoring model on synthetic merchant data.

There's no real default history yet (this is a pilot), so this generates a
plausible synthetic dataset whose feature -> default relationship matches
the "Expected Signal" column in TDD §5.1, and trains a real, calibrated
classifier against it. Swap in real defaults and re-run once they exist --
nothing downstream needs to change except the training data and MODEL_VERSION.

Usage: python -m app.modules.scoring.ml.train_model
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from app.core.config import get_settings

FEATURE_NAMES = ["sales_velocity", "receivables_days", "chama_punctuality", "margin_stability"]
N_SAMPLES = 8000
RANDOM_STATE = 42


def generate_synthetic_dataset(n: int = N_SAMPLES, seed: int = RANDOM_STATE) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)

    sales_velocity = rng.gamma(shape=2.0, scale=1500.0, size=n)  # KES/day
    receivables_days = np.clip(rng.exponential(scale=10.0, size=n), 0, 90)
    chama_punctuality = np.clip(rng.beta(5, 2, size=n) * 100, 0, 100)
    margin_stability = np.clip(rng.normal(0.25, 0.08, size=n), 0, 1)

    df = pd.DataFrame(
        {
            "sales_velocity": sales_velocity,
            "receivables_days": receivables_days,
            "chama_punctuality": chama_punctuality,
            "margin_stability": margin_stability,
        }
    )

    # Logistic combination encoding each feature's expected signal from §5.1:
    # higher velocity/punctuality/margin -> lower default risk; higher
    # receivables days -> higher default risk. Coefficients are illustrative,
    # not calibrated against real outcomes -- see the linear PD->score
    # mapping note in scoring_engine.py for the same caveat downstream.
    logit = (
        -1.5
        - 0.0004 * sales_velocity
        + 0.04 * receivables_days
        - 0.02 * chama_punctuality
        - 3.5 * margin_stability
        + rng.normal(0, 0.5, size=n)
    )
    p_default = 1 / (1 + np.exp(-logit))
    y = rng.binomial(1, p_default)

    return df, y


def main() -> None:
    settings = get_settings()
    output_dir = Path(__file__).resolve().parent / "model_artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{settings.model_version}.joblib"

    X, y = generate_synthetic_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y)

    base_estimator = RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=20, random_state=RANDOM_STATE)
    # Uncalibrated predict_proba from a raw RandomForest isn't a defensible
    # probability estimate -- wrap it so PD really means PD (see TDD §5.2).
    calibrated = CalibratedClassifierCV(base_estimator, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)

    auc = roc_auc_score(y_test, calibrated.predict_proba(X_test)[:, 1])
    print(f"Synthetic holdout AUC: {auc:.3f} (sanity check only -- not a real backtest)")

    background = X_train.sample(n=min(100, len(X_train)), random_state=RANDOM_STATE).reset_index(drop=True)

    joblib.dump({"model": calibrated, "feature_names": FEATURE_NAMES, "background": background}, output_path)
    print(f"Wrote model artifact to {output_path}")


if __name__ == "__main__":
    sys.exit(main() or 0)
