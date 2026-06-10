---
name: vocaloid-git
description: Source control workflows, committing changes, and managing pre-commit hooks. Use when preparing a commit or pushing changes.
---

# 🌳 Git & Workflow

- **Pre-commit Hooks:** NEVER use `--no-verify`. Husky MUST run linting and tests.
- **Conventional Commits:** ALWAYS use the format `type(scope): message`.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
  - Scopes: `backend`, `frontend`, `docs`, `git`, `i18n`, `qa`, etc.
- **Brevity:** Use short, single-line messages. Never use long descriptions unless absolutely required for complex logic.
- **Atomic Splitting:** NEVER bundle different types of changes (e.g., docs and code) in one commit. Split them into logical, scoped commits.
- **Syncing:** Always `git pull` before starting new tasks.
- **Staging:** Be surgical with `git add`. Avoid `git add .`.
