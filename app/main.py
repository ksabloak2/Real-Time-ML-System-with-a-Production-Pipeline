"""
FastAPI application — entry point.

Endpoints:
  POST /predict          — single text prediction
  POST /predict/batch    — batch prediction
  GET  /predictions      — recent stored predictions
  GET  /drift            — confidence drift stats
  GET  /metrics          — request-level metrics
  GET  /health           — liveness check
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.model import predict, predict_batch
from app.database import init_db, insert_prediction, get_recent_predictions, get_drift_stats
from app.monitor import MetricsMiddleware, get_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

REDDIT_ENABLED = all(
    os.getenv(k) for k in ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if REDDIT_ENABLED:
        from app.ingestion import start_worker
        start_worker()
        logger.info("Reddit ingestion worker started")
    else:
        logger.info("Reddit credentials not set — ingestion worker disabled")
    yield
    if REDDIT_ENABLED:
        from app.ingestion import stop_worker
        stop_worker()


app = FastAPI(
    title="Real-Time Sentiment API",
    description="Live sentiment analysis with Reddit ingestion, monitoring, and drift tracking.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(MetricsMiddleware)


# ── Request / Response Models ──────────────────────────────────────────────────

class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, example="The market is looking great today!")

class BatchPredictRequest(BaseModel):
    texts: list[str] = Field(..., min_items=1, max_items=50)

class PredictResponse(BaseModel):
    text: str
    label: str
    score: float
    latency_ms: float


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest):
    result = predict(req.text)
    insert_prediction(
        source="api",
        text=req.text,
        label=result["label"],
        score=result["score"],
        latency_ms=result["latency_ms"],
    )
    return PredictResponse(text=req.text, **result)


@app.post("/predict/batch")
def predict_batch_endpoint(req: BatchPredictRequest):
    results = predict_batch(req.texts)
    for text, result in zip(req.texts, results):
        insert_prediction(
            source="api_batch",
            text=text,
            label=result["label"],
            score=result["score"],
            latency_ms=result["latency_ms"],
        )
    return [{"text": t, **r} for t, r in zip(req.texts, results)]


@app.get("/predictions")
def recent_predictions(limit: int = 50):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return get_recent_predictions(limit)


@app.get("/drift")
def drift_stats(window: int = 500):
    return get_drift_stats(window)


@app.get("/metrics")
def metrics():
    return get_metrics()
