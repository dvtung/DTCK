"""Shared test fixtures (root conftest).

``.env`` may carry a production ``API_AUTH_KEY`` (T015); the auth middleware
reads it per request, which would 401 every offline POST in the suite. Reset it
for tests — ``test_t015_hardening.py`` re-enables it explicitly per test.
"""

from __future__ import annotations

import pytest

from apps.api.config import settings


@pytest.fixture(autouse=True)
def _offline_api_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_auth_key", "")
