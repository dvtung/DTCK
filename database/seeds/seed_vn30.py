"""Seed VN30 baseline universe (DATABASE_SCHEMA §3.3). Idempotent upsert.

This is a *baseline* constituent list used to bootstrap the MVP universe. The
real VN30 membership changes quarterly and must be refreshed by a data feed in
Phase 1 (collectors); the seed only guarantees a known-good starting set.
"""

from __future__ import annotations

from sqlalchemy import Connection
from sqlalchemy.dialects.postgresql import insert

# (symbol, company_name, exchange, sector_code, industry_code, is_vn30)
VN30: list[tuple[str, str, str, str, str, bool]] = [
    ("ACB", "Asia Commercial Joint Stock Bank", "HOSE", "FINANCIALS", "BANKS", True),
    ("BCM", "Becamex IDC Corporation", "HOSE", "REAL_ESTATE", "REALESTATE_DEV", True),
    ("BID", "Bank for Investment and Development of Vietnam", "HOSE", "FINANCIALS", "BANKS", True),
    ("BVH", "Bao Viet Holdings", "HOSE", "FINANCIALS", "INSURANCE", True),
    ("CTG", "Vietnam Joint Stock Commercial Bank for Industry and Trade", "HOSE", "FINANCIALS", "BANKS", True),  # noqa: E501
    ("FPT", "FPT Corporation", "HOSE", "TECHNOLOGY", "IT_SERVICES", True),
    ("GAS", "PetroVietnam Gas JSC", "HOSE", "ENERGY", "OIL_GAS", True),
    ("GVR", "Vietnam Rubber Group", "HOSE", "MATERIALS", "RUBBER", True),
    ("HDB", "HDBank", "HOSE", "FINANCIALS", "BANKS", True),
    ("HPG", "Hoa Phat Group", "HOSE", "MATERIALS", "STEEL", True),
    ("MBB", "Military Commercial Joint Stock Bank", "HOSE", "FINANCIALS", "BANKS", True),
    ("MSN", "Masan Group", "HOSE", "CONSUMER_STAPLES", "FOOD_BEV", True),
    ("MWG", "Mobile World Investment Corporation", "HOSE", "CONSUMER_DISCRETIONARY", "RETAIL", True),  # noqa: E501
    ("NVL", "Novaland Investment Group", "HOSE", "REAL_ESTATE", "REALESTATE_DEV", True),
    ("PLX", "Petrolimex Group", "HOSE", "ENERGY", "OIL_GAS", True),
    ("POW", "PetroVietnam Power Corporation", "HOSE", "UTILITIES", "ELECTRICITY", True),
    ("PNJ", "Phu Nhuan Jewelry JSC", "HOSE", "CONSUMER_DISCRETIONARY", "RETAIL", True),
    ("SAB", "Saigon Beer Alcohol Beverage Corporation", "HOSE", "CONSUMER_STAPLES", "FOOD_BEV", True),  # noqa: E501
    ("SHB", "Saigon-Hanoi Commercial Joint Stock Bank", "HOSE", "FINANCIALS", "BANKS", True),
    ("SSI", "SSI Securities Corporation", "HOSE", "FINANCIALS", "SECURITIES", True),
    ("STB", "Sacombank", "HOSE", "FINANCIALS", "BANKS", True),
    ("TCB", "Vietnam Technological and Commercial Joint Stock Bank", "HOSE", "FINANCIALS", "BANKS", True),  # noqa: E501
    ("TPB", "TPBank", "HOSE", "FINANCIALS", "BANKS", True),
    ("VCB", "Vietcombank", "HOSE", "FINANCIALS", "BANKS", True),
    ("VHM", "Vinhomes JSC", "HOSE", "REAL_ESTATE", "REALESTATE_DEV", True),
    ("VIC", "Vingroup JSC", "HOSE", "REAL_ESTATE", "REALESTATE_DEV", True),
    ("VJC", "Vietjet Aviation JSC", "HOSE", "INDUSTRIALS", "AIRLINES", True),
    ("VNM", "Vietnam Dairy Products JSC (Vinamilk)", "HOSE", "CONSUMER_STAPLES", "DAIRY", True),
    ("VPB", "VPBank", "HOSE", "FINANCIALS", "BANKS", True),
    ("VRE", "Vincom Retail JSC", "HOSE", "REAL_ESTATE", "REALESTATE_DEV", True),
]


def seed_vn30(
    conn: Connection,
    exchanges: dict[str, int],
    sectors: dict[str, int],
    industries: dict[str, int],
) -> int:
    """Upsert VN30 constituent rows into ``stocks``; returns number upserted."""
    from src.common.models.reference import Stock

    exchange = Stock.__table__.c.exchange_id
    updated = 0
    for symbol, name, exchange_code, sector_code, industry_code, is_vn30 in VN30:
        stmt = (
            insert(Stock)
            .values(
                symbol=symbol,
                exchange_id=exchanges[exchange_code],
                company_name=name,
                sector_id=sectors[sector_code],
                industry_id=industries[industry_code],
                status="ACTIVE",
                is_vn30=is_vn30,
                is_vn100=False,
            )
            .on_conflict_do_update(
                index_elements=[Stock.symbol, exchange],
                set_={
                    "company_name": name,
                    "sector_id": sectors[sector_code],
                    "industry_id": industries[industry_code],
                    "is_vn30": is_vn30,
                },
            )
        )
        conn.execute(stmt)
        updated += 1
    return updated
