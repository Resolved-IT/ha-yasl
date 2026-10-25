"""Client for the Yasl REST API."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import API_URL


class YaslError(Exception):
    """Request to Yasl failed (network, server)."""


class YaslAuthError(YaslError):
    """Access token rejected: the connection was disconnected in Yasl."""


class YaslDailyLimitError(YaslError):
    """Free daily quota used up; changes work again after midnight (German time) or with Yasl Plus."""


class YaslApi:
    """Lists and items of a Yasl account; the access token comes from Home Assistant's OAuth session."""

    def __init__(self, session: ClientSession, access_token: Callable[[], Awaitable[str]], base_url: str = API_URL) -> None:
        """Initialize the client."""
        self._session = session
        self._access_token = access_token
        self._base_url = base_url

    async def async_get_lists(self) -> list[dict[str, Any]]:
        """All lists of the account (own, shared, household) with their items, in one request."""
        data = await self._request("GET", "/api/lists")
        return data.get("lists", []) if isinstance(data, dict) else []

    async def async_add_item(self, list_id: str, item: dict[str, Any]) -> dict[str, Any]:
        """Put an item on a list (name, quantity, unit, note)."""
        return await self._request("POST", f"/api/lists/{list_id}/items", item)

    async def async_update_item(self, list_id: str, item_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Change only the fields sent; an empty note clears it, checked=true checks the item off."""
        return await self._request("PATCH", f"/api/lists/{list_id}/items/{item_id}", changes)

    async def async_delete_item(self, list_id: str, item_id: str) -> None:
        """Delete an item; one that is already gone counts as deleted."""
        await self._request("DELETE", f"/api/lists/{list_id}/items/{item_id}", allow_not_found=True)

    async def async_reorder(self, list_id: str, item_ids: list[str]) -> None:
        """Set the order of the items; items not named keep their place behind them."""
        await self._request("PUT", f"/api/lists/{list_id}/items/order", {"itemIds": item_ids})

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None, allow_not_found: bool = False) -> Any:
        headers = {"Authorization": f"Bearer {await self._access_token()}", "Accept": "application/json"}
        try:
            async with self._session.request(method, self._base_url + path, json=body, headers=headers) as response:
                if response.status == 404 and allow_not_found:
                    return None
                await _raise_for_status(response)
                text = await response.text()
                return json.loads(text) if text else None
        except ClientError as err:
            raise YaslError(f"Cannot reach Yasl: {err}") from err


async def _raise_for_status(response: ClientResponse) -> None:
    if response.status < 400:
        return
    try:
        body = await response.json()
    except (ClientError, ValueError):
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    message = (body.get("message") or body.get("error")) if isinstance(body, dict) else None
    if response.status == 401:
        raise YaslAuthError("The connection to Yasl was disconnected")
    if response.status == 429 and error == "daily_limit_reached":
        raise YaslDailyLimitError(message or "Daily limit of the free plan reached")
    raise YaslError(f"Yasl answered {response.status}: {message or response.reason}")
