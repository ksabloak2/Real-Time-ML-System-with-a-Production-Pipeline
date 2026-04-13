"""
Reddit ingestion worker.

Polls a subreddit every POLL_INTERVAL seconds, runs sentiment inference
on new post titles, and writes results to the database.

Environment variables required:
  REDDIT_CLIENT_ID
  REDDIT_CLIENT_SECRET
  REDDIT_USER_AGENT   (e.g. "sentiment-bot/1.0 by u/yourname")
  REDDIT_SUBREDDIT    (default: "worldnews")
  POLL_INTERVAL       (default: 60 seconds)
"""
import os
import time
import logging
import threading
import praw

from app.model import predict
from app.database import insert_prediction, insert_ingestion_run

logger = logging.getLogger(__name__)

_seen_ids: set[str] = set()
_worker_thread: threading.Thread | None = None
_running = False


def _build_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.getenv("REDDIT_USER_AGENT", "sentiment-bot/1.0"),
        read_only=True,
    )


def _poll_once(reddit: praw.Reddit, subreddit_name: str) -> int:
    subreddit = reddit.subreddit(subreddit_name)
    new_posts = []
    for submission in subreddit.new(limit=25):
        if submission.id not in _seen_ids:
            _seen_ids.add(submission.id)
            new_posts.append(submission)

    for post in new_posts:
        result = predict(post.title)
        insert_prediction(
            source=f"reddit/r/{subreddit_name}",
            text=post.title,
            label=result["label"],
            score=result["score"],
            latency_ms=result["latency_ms"],
        )
        logger.debug(f"[{result['label']} {result['score']:.2f}] {post.title[:80]}")

    if new_posts:
        insert_ingestion_run(subreddit_name, len(new_posts))
        logger.info(f"Ingested {len(new_posts)} new posts from r/{subreddit_name}")

    return len(new_posts)


def _worker_loop(subreddit_name: str, poll_interval: int):
    global _running
    reddit = _build_reddit_client()
    logger.info(f"Ingestion worker started — polling r/{subreddit_name} every {poll_interval}s")
    while _running:
        try:
            _poll_once(reddit, subreddit_name)
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
