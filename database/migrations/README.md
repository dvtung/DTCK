# Alembic revisions

Initial migration: `versions/0001_initial_schema.py` (STEP 2 DATABASE DESIGN)
creates all tables from `src.common.models.Base.metadata` and converts the
time-series tables into TimescaleDB hypertables (see `docs/DATABASE_SCHEMA.md` §17).

```bash
alembic upgrade head      # apply all migrations (needs a reachable DATABASE_URL)
alembic downgrade base    # drop all tables
python -m database.seeds.run_all   # seed exchanges / sectors / industries / VN30
```