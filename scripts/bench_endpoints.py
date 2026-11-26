"""Reusable endpoint CPU benchmark for Vocaloid Rate.

Seeds a realistic catalog (~10k tracks, a few hundred producers/voicebanks,
ratings, playlists, rank history) into a throwaway SQLite database and measures
**CPU time** (time.process_time, not wall) and response size for the heaviest
endpoints, using FastAPI's TestClient in-process.

Usage:
    uv run python scripts/bench_endpoints.py            # seed + benchmark
    uv run python scripts/bench_endpoints.py --profile  # also cProfile top 3

Notes:
- CPU is sampled in batches to beat the coarse Windows process_time resolution.
- process_time is process-wide; run this on an otherwise idle machine.
- This is a relative, in-process measurement. It is NOT Vercel production CPU.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Ensure the repo root is importable when run as `python scripts/bench_endpoints.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- Configure a throwaway environment BEFORE importing the app ---------------
_BENCH_DB = Path(tempfile.gettempdir()) / "vocaloid_rate_bench.db"
if _BENCH_DB.exists():
    _BENCH_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_BENCH_DB.as_posix()}"
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
os.environ.setdefault("SECRET_KEY", "bench-secret-key-not-for-production")

from fastapi.testclient import TestClient

from app import models
from app.database import Base, SessionLocal, engine
from app.main import app

# --- Benchmark configuration --------------------------------------------------
REPEATS = 20  # samples per endpoint
BATCH = 10  # calls per sample (averaged) to beat timer resolution
WARMUP = 3


def seed_catalog() -> dict:
    """Populate the database with a realistic catalog. Returns key names."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Track).count() >= 9000:
            return _existing_names(db)

        import random
        from datetime import datetime, timedelta, timezone

        random.seed(1234)
        n_producers = 300
        n_voicebanks = 200
        n_tracks = 10000

        producers = [
            models.Producer(name=f"Producer {i:04d}", name_jp=f"P{i:04d}")
            for i in range(n_producers)
        ]
        voicebanks = [
            models.Voicebank(name=f"Voicebank {i:03d}", name_jp=f"V{i:03d}")
            for i in range(n_voicebanks)
        ]
        db.add_all(producers)
        db.add_all(voicebanks)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        tracks = []
        tps = []
        tvs = []
        for i in range(n_tracks):
            pub = now - timedelta(days=random.randint(0, 900))
            rank = i + 1 if i < 3000 else None
            p = random.choice(producers)
            v = random.choice(voicebanks)
            t = models.Track(
                title=f"Track Title Number {i:05d}",
                title_jp=f"Track JP {i:05d}",
                producer=p.name,
                producer_jp=p.name_jp,
                voicebank=v.name,
                voicebank_jp=v.name_jp,
                published_date=pub,
                link=f"https://www.youtube.com/watch?v=bench{i:05d}",
                image_url=f"https://i.ytimg.com/vi/bench{i:05d}/default.jpg",
                rank=rank,
            )
            tracks.append(t)
            tps.append((t, p))
            tvs.append((t, v))

        db.add_all(tracks)
        db.flush()
        for t, p in tps:
            t.producers.append(p)
        for t, v in tvs:
            t.voicebanks.append(v)

        # Ratings for a couple of users (so /rated paths have data).
        users = [
            models.User(
                email=f"user{i}@bench.local",
                hashed_password="x",
                username=f"benchuser{i}",
                is_profile_public=True,
            )
            for i in range(3)
        ]
        db.add_all(users)
        db.flush()
        for u in users:
            for t in random.sample(tracks, 1500):
                db.add(
                    models.Rating(
                        track_id=t.id,
                        user_id=u.id,
                        rating=round(random.uniform(1, 10), 1),
                    )
                )

        # A public playlist with tracks.
        pl = models.Playlist(user_id=users[0].id, name="Bench Playlist", is_public=True)
        db.add(pl)
        db.flush()
        for pos, t in enumerate(random.sample(tracks, 500)):
            db.add(models.PlaylistTrack(playlist_id=pl.id, track_id=t.id, position=pos))

        # Rank history: a few snapshots for all ranked tracks.
        for day in range(6):
            recorded = now - timedelta(days=day)
            for t in tracks[:3000]:
                db.add(
                    models.RankHistory(track_id=t.id, rank=t.rank, recorded_at=recorded)
                )
        db.commit()
        return {
            "producer": producers[0].name,
            "voicebank": voicebanks[0].name,
            "playlist": pl.id,
        }
    finally:
        db.close()


