"""Polls the lists of a Yasl account."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import YaslApi, YaslAuthError, YaslError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type YaslConfigEntry = ConfigEntry[YaslCoordinator]


def is_auth_failure(err: ClientResponseError) -> bool:
    """A refresh token Yasl rejected (revoked, expired): the user has to sign in again."""
    return err.status in (400, 401)


class YaslCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """All lists of the account by id, each with its items (one request per update)."""

    config_entry: YaslConfigEntry

    def __init__(self, hass: HomeAssistant, entry: YaslConfigEntry, api: YaslApi) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            lists = await self.api.async_get_lists()
        except ConfigEntryAuthFailed:
            # Newer Home Assistant versions raise this themselves when the token refresh is refused
            raise
        except YaslAuthError as err:
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="auth_failed") from err
        except ClientResponseError as err:
            # Token refresh failed (raised by Home Assistant's OAuth session)
            if is_auth_failure(err):
                raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="auth_failed") from err
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed", translation_placeholders={"error": str(err)}
            ) from err
        except (YaslError, ClientError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed", translation_placeholders={"error": str(err)}
            ) from err
        return {shopping_list["id"]: shopping_list for shopping_list in lists}
