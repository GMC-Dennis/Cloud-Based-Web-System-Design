import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import get_redis
from app.core.config import get_settings
from app.modules.chama.presentation.router import router as chama_router
from app.modules.identity.presentation.admin_router import router as admin_router
from app.modules.identity.presentation.router import router as identity_router
from app.modules.ledger.presentation.router import router as ledger_router
from app.modules.scoring.infrastructure.scoring_engine import AlternativeCreditScorer
from app.modules.scoring.presentation.router import router as scoring_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    model_path = Path(__file__).resolve().parent / "modules" / "scoring" / "ml" / "model_artifacts" / f"{settings.model_version}.joblib"
    if model_path.exists():
        # Loaded once at startup, not per-request -- the joblib artifact and its
        # SHAP explainer are expensive to construct and safe to share/reuse.
        app.state.scoring_engine = AlternativeCreditScorer(model_path, settings.model_version, get_redis())
    else:
        logging.warning("No trained model found at %s; run `python -m app.modules.scoring.ml.train_model` first.", model_path)
        app.state.scoring_engine = None
    yield


app = FastAPI(title="DukaCred API", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(identity_router)
app.include_router(admin_router)
app.include_router(ledger_router)
app.include_router(chama_router)
app.include_router(scoring_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
