"""Read-only summary of the request_metrics table (CPU attribution).

Prints top routes by total CPU and by request count, split bot vs human, plus
cold-start share. Requires the request_metrics table (RECORD_METRICS_SAMPLE>0 in
production). Read-only.

Usage: uv run python scripts/metrics_summary.py [--days 7]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from app import models
from app.database import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    db = SessionLocal()
    try:
        base = db.query(models.RequestMetric).filter(
            models.RequestMetric.created_at >= cutoff
        )
        total = base.count()
        cold = base.filter(models.RequestMetric.is_cold_start.is_(True)).count()
        print(f"rows={total} (last {args.days}d)  cold_start_rows={cold}")
        if total == 0:
            print("no data (is RECORD_METRICS_SAMPLE set?)")
            return

        print("\n== Top routes by TOTAL CPU (ms) ==")
        rows = (
            db.query(
                models.RequestMetric.route,
                func.count().label("n"),
                func.sum(models.RequestMetric.cpu_ms).label("cpu"),
            )
            .filter(models.RequestMetric.created_at >= cutoff)
            .group_by(models.RequestMetric.route)
            .order_by(func.sum(models.RequestMetric.cpu_ms).desc())
            .limit(15)
            .all()
        )
        for route, n, cpu in rows:
            print(f"  {cpu:10.1f} ms  {n:6d} req  {route}")

        print("\n== Top routes by COUNT ==")
        rows = (
            db.query(
                models.RequestMetric.route,
                func.count().label("n"),
                func.sum(models.RequestMetric.cpu_ms).label("cpu"),
            )
            .filter(models.RequestMetric.created_at >= cutoff)
            .group_by(models.RequestMetric.route)
            .order_by(func.count().desc())
            .limit(15)
            .all()
        )
        for route, n, cpu in rows:
            print(f"  {n:6d} req  {cpu:10.1f} ms  {route}")

        print("\n== Bot vs human ==")
        rows = (
            db.query(
                models.RequestMetric.ua_class,
                func.count().label("n"),
                func.sum(models.RequestMetric.cpu_ms).label("cpu"),
            )
            .filter(models.RequestMetric.created_at >= cutoff)
            .group_by(models.RequestMetric.ua_class)
            .all()
        )
        for ua, n, cpu in rows:
            print(f"  {ua:6} {n:6d} req  {cpu:10.1f} ms")
    finally:
        db.close()


if __name__ == "__main__":
    main()
