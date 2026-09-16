"""ML prediction endpoints (spec §2.8 / §26, docs/API_SPECIFICATION.md).

Serves predictions from the in-process registry via ``PredictionService``
(T014).  With no trained model registered, the service falls back to a
deterministic approval-grade stub (KI-008) so the contract is always honored.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from apps.api.dependencies import get_market_service
from src.ml.predictor import PredictionService
from src.ml.schemas import PredictionOut

router = APIRouter(prefix="/api/v1", tags=["predictions"])

_NOT_FOUND = {"error": {"code": "not_found", "message": "{0} not found"}}


def get_prediction_service() -> PredictionService:
    """Process-wide prediction service over the shared market fixture."""
    return PredictionService(get_market_service())


@router.get("/predictions/{symbol}")
def get_prediction(symbol: str) -> dict[str, Any]:
    """Latest P(return > 0) prediction for ``symbol`` over the model horizon."""
    symbol = symbol.strip().upper()
    service = get_prediction_service()
    result = service.predict(symbol)
    if not result.get("available"):
        raise HTTPException(
            status_code=404,
            detail=dict(
                _NOT_FOUND["error"],
                message=f"prediction for {symbol!r} unavailable: {result.get('reason', 'unknown')}",
            ),
        )
    trade_date = _latest_trade_date(symbol)
    return {
        "symbol": symbol,
        "trade_date": trade_date.isoformat(),
        "model_id": result.get("model_id", "price_direction_xgb"),
        "model_version": result.get("model_version", "1.0.0"),
        "feature_version": result.get("feature_version", "feature_v1"),
        "target": result.get("target", "P(return > 0) over 5TD"),
        "horizon_days": result.get("horizon_days", 5),
        "probability_positive": result.get("probability_positive"),
        "expected_return": result.get("expected_return"),
        "confidence": result.get("confidence", 0.0),
        "calibrated": result.get("calibrated", True),
    }


@router.get("/predictions/{symbol}/evaluations")
def get_prediction_evaluations(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """Evaluation loop records for ``symbol`` (§26).

    Evaluations require elapsed horizons; until the persistence layer is
    wired (KI-008) this reports the evaluated-state contract with an empty
    list and provenance of the fallback.
    """
    symbol = symbol.strip().upper()
    market = get_market_service()
    if market.get_stock(symbol) is None:
        raise HTTPException(
            status_code=404,
            detail=dict(_NOT_FOUND["error"], message=f"symbol {symbol!r} not found"),
        )
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": 0,
        "note": "evaluation store pending TimescaleDB wiring (KI-008)",
    }


@router.get("/predictions/{symbol}/validation")
def get_prediction_validation(symbol: str) -> dict[str, Any]:
    """Contract-validated prediction payload (response-model shape check)."""
    symbol = symbol.strip().upper()
    service = get_prediction_service()
    result = service.predict(symbol)
    if not result.get("available"):
        raise HTTPException(
            status_code=404,
            detail=dict(
                _NOT_FOUND["error"],
                message=f"prediction for {symbol!r} unavailable: {result.get('reason', 'unknown')}",
            ),
        )
    return PredictionOut(
        symbol=symbol,
        trade_date=_latest_trade_date(symbol),
        model_id=str(result.get("model_id", "price_direction_xgb")),
        model_version=str(result.get("model_version", "1.0.0")),
        feature_version=str(result.get("feature_version", "feature_v1")),
        target=str(result.get("target", "P(return > 0) over 5TD")),
        horizon_days=int(result.get("horizon_days", 5)),
        probability_positive=result.get("probability_positive"),
        expected_return=result.get("expected_return"),
        confidence=float(result.get("confidence", 0.0)),
        calibrated=bool(result.get("calibrated", True)),
    ).model_dump(mode="json")


def _latest_trade_date(symbol: str) -> date:
    prices = get_market_service().get_prices(symbol) or []
    if not prices:
        return date.today() - timedelta(days=1)
    trade_date = prices[-1].get("trade_date")
    if isinstance(trade_date, date):
        return trade_date
    return date.today() - timedelta(days=1)


__all__ = ["router", "get_prediction_service"]
