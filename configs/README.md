# configs/

Runtime configuration. Secrets NEVER live here (see `.env` / secret store).

## Files

- `scoring_weights.yaml` — baseline multi-factor weights (spec §12, versioned).
- Placeholder for future: `universe.yaml` (VN30/VN100 memberships snapshot),
  `sources.yaml` (data provider registry), `agents.yaml` (agent registry).

## Scoring weights

The baseline weights are **assumptions to be validated by backtesting** (§12).
Changing weights = new `scoring_version`, never an in-place edit of a deployed version.