# Project Structure

This document describes the current Vocaloid Rate code layout after the
FastAPI refactor and module split. It is the architecture reference for where
new code should live.

## Top-Level Layout

```text
app/                 FastAPI application package
  main.py            App factory/wiring, lifespan, middleware, static mounting
  config.py          Environment/runtime mode helpers
  constants.py       Shared constants and runtime resource paths
  database.py        SQLAlchemy engine, session factory, Base
  dependencies.py    FastAPI dependencies, templates, locale/i18n helpers
  models.py          SQLAlchemy ORM models
  schemas.py         Pydantic request/response models
  crud.py            Database query and mutation layer
  auth.py            Auth/user resolution/password/JWT helpers
  security.py        Security constants
  scraper.py         Vocaloard scraping integration
  vocadb.py          VocaDB API integration
  routers/           HTTP routes grouped by feature
  services/          Reusable workflows/background orchestration
  utils/             Small shared helpers
  templates/         Jinja pages, partials, and macros
  static/            Source JS, source CSS, icons, manifests, service worker
alembic/             Database migrations
api/index.py         Vercel ASGI entrypoint
scripts/             Maintenance, docs, i18n, user admin, bot jobs
tests/               Pytest suite
docs/                Docusaurus documentation site
```

## Core Boundary

`app/main.py` wires the app together. It should not become a feature module.

Keep in `app/main.py`:

- `FastAPI(...)`
- lifespan startup/shutdown
- startup migration trigger
- empty-database initial scrape scheduling
- middleware
- `/static/sw.js` special serving
- static file mounting
- shared Jinja filter registration
- `app.include_router(...)`

Do not add to `app/main.py`:

- page handlers
- API handlers
- database query logic
- scrape/VocaDB implementation details
- playlist/rating/profile business rules

`main.py` re-exports a few names for compatibility and tests. New production
code should import directly from the owner module.

## Application Modules

### `app/config.py`

Centralizes environment and runtime mode decisions:

- frozen/PyInstaller detection
- Vercel detection
- `DATABASE_URL`, `DATA_DIR`, `PUBLIC_BASE_URL`, `SECRET_KEY`
- local mode vs cloud mode
- local auth mode
- secure-cookie decision
- startup migration default

Use this when behavior depends on environment variables or packaging mode.

### `app/constants.py`

Stores shared constants and filesystem/resource paths:

- `BASE_DIR`, `STATIC_DIR`
- supported/default locales
- upload and pagination constants
- scrape status file path
- runtime resource base path for normal and frozen builds

Use this for reused values that are not request-specific.

### `app/database.py`

Creates the SQLAlchemy engine, `SessionLocal`, and declarative `Base`.

Behavior:

- loads `.env` early
- uses `DATABASE_URL` when set
- falls back to SQLite at `DATA_DIR/tracks.db`
- applies SQLite-specific `connect_args`

Do not put model definitions or query helpers here.

### `app/dependencies.py`

Shared FastAPI dependency and template helpers:

- `get_db()`
- `get_locale()`
- `get_translations()`
- `get_slim_mode()`
- `locale_template_response()`
- shared `Jinja2Templates` instance

Rendered pages should usually go through `locale_template_response()` so
language cookies, current-user injection, local-env flags, and canonical URLs
stay consistent.

### `app/models.py`

Owns ORM schema and relationships only.

Current domain objects:

- `Track`
- `Rating`
- `UpdateLog`
- `RankHistory`
- `Playlist`
- `PlaylistTrack`
- `User`
- `Lyric`
- `Producer`
- `Voicebank`
- `track_producers` and `track_voicebanks` junction tables

Small serialization helpers like `Track.to_dict()` are acceptable. Request,
rendering, and workflow logic should live elsewhere.

### `app/schemas.py`

Pydantic models for API validation and response typing:

- ratings
- tracks
- playlists
- users/profile updates
- tokens

Use this when an HTTP payload or response shape needs validation.

### `app/crud.py`

Database access layer. This file owns "how to query or mutate persistent data".

Current responsibility groups:

- track create/update/filter/count
- producer/voicebank relationship sync
- ratings and rating statistics
- update logs
- playlists, playlist tracks, import/export, reorder
- playlist and recently-added snapshots
- recommendations
- users and profile/admin status

Keep user-owned queries scoped by `user_id`. If a route checks ownership, the
database operation should usually enforce the same constraint.

### `app/auth.py` and `app/security.py`

Auth primitives:

- password hashing and verification
- user lookup by email or username
- JWT creation
- current-user and optional-current-user dependencies
- local auth auto-user behavior
- token/security constants

Routers should call these helpers instead of duplicating auth behavior.

### `app/scraper.py`

Vocaloard integration:

- fetches English and Japanese ranking pages
- parses ranking rows
- returns normalized track dictionaries

This module talks to the external site. It should not know about FastAPI route
responses or template rendering.

