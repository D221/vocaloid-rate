# Vocaloid Rate — Claude Code Guide

## Toolchain & Standards

- **Python Management:** Use `uv` for dependency management and running scripts (`uv run ...`).
- **Linting & Formatting:** `ruff` for Python linting/formatting.
- **Type Checking:** `ty` for Python type checking.
- **Frontend Tools:** `bun` for root scripts; `npm` for `docs/` site.
- **Task Runner:** Prefer `bun run <script>` for commands in `package.json`.

## Architecture Rules

- **`app/main.py`** — app wiring only (lifespan, middleware, static mounting, router registration).
- **`app/routers/`** — HTTP request/response handling.
- **`app/crud.py`** — database queries and mutations.
- **`app/services/`** — reusable workflows and background orchestration.
- **`app/dependencies.py`** — FastAPI dependencies, locale/template helpers.
- **`app/utils/`** — small cross-cutting helpers.
- Read `STRUCTURE.md` before moving module boundaries.

## Frontend

- Source: `app/static/js/*.js` and `app/static/css/input.css`.
- Templates load generated files (`*.min.js`, `app.css`). Run `bun run build` after changes.
- JS is plain browser script (not modules) with globals: `YT`, `Chart`, `Sortable`.
- Templates communicate with JS via `data-*` attributes — preserve those contracts.
- Use existing partials/macros in `app/templates/partials/` and `app/templates/macros/`.

## I18n

- Supported: `en` (default) and `ja`.
- Python/Jinja: `_("...")` | JS: `window._("...")`.
- Extract: `bun run i18n:extract` | Compile: `bun run i18n:compile`.

## Testing

- In-memory SQLite from `tests/conftest.py`, network calls monkeypatched.
- Add tests near the changed layer. Run `bun run lint && bun run test` before committing.

## Data & Migrations

- Models: `app/models.py` | Pydantic schemas: `app/schemas.py`.
- User-owned data scoped by `user_id` (ratings, playlists, profiles).
- Migrations in `alembic/versions/` — must work for both SQLite and Postgres.

## Common Commands

| Command             | What it does                 |
| ------------------- | ---------------------------- |
| `bun run dev:local` | Local dev with SQLite        |
| `bun run dev`       | Env-driven dev (Postgres)    |
| `bun run build`     | Build CSS + JS + i18n        |
| `bun run lint`      | Full lint (JS + Python)      |
| `bun run format`    | Format all files             |
| `bun run test`      | Run all tests                |
| `bun run test:cov`  | Tests with 80% coverage gate |
