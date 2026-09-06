# DTCK — offline install procedure  (air-gapped environments)

## How to refresh the offline bundle (run on an internet-connected machine)

```bash
pip download -r requirements.txt -d ./offline_package/wheels
# pin exact versions for reproducibility:
# pip freeze > offline_package/requirements-offline.txt   (venv-based)
```

## How to install offline

```bash
pip install --no-index --find-links=./offline_package/wheels -r requirements-offline.txt
```

## Requirements for this bundle

- Python 3.12 (matching the Docker base images: `python:3.12-slim`)
- Building xgboost/lightgbm from wheels is CPU-only by default
- See `helper/resources.md` for the dependency matrix