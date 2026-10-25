"""Yasl shopping lists as to-do lists in Home Assistant."""

from __future__ import annotations

from aiohttp import ClientError, ClientResponseError
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import YaslApi
from .const import DOMAIN
from .coordinator import YaslConfigEntry, YaslCoordinator, is_auth_failure
from .oauth import async_register_implementation

PLATFORMS = [Platform.TODO]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Yasl's sign-in, so existing entries can refresh their tokens."""
    async_register_implementation(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: YaslConfigEntry) -> bool:
    """Set up a Yasl account: poll its lists and add one to-do entity per list."""
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(hass, entry)
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except ConfigEntryAuthFailed:
        raise
    except ClientResponseError as err:
        if is_auth_failure(err):
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="auth_failed") from err
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="cannot_connect") from err
    except ClientError as err:
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="cannot_connect") from err

    async def access_token() -> str:
        await session.async_ensure_token_valid()
        return str(session.token["access_token"])

    coordinator = YaslCoordinator(hass, entry, YaslApi(async_get_clientsession(hass), access_token))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YaslConfigEntry) -> bool:
    """Unload a Yasl account."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
