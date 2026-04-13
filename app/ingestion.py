"""
Reddit ingestion worker — no API credentials required.

Uses Reddit's public JSON feed (reddit.com/r/<subreddit>/new.json)
which is freely accessible with just a User-Agent header.

Environment variables (all optional):
  REDDIT_SUBREDDIT    subreddit to poll, default "worldnews"
  POLL_INTERVAL       seconds between polls, default 60
"""
import os
import time
import logging
import threading

import requests

from app.model import predict
from app.database import insert_prediction, insert_ingestion_run

logger = logging.getLogger(__name__)

_seen_ids: set[str] = set()
_worker_thread: threading.Thread | None = None
_running = False

HEADERS = {"User-Agent": "sentiment-bot/1.0 (personal ML project)"}


def _fetch_posts(subreddit_name: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit_name}/new.json?limit=25"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]["children"]


def _poll_once(subreddit_name: str) -> int:
    posts = _fetch_posts(subreddit_name)
    new_posts = []
    for child in posts:
        post = child["data"]
        if post["id"] not in _seen_ids:
            _seen_ids.add(post["id"])
            new_posts.append(post)

    for post in new_posts:
        result = predict(post["title"])
        insert_prediction(
            source=f"reddit/r/{subreddit_name}",
            text=post["title"],
            label=result["label"],
            score=result["score"],
            latency_ms=result["latency_ms"],
        )
        logger.debug(f"[{result['label']} {result['score']:.2f}] {post['title'][:80]}")

    if new_posts:
        insert_ingestion_run(subreddit_name, len(new_posts))
        logger.info(f"Ingested {len(new_posts)} new posts from r/{subreddit_name}")

    return len(new_posts)


def _worker_loop(subreddit_name: str, poll_interval: int):
    global _running
    logger.info(f"Ingestion worker started — polling r/{subreddit_name} every {poll_interval}s")
    while _running:
        try:
            _poll_once(subreddit_name)
        except Exception as e:
            logger.error(f"Ingestion error: {e}")
        time.sleep(poll_interval)
    logger.info("Ingestion worker stopped")


def start_worker():
    global _worker_thread, _running
    if _worker_thread and _worker_thread.is_alive():
        return
    subreddit = os.getenv("REDDIT_SUBREDDIT", "worldnews")
    interval = int(os.getenv("POLL_INTERVAL", "60"))
    _running = True
    _worker_thread = threading.Thread(
        target=_worker_loop, args=(subreddit, interval), daemon=True
    )
    _worker_thread.start()


def stop_worker():
    global _running
    _running = False
