"""Shared test fixtures (root conftest).

``.env`` may carry production credentials (``API_AUTH_KEY``, ``AUTH_JWT_SECRET``)
— the auth middleware/dependencies read them per request, which would 401 every
offline POST in the suite.  Reset both for tests; ``test_t015_hardening.py`` and
``test_security_jwt.py`` re-enable them explicitly per test.
"""

from __future__ import annotations

import pytest

from apps.api.config import settings


@pytest.fixture(autouse=True)
def _offline_api_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_auth_key", "")
    monkeypatch.setattr(settings, "auth_jwt_secret", "")