### `app/vocadb.py`

VocaDB integration:

- artist search
- song search with Japanese-title fallback
- lyric fetch and normalization

This module owns VocaDB request details. Caching/persistence belongs in CRUD or
route/service coordination.

## Routers

Routers translate HTTP requests into dependency resolution, CRUD/service calls,
and HTTP responses. They should coordinate, validate request-level behavior, and
delegate heavier work.

### `app/routers/auth.py`

Authentication and profile endpoints:

- `POST /token`
- `POST /users/`
- `GET /users/me/`
- `POST /logout`
- `PUT /api/users/me/profile`

Uses `auth.py`, `crud.py`, and shared dependencies.

### `app/routers/pages.py`

Server-rendered HTML pages:

- main chart
- rated tracks
- recently added
- recommendations
- playlists and playlist edit/view pages
- options/login/register/about/explore
- profiles index and public profile pages
- producer and voicebank index/detail pages
- `robots.txt`

This router is allowed to prepare template context, but reusable formatting,
pagination, and filtering helpers should move to `app/utils/` or `app/crud.py`.

### `app/routers/tracks.py`

Track/rating/data endpoints used by the frontend:

- partial track table HTML JSON responses
- playlist track partials
- recently-added partials
- rating backup/restore
- JS translations endpoint
- create/delete rating
- playlist membership status
- snapshot endpoints for pagination/player state

This router is the bridge between `app/static/js/main.js` and the database.

### `app/routers/playlists.py`

Playlist API:

- list/create/update/delete playlists
- add/remove/reorder tracks
- bulk playlist import/export
- single playlist import/export

Ownership checks should remain centered on `current_user.id`.

### `app/routers/scraping.py`

Scraping and scheduled task endpoints:

- manual scrape trigger
- Vercel cron scrape
- Vercel cron bot task
- scrape status

The route starts or schedules work. `app/services/scraping.py` owns the scrape
workflow.

### `app/routers/vocadb.py`

Lyrics and VocaDB lookup endpoints:

- cached/local lyrics response
- VocaDB artist search
- VocaDB song search
- direct VocaDB lyric fetch

The external request logic belongs in `app/vocadb.py`; this router coordinates
cache lookup and persistence.

### `app/routers/sitemap.py`

SEO sitemap endpoint:

- builds `/sitemap.xml`
- includes public pages, public profiles, public playlists, producers, and
  voicebanks
- caches the XML briefly in-process

Uses `PUBLIC_BASE_URL` from `app/config.py`.

## Services

### `app/services/scraping.py`

Background scrape orchestration:

- in-process initial scrape status flag
- scrape status file read/write
- empty-database initial scrape
- smart scrape/update flow
- rank history snapshotting
- database updates through CRUD

Use services when logic is not HTTP-specific, is reusable from startup and
routes, or coordinates several steps.

## Utilities

### `app/utils/view_helpers.py`

Shared view/rendering helpers:

- track serialization for templates
- producer/voicebank option collection
- page limit/offset calculation
- partial track table rendering
- `time_ago` Jinja filter

### `app/utils/uploads.py`

Upload helpers:

- chunked upload reads
- max-size enforcement

Use this for import/restore endpoints instead of reading uploaded files directly.

## Templates And Static Assets

### `app/templates/`

Jinja templates for server-rendered UI.

Conventions:

- full pages live at the template root
- reusable fragments live in `partials/`
- macros live in `macros/`
- templates expose frontend state mainly through `data-*` attributes

Preserve `data-*` contracts when changing templates; the vanilla JS depends on
them heavily.

### `app/static/`

Source frontend assets:

- `js/global.js`
- `js/main.js`
- `js/options.js`
- `js/playlist_editor.js`
- `js/playlists_page.js`
- `js/idb-helper.js`
- `css/input.css`
- icons, manifests, service worker

Templates load generated files such as `js/*.min.js` and `css/app.css`. Those
build outputs are ignored by git. Edit source files, then run the relevant build
script when local rendering needs the generated assets.

## Internationalization

- Supported locales are `en` and `ja`.
- Locale resolution lives in `app/dependencies.py`.
- Python and Jinja strings are extracted through `babel.cfg`.
- JavaScript strings are collected into `locales/js_translations.json` by
  `scripts/extract_js_messages.py`.
- Compiled `.mo` files are generated artifacts.

Use `locale_template_response()` for rendered pages so locale, current user, and
canonical URL behavior stay consistent.

## Request Flows

### HTML Page

```text
browser
  -> app/routers/pages.py
  -> dependencies for db/current user/locale/translations
  -> crud/view helper calls
  -> locale_template_response()
  -> Jinja template
```

### Track Table Partial

```text
frontend fetch
  -> app/routers/tracks.py
  -> crud.get_tracks_count() / crud.get_tracks()
  -> app/utils/view_helpers.py
  -> JSON containing rendered table HTML and pagination metadata
```

