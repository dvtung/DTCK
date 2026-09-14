"""Seed sector/industry taxonomy. Idempotent upsert on ``code``."""

from __future__ import annotations

from sqlalchemy import Connection, select
from sqlalchemy.dialects.postgresql import insert

# Top-level sectors (code, name).
SECTORS: list[tuple[str, str]] = [
    ("TECHNOLOGY", "Technology"),
    ("FINANCIALS", "Financials"),
    ("REAL_ESTATE", "Real Estate"),
    ("MATERIALS", "Materials"),
    ("ENERGY", "Energy"),
    ("CONSUMER_DISCRETIONARY", "Consumer Discretionary"),
    ("CONSUMER_STAPLES", "Consumer Staples"),
    ("INDUSTRIALS", "Industrials"),
    ("UTILITIES", "Utilities"),
    ("TELECOMMUNICATIONS", "Telecommunications"),
]

# Industries (code, name, parent sector code).
INDUSTRIES: list[tuple[str, str, str]] = [
    ("SOFTWARE", "Software & Services", "TECHNOLOGY"),
    ("IT_SERVICES", "IT Services", "TECHNOLOGY"),
    ("BANKS", "Banks", "FINANCIALS"),
    ("SECURITIES", "Capital Markets / Securities", "FINANCIALS"),
    ("INSURANCE", "Insurance", "FINANCIALS"),
    ("REALESTATE_DEV", "Real Estate Development", "REAL_ESTATE"),
    ("STEEL", "Steel & Basic Materials", "MATERIALS"),
    ("POLYMERS", "Polymers & Chemicals", "MATERIALS"),
    ("RUBBER", "Rubber & Plantations", "MATERIALS"),
    ("OIL_GAS", "Oil & Gas", "ENERGY"),
    ("RETAIL", "Retailing & E-commerce", "CONSUMER_DISCRETIONARY"),
    ("FOOD_BEV", "Food & Beverage", "CONSUMER_STAPLES"),
    ("DAIRY", "Dairy & Dairy Products", "CONSUMER_STAPLES"),
    ("AIRLINES", "Airlines", "INDUSTRIALS"),
    ("ELECTRICITY", "Electric Utilities", "UTILITIES"),
]


def seed_sectors(conn: Connection) -> tuple[dict[str, int], dict[str, int]]:
    """Upsert sectors + industries; return mappings ``code -> id`` for both."""
    from src.common.models.reference import Industry, Sector

    for code, name in SECTORS:
        conn.execute(
            insert(Sector)
            .values(code=code, name=name, parent_id=None)
            .on_conflict_do_update(index_elements=[Sector.code], set_={"name": name})
        )

    sector_rows = conn.execute(select(Sector.id, Sector.code)).fetchall()
    sector_ids = {code: sector_id for sector_id, code in sector_rows}

    for code, name, parent in INDUSTRIES:
        conn.execute(
            insert(Industry)
            .values(code=code, name=name, parent_id=sector_ids[parent])
            .on_conflict_do_update(
                index_elements=[Industry.code],
                set_={"name": name, "parent_id": sector_ids[parent]},
            )
        )

    industry_rows = conn.execute(select(Industry.id, Industry.code)).fetchall()
    industry_ids = {code: industry_id for industry_id, code in industry_rows}
    return sector_ids, industry_ids
