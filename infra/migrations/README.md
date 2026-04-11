# Migrations

Phase 0 establishes the migration path. Alembic is configured and ready, even though no domain tables have been defined yet.

Planned next steps:

1. Add canonical domain tables
2. Create the initial revision
3. Apply migrations against SQLite or PostgreSQL

Example commands:

```bash
conda run -n py311 alembic revision -m "init core tables"
conda run -n py311 alembic upgrade head
```
