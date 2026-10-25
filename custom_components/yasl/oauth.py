"""Sign-in with Yasl: OAuth 2.1 with PKCE and Yasl's built-in client for this integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow

from .const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, TOKEN_URL


class YaslImplementation(config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce):
    """Public client: no secret, every user authorizes it on Yasl's consent page."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the implementation."""
        super().__init__(hass, DOMAIN, CLIENT_ID, AUTHORIZE_URL, TOKEN_URL)

    @property
    def name(self) -> str:
        """Name shown when several implementations exist."""
        return "Yasl"


@callback
def async_register_implementation(hass: HomeAssistant) -> None:
    """Register a fresh implementation (each sign-in gets its own PKCE verifier)."""
    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, YaslImplementation(hass))
