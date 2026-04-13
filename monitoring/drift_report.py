"""
Standalone script — prints a drift report from the local predictions database.

Usage:
    python monitoring/drift_report.py
    python monitoring/drift_report.py --db /path/to/predictions.db --window 1000
"""
import argparse
import sqlite3
import os


def report(db_path: str, window: int):
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT label, score, source, created_at FROM predictions ORDER BY created_at DESC LIMIT ?",
        (window,),
    ).fetchall()

    if not rows:
        print("No predictions in database yet.")
        return

    total = len(rows)
    positive = sum(1 for r in rows if r["label"] == "POSITIVE")
    avg_score = sum(r["score"] for r in rows) / total
    sources = {}
    for r in rows:
        sources[r["source"]] = sources.get(r["source"], 0) + 1

    print(f"\n{'='*50}")
    print(f"  Drift Report — last {total} predictions")
    print(f"{'='*50}")
    print(f"  POSITIVE : {positive} ({positive/total*100:.1f}%)")
    print(f"  NEGATIVE : {total - positive} ({(total-positive)/total*100:.1f}%)")
    print(f"  Avg confidence score : {avg_score:.4f}")
    print(f"\n  Sources:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"    {src}: {count}")

    # Sliding window trend (split into 5 buckets)
    bucket_size = total // 5
    if bucket_size > 0:
        print(f"\n  Confidence trend (oldest → newest, {bucket_size} predictions/bucket):")
        buckets = [rows[i * bucket_size:(i + 1) * bucket_size] for i in range(4, -1, -1)]
        for i, bucket in enumerate(buckets):
            avg = sum(r["score"] for r in bucket) / len(bucket)
            bar = "█" * int(avg * 20)
            print(f"    Bucket {i+1}: {bar} {avg:.4f}")

    print(f"{'='*50}\n")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.getenv("DB_PATH", "predictions.db"))
    parser.add_argument("--window", type=int, default=500)
    args = parser.parse_args()
    report(args.db, args.window)
