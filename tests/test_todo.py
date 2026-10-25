"""Yasl lists as to-do entities."""

from __future__ import annotations

from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.yasl.const import API_URL, UPDATE_INTERVAL
from custom_components.yasl.todo import format_summary, parse_summary

from .conftest import LISTS_URL, item

WEEKLY = "todo.yasl_anna_wocheneinkauf"
ITEMS_URL = f"{API_URL}/api/lists/list-1/items"


async def set_up(hass: HomeAssistant, entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker, lists: list[dict[str, Any]]) -> None:
    aioclient_mock.get(LISTS_URL, json={"lists": lists})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def get_items(hass: HomeAssistant) -> list[dict[str, Any]]:
    result = await hass.services.async_call(TODO_DOMAIN, "get_items", {}, target={"entity_id": WEEKLY}, blocking=True, return_response=True)
    return result[WEEKLY]["items"]


def calls(aioclient_mock: AiohttpClientMocker, method: str) -> list[tuple[str, Any]]:
    return [(str(url), data) for call_method, url, data, _ in aioclient_mock.mock_calls if call_method.lower() == method]


@pytest.mark.parametrize(
    ("name", "quantity", "unit", "summary"),
    [
        ("Milch", 1, "pcs", "Milch"),
        ("Eier", 6, "pcs", "Eier (6×)"),
        ("Milch", 2, "l", "Milch (2 l)"),
        ("Mehl", 1.5, "kg", "Mehl (1.5 kg)"),
    ],
)
def test_summary_round_trip(name: str, quantity: float, unit: str, summary: str) -> None:
    """Quantity and unit live in the summary and come back when it is edited."""
    assert format_summary(name, quantity, unit) == summary
    assert parse_summary(summary) == (name, quantity, unit)


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("Mehl (1,5 kg)", ("Mehl", 1.5, "kg")),
        ("Eier (6x)", ("Eier", 6, "pcs")),
        ("Eier (6)", ("Eier", 6, "pcs")),
        ("  Brot  ", ("Brot", 1, "pcs")),
        ("Tee (grün)", ("Tee (grün)", 1, "pcs")),
        ("(2 l)", ("(2 l)", 1, "pcs")),
    ],
)
def test_parse_what_users_type(summary: str, expected: tuple[str, float, str]) -> None:
    """Typed variants work; brackets that are no quantity stay part of the name."""
    assert parse_summary(summary) == expected


async def test_lists_become_todo_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker, lists: list[dict[str, Any]]
) -> None:
    """One entity per list, items in the app's order, open items as state."""
    await set_up(hass, config_entry, aioclient_mock, lists)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(WEEKLY).state == "3"
    assert hass.states.get("todo.yasl_anna_baumarkt").state == "0"
    assert await get_items(hass) == [
        {"uid": "i-2", "summary": "Eier (6×)", "status": "needs_action"},
        {"uid": "i-1", "summary": "Milch (2 l)", "status": "needs_action", "description": "laktosefrei"},
        {"uid": "i-3", "summary": "Brot", "status": "needs_action"},
        {"uid": "i-4", "summary": "Butter", "status": "completed"},
    ]
    _, _, _, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == "Bearer yasl_access"


async def test_add_check_off_edit_delete(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker, lists: list[dict[str, Any]]
) -> None:
    """Changes go to Yasl's item endpoints with only what changed."""
    await set_up(hass, config_entry, aioclient_mock, lists)
    aioclient_mock.post(ITEMS_URL, json=item("i-5", "Mehl"))
    aioclient_mock.patch(f"{ITEMS_URL}/i-1", json=item("i-1", "Milch"))
    aioclient_mock.delete(f"{ITEMS_URL}/i-3", status=204)

    await hass.services.async_call(
        TODO_DOMAIN, "add_item", {"item": "Mehl (1,5 kg)", "description": "Type 405"}, target={"entity_id": WEEKLY}, blocking=True
    )
    await hass.services.async_call(
        TODO_DOMAIN, "update_item", {"item": "i-1", "status": "completed"}, target={"entity_id": WEEKLY}, blocking=True
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "Milch (2 l)", "rename": "Hafermilch (3 l)", "description": ""},
        target={"entity_id": WEEKLY},
        blocking=True,
    )
    await hass.services.async_call(TODO_DOMAIN, "remove_item", {"item": ["Brot"]}, target={"entity_id": WEEKLY}, blocking=True)

    assert calls(aioclient_mock, "post") == [(ITEMS_URL, {"name": "Mehl", "quantity": 1.5, "unit": "kg", "note": "Type 405"})]
    assert calls(aioclient_mock, "patch") == [
        (f"{ITEMS_URL}/i-1", {"checked": True}),
        (f"{ITEMS_URL}/i-1", {"name": "Hafermilch", "quantity": 3, "unit": "l", "note": ""}),
    ]
    assert [url for url, _ in calls(aioclient_mock, "delete")] == [f"{ITEMS_URL}/i-3"]


async def test_move_sets_the_order(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    lists: list[dict[str, Any]],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Dragging an item in the to-do card sends the whole new order."""
    await set_up(hass, config_entry, aioclient_mock, lists)
    aioclient_mock.put(f"{ITEMS_URL}/order", json={"items": []})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "todo/item/move", "entity_id": WEEKLY, "uid": "i-3", "previous_uid": "i-2"})
    assert (await client.receive_json())["success"]
    await client.send_json_auto_id({"type": "todo/item/move", "entity_id": WEEKLY, "uid": "i-4"})
    assert (await client.receive_json())["success"]

    assert calls(aioclient_mock, "put") == [
        (f"{ITEMS_URL}/order", {"itemIds": ["i-2", "i-3", "i-1", "i-4"]}),
        (f"{ITEMS_URL}/order", {"itemIds": ["i-4", "i-2", "i-1", "i-3"]}),
    ]


async def test_daily_limit_explains_itself(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker, lists: list[dict[str, Any]]
) -> None:
    """Free accounts: when today's changes are used up the user learns why."""
    await set_up(hass, config_entry, aioclient_mock, lists)
    aioclient_mock.post(
        ITEMS_URL, status=429, json={"error": "daily_limit_reached", "message": "The free plan includes 10 API requests per day"}
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(TODO_DOMAIN, "add_item", {"item": "Mehl"}, target={"entity_id": WEEKLY}, blocking=True)

    assert err.value.translation_key == "daily_limit"


async def test_lists_come_and_go(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    lists: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A list created in Yasl appears, a deleted one is removed, renames follow."""
    await set_up(hass, config_entry, aioclient_mock, lists)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        LISTS_URL,
        json={
            "lists": [
                {**lists[0], "name": "Wocheneinkauf"},
                {"id": "list-3", "name": "Party", "items": [item("p-1", "Chips")]},
            ]
        },
    )

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("todo.yasl_anna_party").state == "1"
    assert hass.states.get("todo.yasl_anna_baumarkt") is None
    assert er.async_get(hass).async_get("todo.yasl_anna_baumarkt") is None


async def test_disconnected_in_yasl_asks_to_sign_in_again(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    lists: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A 401 (connection removed under Integrationen) starts the reauth flow and marks the lists unavailable."""
    await set_up(hass, config_entry, aioclient_mock, lists)
    aioclient_mock.clear_requests()
    aioclient_mock.get(LISTS_URL, status=401, json={"error": "invalid_api_key"})

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WEEKLY).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]
