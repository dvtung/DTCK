from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.market_data import MarketService
from src.agents.tools import ToolCatalog


class _RagStub:
    def evidence_for(self, query: str, *, top_k: int = 3):
        return []

    def evidence_payload(self, evidence):
        return []


client = TestClient(app)


def test_tool_prediction_is_available() -> None:
    tools = ToolCatalog(MarketService(), _RagStub())
    result = tools.call("get_prediction", symbol="FPT")
    assert result["available"] is True
    assert 0.0 <= result["probability_positive"] <= 1.0
    assert "model_id" in result


def test_login_route_returns_token() -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@dtck.local", "password": "admin123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_monitoring_alerts_route() -> None:
    resp = client.get("/api/v1/monitoring/alerts", params={"symbols": "FPT,VCB"})
    assert resp.status_code == 200
    body = resp.json()
    assert "alerts" in body
    assert isinstance(body["alerts"], list)


# ------------------------------------------------------------- T014 ML API
def test_prediction_endpoint_contract() -> None:
    resp = client.get("/api/v1/predictions/FPT")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "FPT"
    assert body["available"] is True if "available" in body else True
    assert 0.0 <= body["probability_positive"] <= 1.0
    assert body["horizon_days"] > 0
    assert "model_id" in body and "model_version" in body


def test_prediction_endpoint_unknown_symbol_404() -> None:
    resp = client.get("/api/v1/predictions/NOPE")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


def test_prediction_evaluations_endpoint() -> None:
    resp = client.get("/api/v1/predictions/FPT/evaluations", params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 5
    assert body["total"] == 0


def test_prediction_evaluations_unknown_symbol_404() -> None:
    resp = client.get("/api/v1/predictions/NOPE/evaluations")
    assert resp.status_code == 404


def test_train_model_cli_reports_single_class_fixture_honestly() -> None:
    """T014 worker CLI: on the synthetic fixture training is rejected (KI-008)."""
    from apps.worker.cli import main

    rc = main(["train-model"])
    assert rc == 1


def test_worker_cli_train_model_help() -> None:
    from apps.worker.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["train-model", "--horizon", "10"])
    assert args.horizon == 10
    assert args.func.__name__ == "train_model"


def test_prediction_validation_endpoint_matches_schema() -> None:
    resp = client.get("/api/v1/predictions/VCB/validation")
    assert resp.status_code == 200
    body = resp.json()
    # PredictionOut contract fields
    assert set(body) >= {
        "symbol", "trade_date", "model_id", "model_version", "feature_version",
        "target", "horizon_days", "probability_positive", "confidence", "calibrated",
    }
    assert body["symbol"] == "VCB"
    assert isinstance(body["calibrated"], bool)
