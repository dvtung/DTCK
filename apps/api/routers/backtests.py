"""/api/v1/backtests (API_SPECIFICATION §2.10)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found, page_of, paginate_params
from apps.api.schemas import BacktestMetricOut, BacktestOut, BacktestTradeOut

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


class BacktestCreate(BaseModel):
    strategy_name: str
    strategy_version: str = "0.1.0"
    universe: str = "VN30"
    start_date: str
    end_date: str
    run_type: str = "walk-forward"


@router.get("", response_model=dict)
def list_backtests(
    service: MarketDep,
    limit: int = Query(default=20),
    offset: int = Query(default=0),
) -> dict[str, Any]:
    rows = service.list_backtests()
    limit, offset = paginate_params(limit, offset)
    return page_of(rows, len(rows), limit, offset)


@router.post("", response_model=dict, status_code=201)
def create_backtest(body: BacktestCreate, service: MarketDep) -> dict[str, Any]:
    """Create and persist a backtest execution run (§11.1/§16).

    In DB mode (DbMarketService), persists a genuine Backtest record into
    TimescaleDB. In memory mode, returns a deterministic accepted payload.
    """
    import uuid
    from datetime import date
    from decimal import Decimal

    from apps.api.services.db_market import DbMarketService

    bt_uuid = uuid.uuid4()
    bt_id_str = str(bt_uuid)

    if isinstance(service, DbMarketService):
        from apps.api.db import session_factory
        from src.common.models.backtest import Backtest

        with session_factory() as session:
            row = Backtest(
                id=bt_uuid,
                strategy_name=body.strategy_name,
                strategy_version=body.strategy_version,
                universe=body.universe,
                start_date=date.fromisoformat(body.start_date),
                end_date=date.fromisoformat(body.end_date),
                run_type=body.run_type,
                transaction_cost_bps=Decimal("15.0"),
                slippage_bps=Decimal("5.0"),
                params={},
            )
            session.add(row)
            session.commit()

    return {"id": bt_id_str, "created": True, "body": body.model_dump()}


@router.get("/{bt_id}", response_model=BacktestOut)
def get_backtest(bt_id: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_backtest(bt_id)
    if not row:
        raise not_found("backtest", bt_id)
    return row


@router.get("/{bt_id}/metrics", response_model=list[BacktestMetricOut])
def backtest_metrics(bt_id: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_backtest(bt_id) is None:
        raise not_found("backtest", bt_id)
    return service.get_backtest_metrics(bt_id)


@router.get("/{bt_id}/trades", response_model=list[BacktestTradeOut])
def backtest_trades(bt_id: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_backtest(bt_id) is None:
        raise not_found("backtest", bt_id)
    return service.get_backtest_trades(bt_id)
