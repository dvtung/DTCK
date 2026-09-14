"""Seed exchanges (HOSE / HNX / UPCOM). Idempotent upsert on ``code``."""

from __future__ import annotations

from sqlalchemy import Connection, select
from sqlalchemy.dialects.postgresql import insert

EXCHANGES: list[tuple[str, str]] = [
    ("HOSE", "Ho Chi Minh Stock Exchange"),
    ("HNX", "Hanoi Stock Exchange"),
    ("UPCOM", "UPCoM Unlisted Public Company Market"),
]


def seed_exchanges(conn: Connection) -> dict[str, int]:
    """Upsert the three exchanges and return a mapping ``code -> id``."""
    from src.common.models.reference import Exchange

    for code, name in EXCHANGES:
        conn.execute(
            insert(Exchange)
            .values(code=code, name=name)
            .on_conflict_do_update(index_elements=[Exchange.code], set_={"name": name})
        )

    rows = conn.execute(select(Exchange.id, Exchange.code)).fetchall()
    return {code: exchange_id for exchange_id, code in rows}
