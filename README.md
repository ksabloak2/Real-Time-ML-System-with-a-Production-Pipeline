# Real-Time ML System with a Production Pipeline

A fully production-grade sentiment analysis system that ingests live Reddit posts, runs inference via a fine-tuned transformer, serves predictions through a REST API, ships in Docker, and tracks prediction drift over time.

---

## Architecture

```
Reddit API (every 60s)
       │
       ▼
  Ingestion Worker (PRAW)
       │
       ▼
  Sentiment Model (DistilBERT)
       │
       ▼
  SQLite (predictions + logs)
       │
       ▼
  FastAPI  ←── external callers
       │
       ▼
  Monitoring endpoints (/metrics, /drift)
```

---

## Project Structure

```
├── app/
│   ├── main.py          # FastAPI app + endpoints
│   ├── model.py         # DistilBERT inference wrapper
│   ├── ingestion.py     # Reddit polling worker (background thread)
│   ├── database.py      # SQLite helpers
│   └── monitor.py       # Request metrics middleware
├── monitoring/
│   └── drift_report.py  # CLI drift report from the database
├── scripts/
│   └── run_local.sh     # Local dev runner (no Docker)
├── deploy/
│   ├── ec2_setup.sh     # One-command EC2 bootstrap
│   └── nginx.conf       # Reverse proxy config
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Quick Start (Local, no Docker)

```bash
cp .env.example .env
# edit .env with your Reddit API credentials
bash scripts/run_local.sh
```

API docs at http://localhost:8000/docs

---

## Quick Start (Docker)

```bash
cp .env.example .env
# edit .env with your Reddit credentials
mkdir -p data
docker compose up --build
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/predict` | Single text → sentiment label + score |
| `POST` | `/predict/batch` | Up to 50 texts at once |
| `GET` | `/predictions` | Recent stored predictions |
| `GET` | `/drift` | Label distribution + avg confidence |
| `GET` | `/metrics` | Request count, latency, errors |
| `GET` | `/health` | Liveness check |

### Example

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "The stock market is up 5% today!"}'
```

```json
{
  "text": "The stock market is up 5% today!",
  "label": "POSITIVE",
  "score": 0.9987,
  "latency_ms": 42.1
}
```

---

## Reddit Credentials

1. Go to https://www.reddit.com/prefs/apps
2. Click **Create another app** → choose **script**
3. Copy the client ID and secret into your `.env`

```env
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=sentiment-bot/1.0 by u/your_username
REDDIT_SUBREDDIT=worldnews
POLL_INTERVAL=60
```

If credentials are not set, the API still runs — ingestion is simply disabled.

---

## Deploy to AWS EC2 (Free Tier)

1. Launch an EC2 instance (t2.micro, Ubuntu 22.04 or Amazon Linux 2023)
2. Open port 80 and 8000 in the Security Group
3. SSH in and run:

```bash
bash <(curl -s https://raw.githubusercontent.com/krishsabloak/Real-Time-ML-System-with-a-Production-Pipeline/main/deploy/ec2_setup.sh)
```

That's it. The script installs Docker, clones the repo, and starts the container.

---

## Monitoring & Drift

```bash
# From the API
curl http://localhost:8000/drift

# From the CLI (run locally against the DB)
python monitoring/drift_report.py --window 500
```

The drift report shows label distribution and a confidence trend bucketed over time. A declining average score signals the model is becoming less certain — a prompt to retrain or investigate the data.

---

## Model

Uses [`distilbert-base-uncased-finetuned-sst-2-english`](https://huggingface.co/distilbert-base-uncased-finetuned-sst-2-english) — a 66M parameter model fine-tuned on SST-2. No training required; the weights are downloaded automatically from HuggingFace on first run (baked into the Docker image at build time).

To swap in your own fine-tuned model, edit `app/model.py` and change the `model=` argument in the `pipeline()` call.
