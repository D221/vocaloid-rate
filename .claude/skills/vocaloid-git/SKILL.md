---
name: vocaloid-git
description: Source control workflows, committing, and pre-commit hooks
---

# 🌳 Git & Workflow

- **Pre-commit Hooks:** NEVER use `--no-verify`. Husky MUST run linting and tests before commit.
- **Conventional Commits:** ALWAYS use the format `type(scope): message`.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
  - Scopes: `backend`, `frontend`, `docs`, `git`, `i18n`, `qa`, etc.
- **Brevity:** Short, single-line messages. Avoid long descriptions unless absolutely required.
- **Atomic Splitting:** NEVER bundle different types of changes (e.g., docs and code) in one commit. Split into logical, scoped commits.
- **Syncing:** Always `git pull --rebase` before starting new tasks.
- **Staging:** Be surgical with `git add`. Avoid `git add .`.
