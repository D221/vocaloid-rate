# Project Structure

This document explains the current backend structure after the `app/main.py` refactor.

## High-Level Layout

```text
app/
  main.py
  constants.py
  dependencies.py
  config.py
  database.py
  auth.py
  security.py
  crud.py
  models.py
  schemas.py
  scraper.py
  vocadb.py
  routers/
  services/
  utils/
  templates/
  static/
tests/
```

## Core Rule

`app/main.py` should stay small.

It is only responsible for:

- creating the FastAPI app
- lifespan startup/shutdown logic
- middleware
- static file mounting
- shared Jinja filter registration
- router registration

Business logic and route handlers should not grow back into `main.py`.

## Backend Responsibilities

### `app/main.py`

Entry point and app wiring.

Keep here:

- `FastAPI(...)`
- middleware
- startup/lifespan behavior
- `app.include_router(...)`
- static/service worker setup

Avoid adding:

- page handlers
- API handlers
- database queries
- scraping logic

### `app/constants.py`

Shared constants and filesystem/resource paths.

Examples:

- `BASE_DIR`
- `STATIC_DIR`
- `SCRAPE_STATUS_FILE`
- upload and pagination defaults

Use this when a value is reused across modules and is not request-specific.

### `app/dependencies.py`

Shared FastAPI dependencies and template/i18n helpers.

Examples:

- `get_db`
- `get_locale`
- `get_translations`
- `get_slim_mode`
- `locale_template_response`

Use this for dependency-injected helpers that are shared across routers.

### `app/routers/`

FastAPI route modules. Each file should primarily translate HTTP requests into calls to CRUD/services/helpers.

Current split:

- `auth.py`: login, register, logout, user status fragment
- `scraping.py`: scrape trigger, cron scrape, scrape status
- `vocadb.py`: lyrics and VocaDB lookups
- `playlists.py`: playlist CRUD and playlist import/export
- `tracks.py`: ratings, partial track data, snapshots, rating backup/restore
- `pages.py`: HTML-rendering routes

Rule:

- routers should coordinate
- routers should validate request-level behavior
- routers should not contain heavy domain logic when that logic can live in services/helpers

### `app/services/`

Business logic and background-task orchestration.

Current:

- `scraping.py`

Use services when logic:

- is not HTTP-specific
- may be reused by multiple routes/startup tasks
- performs a workflow with multiple steps

### `app/utils/`

Small shared helpers that do not belong to a router or service.

Current:

- `uploads.py`: upload-size handling
- `view_helpers.py`: shared pagination/rendering/view helpers

Use utils for pure or near-pure helper logic with low coupling.

### `app/crud.py`

Database query and mutation layer.

This module should hold:

- track queries
- playlist queries
- rating queries
- recommendation/statistics queries
- user CRUD

Rule:

- if the logic is mainly “how to query/update the database”, it belongs here
- if the logic is mainly “how to handle an HTTP request”, it belongs in a router
- if the logic is mainly “how to orchestrate a workflow”, it belongs in a service

### `app/models.py`

SQLAlchemy ORM models.

Keep schema/relationship definitions here only. Avoid adding request logic or formatting logic beyond small model-local helpers like `to_dict()`.

### `app/schemas.py`

Pydantic request/response models.

Use this for API payload validation and response typing.

### `app/auth.py` and `app/security.py`

Authentication primitives.

Keep here:

- token creation
- current-user resolution
- password hashing/verification
- auth-specific helpers

### `app/scraper.py` and `app/vocadb.py`

External integration modules.

These talk to outside data sources. They should stay focused on integration details, not route behavior.

## Frontend-Related Directories

### `app/templates/`

Jinja templates for server-rendered pages and partials.

Suggested convention:

- full pages in the top-level template directory
- reusable fragments in `partials/`
- macro-only templates in `macros/`

### `app/static/`

Frontend assets:

- JS
- CSS
- icons
- service worker

## Request Flow

Most routes should follow this pattern:

```text
Request
  -> router
  -> dependency resolution
  -> crud/service/helper calls
  -> template or JSON response
```

Typical examples:

### HTML page

```text
browser request
  -> app/routers/pages.py
  -> app/dependencies.py for locale/user/template helpers
  -> app/crud.py for data
  -> Jinja template response
```

### JSON API

```text
frontend fetch
  -> app/routers/tracks.py or playlists.py
  -> app/crud.py
  -> JSON response
```

### Background scrape

```text
startup or /scrape route
  -> app/services/scraping.py
  -> app/scraper.py
  -> app/crud.py / ORM session
  -> status file updates
```

## Where New Code Should Go

### Add a new HTML page

Usually:

- route in `app/routers/pages.py`
- template in `app/templates/`
- helper logic in `app/utils/view_helpers.py` or `app/crud.py`

### Add a new JSON/API endpoint

Usually:

- route in the matching file under `app/routers/`
- database logic in `app/crud.py`
- workflow logic in `app/services/` if it is multi-step

### Add a new external integration

Usually:

- integration module like `app/<integration>.py`
- service wrapper if the flow is larger than a simple fetch
- router endpoints only if the app exposes that integration directly

### Add a new cross-router dependency

Put it in:

- `app/dependencies.py` if it is request/dependency related
- `app/constants.py` if it is just shared configuration
- `app/utils/` if it is a general helper

## Current Architectural Boundaries

These are intentional:

- `main.py` wires the app, but does not own route logic
- routers own HTTP behavior, but not heavy workflows
- services own workflows, but not rendering
- CRUD owns database access patterns
- templates own markup

If a change crosses those boundaries, it is usually a sign the code should be split before it grows.

## Testing Map

Current test organization:

- `tests/test_app_behavior.py`: compatibility/regression checks
- `tests/test_pages.py`: page-route behavior
- `tests/test_playlists_api.py`: playlist API behavior
- `tests/test_tracks_api.py`: track/rating/snapshot behavior
- `tests/test_scraping.py`: scrape-route behavior
- `tests/test_dependencies.py`: dependency/helper behavior
- `tests/test_services_scraping.py`: scraping service behavior

When adding new features, add tests near the layer being exercised:

- route behavior: route/API test
- helper behavior: helper/dependency test
- workflow behavior: service test

## Practical Guidance

Before adding code, ask:

1. Is this HTTP-specific?
   Then it probably belongs in a router.

2. Is this mostly database querying/updating?
   Then it probably belongs in `crud.py`.

3. Is this a multi-step workflow or background task?
   Then it probably belongs in `services/`.

4. Is this reused glue or formatting logic?
   Then it probably belongs in `utils/` or `dependencies.py`.

Following those rules should keep the project from collapsing back into a single oversized module.
