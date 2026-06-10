---
name: vocaloid-qa
description: Testing and quality assurance using Pytest and linting tools. Use when running tests, fixing bugs, or verifying CI readiness.
---

# 🧪 Testing & QA

- **Isolation:** Never make live network requests. Monkeypatch integrations.
- **Environment:** Use in-memory SQLite from `tests/conftest.py`.
- **Layered Testing:** Add tests near the layer changed (CRUD, Pages, etc.).
- **CI Readiness:** Follow `AGENTS.md` standards: ensure `bun run lint` and `bun run test` pass.
