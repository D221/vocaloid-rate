---
name: vocaloid-backend
description: FastAPI backend development, SQLAlchemy models, and CRUD logic. Use when adding routes, changing database models, or updating query logic in app/crud.py.
---

# 🏗️ Backend Development

- **Portability:** Ensure all code (paths, DB connections, env lookups) supports ALL deployment modes defined in `AGENTS.md` (Local, Cloud, EXE, Docker, Vercel).
- **Routing:** Put HTTP logic in `app/routers/`. Keep `main.py` only for app wiring.
- **Data Access:** All database queries and mutations MUST live in `app/crud.py`.
- **Validation:** Use Pydantic models in `app/schemas.py` for request and response validation.
- **Security:** Always enforce `user_id` scoping for user-owned data. Use `app/auth.py` for current-user resolution.
- **Workflow:** Use `app/services/` for complex, multi-step operations.
- **Integrations**: Keep external request logic in `app/scraper.py` or `app/vocadb.py`.