def _existing_names(db) -> dict:
    p = db.query(models.Producer).first()
    v = db.query(models.Voicebank).first()
    pl = db.query(models.Playlist).first()
    return {"producer": p.name, "voicebank": v.name, "playlist": pl.id}


def build_endpoints(names: dict) -> list[tuple[str, str]]:
    return [
        ("GET", "/"),
        ("GET", "/?limit=all"),
        ("GET", "/_/get_tracks"),
        ("GET", "/_/get_tracks?limit=100"),
        ("GET", "/api/playlist-snapshot"),
        ("GET", f"/producer/{names['producer']}"),
        ("GET", f"/voicebank/{names['voicebank']}"),
        ("GET", "/sitemap.xml"),
        ("GET", "/robots.txt"),
    ]


def time_endpoint(client: TestClient, method: str, path: str) -> dict:
    # Warm up (Jinja compile, lazy imports, connection pool).
    for _ in range(WARMUP):
        client.request(method, path)

    samples_ms = []
    last_bytes = 0
    last_status = 0
    for _ in range(REPEATS):
        c0 = time.process_time()
        for _ in range(BATCH):
            resp = client.request(method, path)
        c1 = time.process_time()
        last_bytes = len(resp.content)
        last_status = resp.status_code
        samples_ms.append(((c1 - c0) / BATCH) * 1000.0)

    samples_ms.sort()
    p95 = samples_ms[round(0.95 * (len(samples_ms) - 1))]
    return {
        "median_ms": statistics.median(samples_ms),
        "p95_ms": p95,
        "bytes": last_bytes,
        "status": last_status,
    }


def profile_endpoint(client: TestClient, method: str, path: str, top: int = 20) -> None:
    import cProfile
    import io
    import pstats

    for _ in range(WARMUP):
        client.request(method, path)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(BATCH):
        client.request(method, path)
    pr.disable()
    buf = io.StringIO()
    stats = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
    stats.print_stats(top)
    print(buf.getvalue())


def profile_core(names: dict, top: int = 25) -> None:
    """Profile the synchronous CPU core (query + serialize + render) in-thread.

    TestClient runs sync routes in a worker thread, so cProfile around the client
    only sees the anyio portal. This exercises the real work directly.
    """
    import cProfile
    import io
    import pstats

    from app import crud
    from app.dependencies import templates
    from app.utils.view_helpers import serialize_tracks

    db = SessionLocal()
    try:
        # Mimic /_/get_tracks?limit=all (ranked, no user) then render the partial.
        def one_call():
            total = crud.get_tracks_count(db, user_id=None, rank_filter="ranked")
            tracks = crud.get_tracks(
                db, user_id=None, skip=0, limit=total or 10000, rank_filter="ranked"
            )
            body = templates.get_template("partials/tracks_table_body.html").render(
                {
                    "request": None,
                    "_": (lambda s: s),
                    "tracks": tracks,
                    "tracks_json": serialize_tracks(tracks),
                    "locale": "en",
                    "current_user": None,
                }
            )
            return len(body)

        for _ in range(WARMUP):
            one_call()
        pr = cProfile.Profile()
        pr.enable()
        for _ in range(BATCH):
            one_call()
        pr.disable()
        buf = io.StringIO()
        pstats.Stats(pr, stream=buf).sort_stats("cumulative").print_stats(top)
        print(buf.getvalue())
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-core", action="store_true")
    args = parser.parse_args()

    names = seed_catalog()
    client = TestClient(app)
    endpoints = build_endpoints(names)

    print(f"\n{'endpoint':38} {'status':>6} {'bytes':>9} {'median':>9} {'p95':>9}")
    print(f"{'':38} {'':>6} {'':>9} {'CPU ms':>9} {'CPU ms':>9}")
    print("-" * 76)
    results = []
    for method, path in endpoints:
        r = time_endpoint(client, method, path)
        results.append((path, r))
        label = path if len(path) <= 38 else path[:35] + "..."
        print(
            f"{label:38} {r['status']:>6} {r['bytes']:>9} "
            f"{r['median_ms']:>9.2f} {r['p95_ms']:>9.2f}"
        )

    if args.profile:
        for path, _ in sorted(results, key=lambda x: x[1]["median_ms"], reverse=True)[
            :3
        ]:
            method = "GET"
            print(f"\n===== cProfile (cumulative, {BATCH} calls): {path} =====")
            profile_endpoint(client, method, path)

    if args.profile_core:
        print(f"\n===== CORE cProfile (query+serialize+render, {BATCH} calls) =====")
        profile_core(names)


if __name__ == "__main__":
    main()
