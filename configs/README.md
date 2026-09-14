# configs/

Runtime configuration. Secrets NEVER live here (see `.env` / secret store).

## Files

- `scoring_weights.yaml` — baseline multi-factor weights (spec §12, versioned).
- `sources.yaml` — data provider registry (T002; design in `docs/DATA_SOURCES.md`):
  provider ids, roles, auth model, credential env-var **names** (never values),
  enabled/priority flags, per-domain selection and fallback chains.
- Placeholder for future: `universe.yaml` (VN30/VN100 memberships snapshot),
  `agents.yaml` (agent registry).

## Scoring weights

The baseline weights are **assumptions to be validated by backtesting** (§12).
Changing weights = new `scoring_version`, never an in-place edit of a deployed version.