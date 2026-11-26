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

## Reconciliation — what is measured vs guessed

Budget: **600–1020 CPU-s/day** (10–17 min).

**[Measured]**

- Per-invocation CPU (gzip, process-wide, SQLite): doc `/` ≈ 56 ms, `/_/get_tracks`
  (100) ≈ 48 ms, snapshot ≈ 33 ms, static ≈ 8 ms each, translations ≈ 8 ms,
  `/?limit=all` (capped) ≈ 185 ms.
- A page view issues ~8–9 same-origin function calls (pre-fix) ≈ **~110 ms**.
- Tracked ~45 views/day; even ×10 = 450 views/day ⇒ **~50 CPU-s/day**.

**[Inferred]**

- 50 CPU-s is only **~5–8%** of 600–1020. Reaching the budget at ~110 ms/view
  needs **~5,500–9,300 page-equivalents/day** ⇒ the bulk is **non-human
  (crawler/bot) volume** Umami does not count.
- After the fixes, static + translations + doc are CDN-cached (`s-maxage`), so a
  crawler's repeat page fetches cost ~0 function CPU (cache HIT); only
  cache-miss/cold requests pay.

**[Guessed] — the unexplained fraction**

- **~92–95% of the 600–1020 CPU-s/day is not explained by measured human
  traffic.** It is a guess split across: (H_bot) crawler volume, (H_cold) cold
  starts (~1.7 CPU-s each; ~350–600/day would alone equal the budget), and
  (H_miss) cache-miss / heavy `limit=all` requests.
- **Telemetry to close it:** `request_metrics` rows (route, ua_class, cpu_ms,
  is_cold_start) + `startup: init_ms` lines + `x-vercel-cache` HIT ratio, over a
  few days. `scripts/metrics_summary.py` ranks routes by CPU and splits bot vs
  human; the `cold=true` rows and `init_ms` lines quantify H_cold.
