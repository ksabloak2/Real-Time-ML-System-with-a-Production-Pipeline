"""
SQLite-backed storage for predictions and ingestion logs.
Keeps a rolling window of recent predictions for drift monitoring.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "predictions.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT    NOT NULL,
                text        TEXT    NOT NULL,
                label       TEXT    NOT NULL,
                score       REAL    NOT NULL,
                latency_ms  REAL    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subreddit   TEXT    NOT NULL,
                posts_fetched INTEGER NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


def insert_prediction(source: str, text: str, label: str, score: float, latency_ms: float):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO predictions (source, text, label, score, latency_ms) VALUES (?,?,?,?,?)",
            (source, text[:1000], label, score, latency_ms),
        )
        conn.commit()


def insert_ingestion_run(subreddit: str, posts_fetched: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ingestion_runs (subreddit, posts_fetched) VALUES (?,?)",
            (subreddit, posts_fetched),
        )
        conn.commit()


def get_recent_predictions(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_drift_stats(window: int = 500) -> dict:
    """
    Return average confidence score and label distribution over the last N predictions.
    A drop in average score can signal distribution shift.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT label, score FROM predictions ORDER BY created_at DESC LIMIT ?", (window,)
        ).fetchall()

    if not rows:
        return {"total": 0, "positive_pct": 0, "negative_pct": 0, "avg_score": 0}

    total = len(rows)
    positive = sum(1 for r in rows if r["label"] == "POSITIVE")
    avg_score = sum(r["score"] for r in rows) / total

    return {
        "total": total,
        "positive_pct": round(positive / total * 100, 1),
        "negative_pct": round((total - positive) / total * 100, 1),
        "avg_score": round(avg_score, 4),
    }
