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
