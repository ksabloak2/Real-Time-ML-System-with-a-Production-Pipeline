"""
Sentiment classifier using a pre-trained DistilBERT model.
No training required — loads directly from HuggingFace.
"""
from transformers import pipeline
import time
import logging

logger = logging.getLogger(__name__)

_classifier = None


def load_model():
    global _classifier
    if _classifier is None:
        logger.info("Loading sentiment model...")
        start = time.time()
        _classifier = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
        logger.info(f"Model loaded in {time.time() - start:.2f}s")
    return _classifier


def predict(text: str) -> dict:
    """
    Run inference on a single text string.
    Returns: {"label": "POSITIVE"|"NEGATIVE", "score": float, "latency_ms": float}
    """
    classifier = load_model()
    start = time.time()
    result = classifier(text)[0]
    latency_ms = (time.time() - start) * 1000
    return {
        "label": result["label"],
        "score": round(result["score"], 4),
        "latency_ms": round(latency_ms, 2),
    }


def predict_batch(texts: list[str]) -> list[dict]:
    """Run inference on a batch of texts."""
    classifier = load_model()
    start = time.time()
    results = classifier(texts)
    latency_ms = (time.time() - start) * 1000
    per_item_latency = round(latency_ms / len(texts), 2)
    return [
        {
            "label": r["label"],
            "score": round(r["score"], 4),
            "latency_ms": per_item_latency,
        }
        for r in results
    ]
