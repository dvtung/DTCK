"""Router helpers: pagination and paginated responses (API_SPECIFICATION §1)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def paginate_params(limit: int, offset: int) -> tuple[int, int]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return limit, offset


def page_of[T](items: list[T], total: int, limit: int, offset: int) -> dict[str, Any]:
    """Slice ``items`` into a paginated envelope honoring limit/offset.

    Returned as a plain dict (not a ``Page`` model) so callers can serve any
    row shape — pagination is structural, content is governed per-route.
    """
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def not_found(kind: str, value: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "not_found",
                "message": f"{kind} {value!r} not found",
            }
        },
    )
