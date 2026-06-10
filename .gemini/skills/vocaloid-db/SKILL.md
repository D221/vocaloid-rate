---
name: vocaloid-db
description: Database migrations using Alembic and schema management. Use when creating new database tables or altering existing columns.
---

# 🗄️ Database Migrations

- **Creation:** Use `alembic revision --autogenerate -m "description"`.
- **Batch Mode:** Ensure migrations support SQLite batch mode.
- **Compatibility:** Migrations must work for both SQLite and Postgres.
- **Validation:** Test by running `alembic upgrade head`.
