# scripts/

Operational scripts (repo root cwd assumed).

Planned:
- `bootstrap.sh`      — create .env from .env.example, init pre-commit
- `run_collector.sh`  — one-off data collection (wraps `apps.worker.cli`)
- `backtest_cli.py`   — run a backtest from config (Phase 3)
- `train_cli.py`      — train + register a model (Phase 6)
- `export_offline.sh` — regenerate offline_package wheels

No scripts are implemented yet — they arrive with their phases (T002+).