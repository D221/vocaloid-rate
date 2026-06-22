---
name: vocaloid-qa
description: Testing and quality assurance with Pytest and linting tools
---

# 🧪 Testing & QA

- **Isolation:** Never make live network requests. Monkeypatch integrations (Vocaloard scraping, VocaDB, bot jobs).
- **Environment:** Use in-memory SQLite from `tests/conftest.py`.
- **Layered Testing:** Add tests near the layer changed (CRUD, Pages, API, etc.).
- **CI Readiness:** Ensure `bun run lint` and `bun run test` pass before committing.
- **Coverage gate:** `bun run test:cov` enforces 80% coverage threshold.
- **Test commands:**
  - `bun run test` — run all tests
  - `bun run test:cov` — run with coverage
  - `uv run pytest tests/test_<area>.py` — run a specific file
