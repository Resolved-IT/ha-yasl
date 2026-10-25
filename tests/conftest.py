"""Fixtures for the Yasl tests."""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yasl.const import API_URL, DOMAIN

USER_ID = "user-1"
LISTS_URL = f"{API_URL}/api/lists"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> Generator[None]:
    """Load custom_components/yasl in every test."""
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Config flow tests do not set up the entry."""
    with patch("custom_components.yasl.async_setup_entry", return_value=True) as mock:
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A signed-in Yasl account with a valid token."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_ID,
        title="Yasl (Anna)",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "yasl_access",
                "refresh_token": "yaslr_refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": time.time() + 3600,
                "yasl_user_id": USER_ID,
                "yasl_user_name": "Anna",
            },
        },
    )


def item(item_id: str, name: str, **values: Any) -> dict[str, Any]:
    """An item as GET /api/lists returns it."""
    return {
        "id": item_id,
        "name": name,
        "quantity": 1,
        "unit": "pcs",
        "category": "Other",
        "checked": False,
        "sortOrder": None,
        "note": None,
        "createdAt": 1,
        **values,
    }


@pytest.fixture
def lists() -> list[dict[str, Any]]:
    """Two lists: the weekly one with open, checked and sorted items, and an empty one."""
    return [
        {
            "id": "list-1",
            "name": "Wocheneinkauf",
            "items": [
                item("i-3", "Brot", createdAt=3),
                item("i-1", "Milch", quantity=2, unit="l", sortOrder=1, note="laktosefrei"),
                item("i-2", "Eier", quantity=6, sortOrder=0),
                item("i-4", "Butter", checked=True, createdAt=4),
            ],
        },
        {"id": "list-2", "name": "Baumarkt", "items": []},
    ]