### Rating Or Playlist Mutation

```text
frontend form/fetch
  -> auth dependency resolves current user
  -> tracks/playlists router validates request
  -> crud mutation scoped by user_id
  -> JSON or status response
```

### Lyrics Lookup

```text
frontend fetch
  -> app/routers/vocadb.py
  -> local DB lyric cache check
  -> app/vocadb.py external lookup if needed
  -> optional DB persistence
  -> JSON response
```

### Scraping

```text
startup or scrape route
  -> app/services/scraping.py
  -> app/scraper.py external fetch/parse
  -> app/crud.py / ORM session
  -> status file and update log
```

### Vercel

```text
Vercel request
  -> api/index.py
  -> app.main:app
  -> normal FastAPI routing
```

## Docs, Scripts, And Packaging

### `scripts/`

- `update_docs.py`: starts FastAPI, fetches OpenAPI, regenerates API/db/README
  docs
- `generate_db_docs.py`: writes DB schema docs from SQLAlchemy models
- `generate_readme_docs.py`: extracts Docusaurus docs from README sections
- `extract_js_messages.py`: updates JS translation keys
- `manage_users.py`: CLI user/admin maintenance
- `bot_daily_top.py`: ranking analysis and Discord/Bluesky posting

### `docs/`

Docusaurus site. It is a separate Node project and consumes generated docs under
`docs/docs/` plus `docs/static/openapi.json`.

### Deployment And Packaging

- Docker builds translations and static assets in a builder stage.
- Vercel uses `api/index.py` and `vercel.json` rewrites/crons.
- PyInstaller packaging is configured by `vocaloid-rate.spec`.
- `entrypoint.sh` adjusts mounted `data/` ownership before starting Docker.

## Where New Code Should Go

### New HTML Page

Usually:

- route in `app/routers/pages.py`
- template in `app/templates/`
- data queries in `app/crud.py`
- reusable context/rendering helpers in `app/utils/view_helpers.py`

If `pages.py` becomes unwieldy for the feature area, create a new page router
instead of moving logic into `main.py`.

### New JSON/API Endpoint

Usually:

- route in the matching `app/routers/` module
- request/response schemas in `app/schemas.py`
- database logic in `app/crud.py`
- multi-step workflow in `app/services/`

### New Database Entity

Usually:

- ORM model in `app/models.py`
- Pydantic shape in `app/schemas.py`
- CRUD functions in `app/crud.py`
- Alembic migration in `alembic/versions/`
- route/service tests near the changed layer

Migrations must work with SQLite and Postgres.

### New External Integration

Usually:

- focused integration module in `app/<integration>.py`
- service wrapper if the workflow has multiple steps
- router only if the app exposes HTTP endpoints for it
- tests with mocked network calls

### New Shared Dependency

Put it in:

- `app/dependencies.py` for FastAPI/request/template/i18n dependencies
- `app/config.py` for environment-derived behavior
- `app/constants.py` for shared constants/paths
- `app/utils/` for small reusable helpers

## Testing Map

Important test behavior:

- tests use in-memory SQLite
- `tests/conftest.py` sets `DATABASE_URL` and `SECRET_KEY`
- `client_factory` disables lifespan so route tests avoid startup migrations and
  background scrape work
- network integrations are monkeypatched, not called live

Current test areas:

- `test_main*.py`: app wiring and lifespan
- `test_app_behavior.py`: compatibility/regression behavior
- `test_auth*.py`: auth routes and auth helpers
- `test_config_and_module_setup.py`: environment/module setup branches
- `test_dependencies*.py`: locale/template/db dependencies
- `test_crud*.py`: query/mutation behavior
- `test_pages*.py`: rendered pages
- `test_tracks_api*.py`: track/rating/snapshot APIs
- `test_playlists_api*.py`: playlist APIs
- `test_scraping.py` and `test_services_scraping.py`: scrape routes/workflows
- `test_vocadb*.py`: VocaDB integration and router behavior
- `test_profile.py`: profile/visibility behavior
- `test_seo.py`: robots, canonical URLs, sitemap, public pages

Add tests at the layer where behavior lives. Prefer focused tests over broad
end-to-end coverage unless the change crosses module boundaries.

## Architectural Checklist

Before adding or moving code, ask:

1. Is it HTTP-specific?
   Put it in a router.

2. Is it mostly querying or mutating the database?
   Put it in `crud.py`.

3. Is it a multi-step workflow or background task?
   Put it in `services/`.

4. Is it an external API/scrape detail?
   Put it in an integration module.

5. Is it request dependency, locale, or template glue?
   Put it in `dependencies.py`.

6. Is it a reusable pure or near-pure helper?
   Put it in `utils/`.

7. Is it app startup, middleware, or router registration?
   Keep it in `main.py`.

Following these boundaries keeps the app split readable and prevents the old
single-module shape from returning.
