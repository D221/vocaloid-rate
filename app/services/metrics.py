"""Durable, sampled request metrics for CPU attribution on serverless.

Vercel Hobby keeps runtime logs for only ~1 hour / 4000 rows, which is too short
for daily aggregation. When ``RECORD_METRICS_SAMPLE`` is set to a positive
integer N, roughly 1 in N requests is appended to the ``request_metrics`` table
(Postgres in production). The write is best-effort and fail-open: any error is
swallowed so a metrics failure never breaks a request.

Prune old rows with :func:`prune` (called from the daily cron).
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta, timezone

from app import models
from app.database import SessionLocal

logger = logging.getLogger(__name__)

RECORD_METRICS_SAMPLE_ENV = "RECORD_METRICS_SAMPLE"
PRUNE_AFTER_DAYS = 14

_cold_start_consumed = False
_warned_missing = False


def _sample_rate() -> int:
    try:
        return max(0, int(os.environ.get(RECORD_METRICS_SAMPLE_ENV, "0") or 0))
    except (TypeError, ValueError):
        return 0


def enabled() -> bool:
    """True when sampled recording is active (RECORD_METRICS_SAMPLE > 0)."""
    return _sample_rate() > 0


def is_cold_start() -> bool:
    """True only for the first request handled by this process instance."""
    global _cold_start_consumed
    if _cold_start_consumed:
        return False
    _cold_start_consumed = True
    return True


def _safe_close(db) -> None:
    if db is None:
        return
    try:
        db.close()
    except Exception:  # noqa: BLE001, S110 - close must never raise
        pass


def record(
    route: str,
    status: int,
    ua_class: str,
    cpu_ms: float,
    bytes_sent: int,
    is_cold: bool,
) -> None:
    """Append one sampled row. Fail-open: never raises."""
    rate = _sample_rate()
    if rate <= 0:
        return
    if random.randint(1, rate) != 1:
        return
    db = None
    try:
        db = SessionLocal()
        db.add(
            models.RequestMetric(
                route=(route or "")[:200],
                status=int(status),
                ua_class=(ua_class or "")[:10],
                cpu_ms=float(cpu_ms),
                bytes_sent=int(bytes_sent),
                is_cold_start=bool(is_cold),
            )
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - metrics must never break requests
        global _warned_missing
        if not _warned_missing:
            _warned_missing = True
            logger.warning(
                "request metrics unavailable (table missing?); recording paused "
                "for this instance: %s",
                exc,
            )
        else:
            logger.debug("request metric write failed: %s", exc)
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001, S110
                pass
    finally:
        _safe_close(db)


def prune(days: int = PRUNE_AFTER_DAYS) -> int:
    """Delete rows older than ``days``. Returns rows removed, or -1 on failure."""
    db = None
    try:
        db = SessionLocal()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        removed = (
            db.query(models.RequestMetric)
            .filter(models.RequestMetric.created_at < cutoff)
            .delete()
        )
        db.commit()
        return int(removed)
    except Exception as exc:  # noqa: BLE001
        logger.debug("request metric prune failed: %s", exc)
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001, S110
                pass
        return -1
    finally:
        _safe_close(db)
