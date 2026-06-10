# Agent Guide

Use this guide for all changes in this repository. Keep it current, but keep it
short; `README.md` is for users, `STRUCTURE.md` is the fuller architecture map,
and `SKILLS.md` contains specialized workflows for different task types.

## Toolchain & Standards

- **Python Management:** ALWAYS use `uv` for dependency management and running scripts (e.g., `uv run ...`).
- **Linting & Formatting:** Use `ruff` for all Python linting and formatting.
- **Type Checking:** Use `ty` for Python type checking.
- **Frontend Tools:** Use `bun` for root scripts and `npm` for `docs/` site tasks.
- **Task Runner:** Prefer `bun run <script>` for any command defined in `package.json`.

## Deployment & Portability

The program MUST function correctly across all supported deployment modes:

- **dev:local:** Local development with a local SQLite database (`data/tracks.db`).
- **dev:** Cloud-ready development (e.g., Postgres via `DATABASE_URL`).
- **PyInstaller EXE:** Frozen executable mode (resource pathing must use `app/constants.py` helpers).
- **Docker:** Containerized deployment (Alpine-based, non-root user).
- **Vercel:** Serverless deployment via `api/index.py`.
- **Custom Deployment:** Any generic server environment following the architecture rules.

## Project Snapshot

- Vocaloid Rate is a FastAPI + SQLAlchemy app with server-rendered Jinja pages,
  vanilla browser JavaScript, Tailwind CSS, Alembic migrations, and a Docusaurus
  docs site.
- Runtime modes:
  - Local/self-hosted/frozen: SQLite in `data/tracks.db`, local auth auto-creates
    an admin user.
  - Cloud/Vercel/Postgres: `DATABASE_URL` is set, auth requires `SECRET_KEY`,
    scheduled cron endpoints require `CRON_SECRET`.
- Python target is 3.13 (`.python-version`, `pyproject.toml`, CI). Prefer `uv`
  for Python dependency and command execution.
- Prefer Bun for root frontend scripts because `bun.lock` is committed. The docs
  site under `docs/` is its own Node project.

## Common Commands

- Install app deps: `uv sync --all-groups` and `bun install`
- Local app dev: `bun run dev:local`
- Env-driven app dev: `bun run dev`
- API only: `bun run dev:api` or `bun run dev:api:local`
- Build app assets: `bun run build`
- Build only CSS/JS: `bun run build:css`, `bun run build:js`
- Python lint/typecheck: `bun run lint:py`
- JS lint: `bun run lint:js`
- Full lint: `bun run lint`
- Format: `bun run format`
- Tests: `bun run test` or `uv run --with pytest --with httpx2 pytest`
- Coverage gate: `bun run test:cov`
- Docker smoke build: `docker build . --file Dockerfile`
- Docs generation: `python scripts/update_docs.py`, then `npm run build` in
  `docs/`

## Architecture Rules

- Keep `app/main.py` as app wiring only: lifespan, middleware, static mounting,
  Jinja filter registration, and router registration.
- Put HTTP request/response handling in `app/routers/`.
- Put database queries and mutations in `app/crud.py`.
- Put reusable workflows and background orchestration in `app/services/`.
- Put external integrations in focused modules such as `app/scraper.py` and
  `app/vocadb.py`.
- Put request dependencies, locale/template helpers, and shared FastAPI glue in
  `app/dependencies.py`.
- Put small cross-cutting helpers in `app/utils/`.
- Read `STRUCTURE.md` before moving boundaries; it is the detailed source of
  truth for module ownership.

## Data And Migrations

- Models live in `app/models.py`; Pydantic API shapes live in `app/schemas.py`.
- Track data has both denormalized string columns and normalized
  producer/voicebank relationships. Use the existing CRUD sync helpers instead
  of updating only one representation.
- User-owned data must stay scoped by `user_id`: ratings, playlists, playlist
  membership, profile visibility, imports, exports, and snapshots.
- When changing models, add an Alembic migration under `alembic/versions/`.
  Migrations must work for SQLite and Postgres; Alembic is configured with
  SQLite batch mode.
- Startup migrations run by default except on Vercel, where
  `RUN_MIGRATIONS_ON_STARTUP` defaults to false.

## Frontend Rules

- Source files are `app/static/js/*.js` and `app/static/css/input.css`.
- Rendered templates load generated files: `app/static/css/app.css` and
  `app/static/js/*.min.js`. These are ignored by git; run the build/watch script
  after changing JS or CSS.
- JS is plain browser script, not modules. ESLint is configured with browser
  globals plus `YT`, `Chart`, and `Sortable`.
- Templates and JS communicate heavily through `data-*` attributes. Preserve
  those contracts when changing markup or event handlers.
- Use existing Jinja partials/macros in `app/templates/partials/` and
  `app/templates/macros/` instead of duplicating markup.
- `base.html` loads htmx, the JSON htmx extension, YouTube iframe API, Sortable,
  Umami, and `global.min.js`. Page templates opt into `main.min.js` and
  page-specific bundles.

## I18n And Generated Files

- Supported locales are `en` and `ja`; default is `en`.
- Python/Jinja strings are extracted with Babel from `babel.cfg`.
- JS strings use `window._("...")` / `_('...')`; update
  `locales/js_translations.json` with `bun run i18n:extract:js`.
- Compile translations with `bun run i18n:compile`.
- Do not hand-edit generated artifacts unless the task is specifically about the
  generated output:
  - `app/static/css/app.css`
  - `app/static/js/*.min.js`
  - `locales/**/messages.mo`
  - `docs/docs/`
  - `docs/static/openapi.json`
  - `public/`, `dist/`, coverage output
- `requirements.txt` is generated from `uv`; update `pyproject.toml` and
  `uv.lock` first.

## Testing Notes

- Tests use in-memory SQLite, patched `SECRET_KEY`, and FastAPI dependency
  overrides from `tests/conftest.py`.
- `client_factory` disables lifespan, so route tests should not depend on
  startup scraping or migrations.
- Mock network work in tests. Existing tests monkeypatch Vocaloard scraping,
  VocaDB requests, bot jobs, and background tasks.
- Add tests near the layer changed:
  - router/API/page behavior: `tests/test_*api*.py`, `tests/test_pages*.py`
  - CRUD/query behavior: `tests/test_crud*.py`
  - auth/config/dependencies: matching focused files
  - scraping workflows: `tests/test_services_scraping.py`
- For small changes, run the most relevant test file plus lint for the touched
  language. For broad changes, run `bun run lint`, `bun run test`, and
  `bun run build`.

## Deployment And Packaging

- Vercel enters through `api/index.py`, rewrites all routes there, and has cron
  jobs for scrape and Bluesky posting.
- Docker builds assets and translations in a builder stage, then copies only
  runtime app files, templates, static assets, locales, and Alembic files.
- The PyInstaller release includes app static files, templates, locales, and
  migrations via `vocaloid-rate.spec`.
- Keep `entrypoint.sh` behavior in mind for Docker: it adjusts `/app/data`
  ownership and runs the app as a matching non-root user.

## Change Hygiene

- Keep changes scoped. Avoid broad rewrites of `app/static/js/main.js` unless the
  feature genuinely requires it.
- Do not add route logic back into `main.py`.
- Do not bypass auth helpers or skip per-user ownership checks for convenience.
- Do not make live external requests in tests.
- Before finishing, report which commands were run and any commands that could
  not be run.
