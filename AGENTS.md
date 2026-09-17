# Agent Guide

Use this guide for all changes in this repository. Keep it short; `README.md` is for users, `STRUCTURE.md` is the architecture map, and `SKILLS.md` contains specialized workflows.

## Toolchain & Standards

- **Python:** Always use `uv` for dependency management and running scripts (e.g., `uv run ...`).
- **Lint/Format:** Use `ruff` for Python linting and formatting.
- **Type Check:** Use `ty` for Python type checking.
- **Frontend:** Use `bun` for root scripts and `npm` for `docs/` site tasks; prefer `bun run <script>` for package.json commands.

## Deployment & Portability

The program MUST function across all supported deployment modes:

- **dev:local:** Local SQLite database (`data/tracks.db`).
- **dev:** Cloud-ready Postgres via `DATABASE_URL`.
- **PyInstaller EXE:** Use `app/constants.py` helpers for resource pathing.
- **Docker:** Alpine-based, non-root user.
- **Vercel:** Serverless via `api/index.py`.
- **Custom:** Any generic environment following the architecture rules.

## Project Snapshot

- Vocaloid Rate is a FastAPI + SQLAlchemy app with server-rendered Jinja pages, vanilla JS, Tailwind CSS, Alembic migrations, and a Docusaurus docs site.
- Runtime modes: Local/self-hosted/frozen uses SQLite (`data/tracks.db`) and auto-creates an admin user; Cloud/Vercel/Postgres requires `SECRET_KEY`, and cron endpoints require `CRON_SECRET`.
- Python target is 3.13 (`.python-version`, `pyproject.toml`, CI); prefer `uv` for Python deps.
- Prefer Bun for root frontend scripts because `bun.lock` is committed; `docs/` is its own Node project.

## Common Commands

- Install app deps: `uv sync --all-groups` + `bun install`
- Local app dev: `bun run dev:local`
- Env-driven app dev: `bun run dev`
- API only: `bun run dev:api` or `bun run dev:api:local`
- Build app assets: `bun run build` (CSS/JS only: `bun run build:css`, `bun run build:js`)
- Python lint/typecheck: `bun run lint:py`
- JS lint: `bun run lint:js`
- Full lint: `bun run lint`
- Format: `bun run format`
- Tests: `bun run test` or `uv run --with pytest pytest`
- Coverage gate: `bun run test:cov`
- Docker smoke build: `docker build . --file Dockerfile`
- Docs generation: `python scripts/update_docs.py`, then `npm run build` in `docs/`

## Architecture Rules

- Keep `app/main.py` as wiring only: lifespan, middleware, static mounting, Jinja filter registration, router registration.
- HTTP handlers in `app/routers/`; DB queries/mutations in `app/crud.py`; reusable workflows/background in `app/services/`; external integrations in `app/scraper.py` and `app/vocadb.py`.
- Request dependencies, locale/template helpers, and shared FastAPI glue in `app/dependencies.py`; cross-cutting helpers in `app/utils/`.
- Read `STRUCTURE.md` before moving boundaries; it is the source of truth for module ownership.

## Data And Migrations

- Models in `app/models.py`; Pydantic shapes in `app/schemas.py`.
- Track data has both denormalized strings and normalized producer/voicebank relationships; use the CRUD sync helpers, not one representation alone.
- User-owned data must stay scoped by `user_id`: ratings, playlists, membership, visibility, imports, exports, snapshots.
- When changing models, add an Alembic migration under `alembic/versions/`; migrations must work for SQLite and Postgres (Alembic configured with SQLite batch mode).
- Startup migrations run by default except on Vercel, where `RUN_MIGRATIONS_ON_STARTUP` defaults to false.

## Frontend Rules

- Source files are `app/static/js/*.js` and `app/static/css/input.css`; generated files are `app/static/css/app.css` and `app/static/js/*.min.js`, ignored by git. Run the build/watch script after JS/CSS changes.
- JS is plain browser script, not modules. ESLint is configured with browser globals plus `YT`, `Chart`, and `Sortable`.
- Templates and JS communicate through `data-*` attributes; preserve those contracts.
- Use existing Jinja partials/macros in `app/templates/partials/` and `app/templates/macros/` instead of duplicating markup.
- `base.html` loads htmx, JSON htmx, YouTube iframe API, Sortable, Umami, and `global.min.js`. Page templates opt into `main.min.js` and page-specific bundles.

## I18n And Generated Files

- Supported locales are `en` and `ja`; default `en`.
- Python/Jinja strings extracted with Babel from `babel.cfg`; JS strings use `window._("...")` / `_('...')`, update `locales/js_translations.json` with `bun run i18n:extract:js`.
- Compile translations with `bun run i18n:compile`.
- Do not hand-edit generated artifacts unless the task is about that output: `app/static/css/app.css`, `app/static/js/*.min.js`, `locales/**/messages.mo`, `docs/docs/`, `docs/static/openapi.json`, `public/`, `dist/`, coverage output.
- `requirements.txt` is generated from `uv`; update `pyproject.toml` and `uv.lock` first.

## Testing Notes

- Tests use in-memory SQLite, patched `SECRET_KEY`, and FastAPI dependency overrides from `tests/conftest.py`; `client_factory` disables lifespan, so route tests should not depend on startup scraping or migrations.
- Mock network work in tests. Existing tests monkeypatch Vocaloard scraping, VocaDB requests, bot jobs, and background tasks.
- Add tests near the layer changed: router/API/page behavior → `tests/test_*api*.py`, `tests/test_pages*.py`; CRUD/query → `tests/test_crud*.py`; auth/config/dependencies → matching focused files; scraping workflows → `tests/test_services_scraping.py`.
- For small changes, run the relevant test file plus lint for the touched language; for broad changes, run `bun run lint`, `bun run test`, and `bun run build`.

## Deployment And Packaging

- Vercel enters through `api/index.py`, rewrites routes, and has cron jobs for scrape and Bluesky posting.
- Docker builds assets/translations in a builder stage, then copies only runtime app, templates, static assets, locales, and Alembic files.
- PyInstaller release includes app static files, templates, locales, and migrations via `vocaloid-rate.spec`.
- Keep `entrypoint.sh` in mind for Docker: it adjusts `/app/data` ownership and runs as a matching non-root user.

## Change Hygiene

- Keep changes scoped; avoid broad rewrites of `app/static/js/main.js` unless the feature genuinely requires it.
- Do not add route logic back into `main.py`; do not bypass auth helpers or skip per-user ownership checks; do not make live external requests in tests.
- Before finishing, report which commands were run and any commands that could not be run.

## Pitfalls

- Do not hand-edit generated translation files (`locales/**/messages.mo`, `app/static/css/app.css`, `app/static/js/*.min.js`); always recompile from source.
- `bun.lock` is committed; `npm install` may change `package-lock.json` and cause diffs — prefer `bun install` for dev work.
- The uvicorn default port `8000` can conflict with other services; use a different port via `UVICORN_PORT` env var if needed.
- On Vercel, startup migrations are disabled (`RUN_MIGRATIONS_ON_STARTUP=false`); ensure migration logic is triggered by cron or CI, not assumed on cold start.
- Tests run in-memory SQLite; do not rely on `data/tracks.db` persistence unless the test explicitly sets it up.
