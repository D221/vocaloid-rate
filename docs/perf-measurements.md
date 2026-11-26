# Performance measurements — provenance

Every number in this repo's perf work is tagged with the interpreter/OS it came
from. **No production/Vercel measurement is included** — all figures are local.

## Environment matrix

| Measurement                                               | Interpreter / OS                          | Notes                                                                           |
| --------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------- |
| In-process endpoint bench (`scripts/bench_endpoints.py`)  | CPython 3.15 (uv `.venv`), Windows        | `time.process_time()` (process-wide, incl. threadpool), gzip wire bytes, SQLite |
| Full test suite                                           | **CPython 3.13.14**, Windows (`.venv313`) | 222 passed                                                                      |
| Import time (`python -X importtime -c "import app.main"`) | **CPython 3.13.14**, Windows, warm        | 1691 ms cumulative                                                              |
| Playwright request/player audit                           | Chromium (headless), Windows              | against a local uvicorn (SQLite)                                                |

Docker/Postgres was unavailable, so no Postgres or Linux-container numbers exist;
Postgres would only add _wait_ (not billed as Active CPU).

## Import time (CPython 3.13.14, warm) — top contributors

`charset_normalizer` (via `requests`), `fastapi`, `sqlalchemy`, `app.routers.*`,
`pydantic_core`. **`alembic`, `atproto`, `cryptography`, `libipld` are absent**
(removed by lazy imports). Total ≈ **1.69 s** on this Windows machine; Linux on
Vercel is [Guessed] similar or faster.

## Cold-start CPU estimate (hypothesis)

[Measured] Warm `import app.main` on CPython 3.13.14/Windows ≈ **1.69 s**; add a
small lifespan cost (one `count(*)` query) ⇒ **~1.7 CPU-s per cold start**
(Linux on Vercel is [Guessed] similar).

[Inferred] To equal the **600–1020 CPU-s/day** budget _entirely_ from cold
starts: 600 / 1.7 ≈ **~350** and 1020 / 1.7 ≈ **~600** cold starts/day.

**Hypothesis H_cold:** if the deployment scales to zero often (sporadic traffic),
init CPU could be a large fraction of the bill. **Confirm/reject with:** the
`startup: init_ms=...` line (logged once per cold start) aggregated over a day,
and Vercel's per-function **init duration** in the dashboard. If
`Σ init_ms` ≈ hundreds of seconds/day, cold starts dominate; if it is a few
seconds, they are negligible and the cause is request volume (bots).
