"""T015 tests — API-key auth middleware, /metrics, train-model --source (§32/§46)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api import metrics as app_metrics
from apps.api.config import settings
from apps.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_metrics() -> None:
    app_metrics.reset()
    yield
    app_metrics.reset()


# ------------------------------------------------------------------ auth (§32)
class TestApiKeyAuth:
    @pytest.fixture()
    def keyed_client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        monkeypatch.setattr(settings, "api_auth_key", "s3cret-key")
        return TestClient(app)

    def test_disabled_by_default_keeps_post_open(self) -> None:
        """Without API_AUTH_KEY the demo/test behavior is unchanged."""
        assert settings.api_auth_key == ""
        r = client.post("/api/v1/agents/analyze", json={"symbol": "VCB"})
        assert r.status_code == 200

    def test_post_without_key_is_401(self, keyed_client: TestClient) -> None:
        r = keyed_client.post("/api/v1/agents/analyze", json={"symbol": "VCB"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
        assert r.headers.get("www-authenticate") == "Bearer"

    def test_post_with_wrong_key_is_401(self, keyed_client: TestClient) -> None:
        r = keyed_client.post(
            "/api/v1/agents/analyze",
            json={"symbol": "VCB"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert r.status_code == 401

    def test_post_with_valid_key_succeeds(self, keyed_client: TestClient) -> None:
        r = keyed_client.post(
            "/api/v1/agents/analyze",
            json={"symbol": "VCB"},
            headers={"Authorization": "Bearer s3cret-key"},
        )
        assert r.status_code == 200

    def test_get_is_not_gated(self, keyed_client: TestClient) -> None:
        """Read paths stay open — the dashboard only issues GETs."""
        assert keyed_client.get("/api/v1/stocks/ranked").status_code == 200

    def test_login_stays_open(self, keyed_client: TestClient) -> None:
        """The login endpoint is how a caller obtains its first credential."""
        r = keyed_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@dtck.local", "password": "admin123"},
        )
        assert r.status_code == 200

    def test_health_probes_stay_open(self, keyed_client: TestClient) -> None:
        assert keyed_client.get("/healthz").status_code == 200
        assert keyed_client.get("/readyz").status_code == 200

    def test_metrics_gated_when_key_set(self, keyed_client: TestClient) -> None:
        assert keyed_client.get("/metrics").status_code == 401
        r = keyed_client.get("/metrics", headers={"Authorization": "Bearer s3cret-key"})
        assert r.status_code == 200


# --------------------------------------------------------------- metrics (§46)
class TestMetricsEndpoint:
    def test_metrics_exposes_request_counters(self) -> None:
        client.get("/healthz")
        r = client.get("/metrics")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        body = r.text
        assert "# TYPE dtck_http_requests_total counter" in body
        assert 'route="/healthz"' in body
        assert "# TYPE dtck_http_request_duration_seconds histogram" in body

    def test_route_label_uses_template_not_raw_path(self) -> None:
        client.get("/api/v1/stocks/FAKE/prices")
        body = client.get("/metrics").text
        # 404s have no matched route — raw path must NOT leak into labels.
        assert "/api/v1/stocks/FAKE/prices" not in body

    def test_agent_runs_are_recorded(self) -> None:
        client.post("/api/v1/agents/analyze", json={"symbol": "VCB"})
        body = client.get("/metrics").text
        assert "# TYPE dtck_agent_runs_total counter" in body
        assert 'task="analyze"' in body
        assert "# TYPE dtck_agent_duration_seconds histogram" in body

    def test_render_is_valid_exposition_shape(self) -> None:
        app_metrics.record_request("GET", "/x", 200, 0.01)
        app_metrics.record_agent_run("analyze", "succeeded", 1.5)
        text = app_metrics.render()
        assert text.endswith("\n")
        for line in text.splitlines():
            if line and not line.startswith("#"):
                assert " " in line  # metric_name{labels} value


# ------------------------------------------------------- train-model source
class TestTrainModelSourceFlag:
    def test_source_defaults_to_memory(self) -> None:
        from apps.worker.cli import build_parser

        assert build_parser().parse_args(["train-model"]).source == "memory"

    def test_source_accepts_db(self) -> None:
        from apps.worker.cli import build_parser

        assert build_parser().parse_args(["train-model", "--source", "db"]).source == "db"

    def test_source_rejects_unknown(self) -> None:
        from apps.worker.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(["train-model", "--source", "oracle"])

    def test_resolver_returns_the_right_service(self) -> None:
        from apps.api.services.market_data import MarketService
        from apps.worker.cli import _train_market_service

        assert isinstance(_train_market_service("memory"), MarketService)
