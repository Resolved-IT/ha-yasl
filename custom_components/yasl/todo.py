"""Every Yasl list as a to-do list: check off, add, edit, sort and delete items."""

from __future__ import annotations

import re
from collections.abc import Awaitable
from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import YaslDailyLimitError, YaslError
from .const import APP_URL, DEFAULT_UNIT, DOMAIN
from .coordinator import YaslConfigEntry, YaslCoordinator

PARALLEL_UPDATES = 0

# "Milch (2 l)", "Eier (6×)", "Mehl (1,5 kg)"
_SUMMARY = re.compile(r"^(?P<name>.*?\S)\s*\((?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>[×x]|[^\d\s()][^()]*)?\)\s*$")


def format_quantity(quantity: float) -> str:
    """1 → "1", 1.5 → "1.5"."""
    return str(int(quantity)) if float(quantity).is_integer() else f"{quantity:g}"


def format_summary(name: str, quantity: float | None, unit: str | None) -> str:
    """Name with quantity and unit unless it is a single piece."""
    unit = unit or DEFAULT_UNIT
    if quantity is None or (quantity == 1 and unit == DEFAULT_UNIT):
        return name
    if unit == DEFAULT_UNIT:
        return f"{name} ({format_quantity(quantity)}×)"
    return f"{name} ({format_quantity(quantity)} {unit})"


def parse_summary(summary: str) -> tuple[str, float, str]:
    """Name, quantity and unit of a summary written by format_summary or by the user; without a suffix one piece."""
    summary = summary.strip()
    match = _SUMMARY.match(summary)
    if not match:
        return summary, 1, DEFAULT_UNIT
    quantity = float(match["quantity"].replace(",", "."))
    unit = (match["unit"] or "").strip()
    if unit in ("", "×", "x"):
        unit = DEFAULT_UNIT
    if quantity <= 0:
        return summary, 1, DEFAULT_UNIT
    return match["name"].strip(), quantity, unit


def ordered_items(shopping_list: dict[str, Any]) -> list[dict[str, Any]]:
    """Items in the app's order: sort order, then creation."""
    return sorted(
        shopping_list.get("items", []),
        key=lambda item: (item.get("sortOrder") is None, item.get("sortOrder") or 0, item.get("createdAt") or 0),
    )


def to_todo_item(item: dict[str, Any]) -> TodoItem:
    """A Yasl item as to-do item."""
    return TodoItem(
        uid=item["id"],
        summary=format_summary(item["name"], item.get("quantity"), item.get("unit")),
        status=TodoItemStatus.COMPLETED if item.get("checked") else TodoItemStatus.NEEDS_ACTION,
        description=item.get("note") or None,
    )


async def async_setup_entry(hass: HomeAssistant, entry: YaslConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """One entity per list; lists created or deleted in Yasl come and go while Home Assistant runs."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def sync_lists() -> None:
        current = set(coordinator.data)
        if new := current - known:
            known.update(new)
            async_add_entities(YaslTodoListEntity(coordinator, list_id) for list_id in new)
        if gone := known - current:
            registry = er.async_get(hass)
            for list_id in gone:
                known.discard(list_id)
                if entity_id := registry.async_get_entity_id("todo", DOMAIN, f"{entry.unique_id}-{list_id}"):
                    registry.async_remove(entity_id)

    sync_lists()
    entry.async_on_unload(coordinator.async_add_listener(sync_lists))


class YaslTodoListEntity(CoordinatorEntity[YaslCoordinator], TodoListEntity):
    """A Yasl shopping list."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: YaslCoordinator, list_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._list_id = list_id
        self._attr_unique_id = f"{entry.unique_id}-{list_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name=entry.title,
            manufacturer="Resolved IT",
            model="Yasl",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=APP_URL,
        )

    @property
    def _list(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self._list_id)

    @property
    def available(self) -> bool:
        """Unavailable once the list is gone in Yasl."""
        return super().available and self._list is not None

    @property
    def name(self) -> str | None:
        """The list's name in Yasl (renames follow)."""
        return self._list["name"] if self._list else None

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Items of the list."""
        return [to_todo_item(item) for item in ordered_items(self._list)] if self._list else None

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Put an item on the list ("Milch (2 l)" sets quantity and unit)."""
        name, quantity, unit = parse_summary(item.summary or "")
        body: dict[str, Any] = {"name": name, "quantity": quantity, "unit": unit}
        if item.description:
            body["note"] = item.description
        created = await self._call(self.coordinator.api.async_add_item(self._list_id, body))
        if item.status == TodoItemStatus.COMPLETED and created:
            await self._call(self.coordinator.api.async_update_item(self._list_id, created["id"], {"checked": True}))
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Check off, rename or change the note; only what changed is sent."""
        current = self._find(item.uid)
        changes: dict[str, Any] = {}
        if item.summary is not None and item.summary != format_summary(current["name"], current.get("quantity"), current.get("unit")):
            name, quantity, unit = parse_summary(item.summary)
            if name != current["name"]:
                changes["name"] = name
            if quantity != current.get("quantity") or unit != (current.get("unit") or DEFAULT_UNIT):
                changes["quantity"] = quantity
                changes["unit"] = unit
        if item.status is not None and (item.status == TodoItemStatus.COMPLETED) != bool(current.get("checked")):
            changes["checked"] = item.status == TodoItemStatus.COMPLETED
        if (item.description or "") != (current.get("note") or ""):
            changes["note"] = item.description or ""
        if changes:
            await self._call(self.coordinator.api.async_update_item(self._list_id, current["id"], changes))
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items (for bought ones checking off is enough)."""
        for uid in uids:
            await self._call(self.coordinator.api.async_delete_item(self._list_id, uid))
        await self.coordinator.async_request_refresh()

    async def async_move_todo_item(self, uid: str, previous_uid: str | None = None) -> None:
        """Move an item behind another one (first when previous_uid is None)."""
        ids = [item["id"] for item in ordered_items(self._list or {})]
        if uid not in ids:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="item_not_found", translation_placeholders={"uid": uid})
        ids.remove(uid)
        ids.insert(ids.index(previous_uid) + 1 if previous_uid in ids else 0, uid)
        await self._call(self.coordinator.api.async_reorder(self._list_id, ids))
        await self.coordinator.async_request_refresh()

    def _find(self, uid: str | None) -> dict[str, Any]:
        for item in (self._list or {}).get("items", []):
            if item["id"] == uid:
                return item
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="item_not_found", translation_placeholders={"uid": str(uid)})

    async def _call[T](self, request: Awaitable[T]) -> T:
        """Run a change; Yasl's limits become messages the user understands."""
        try:
            return await request
        except YaslDailyLimitError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="daily_limit") from err
        except YaslError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request_failed", translation_placeholders={"error": str(err)}
            ) from err
