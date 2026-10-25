"""Config flow: sign in with Yasl (OAuth with PKCE, consent in the Yasl app)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN, LOGGER, SCOPES, TOKEN_USER_ID, TOKEN_USER_NAME
from .oauth import async_register_implementation


class YaslFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """One entry per Yasl account; all its lists become to-do entities."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Logger of the flow."""
        return LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Ask for reading and changing lists; the user may narrow it down on Yasl's consent page."""
        return {"scope": " ".join(SCOPES)}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Start the sign-in."""
        async_register_implementation(self.hass)
        return await super().async_step_user(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The connection was disconnected in Yasl or has expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm signing in again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry for the Yasl account that allowed access."""
        token = data["token"]
        user_id = token.get(TOKEN_USER_ID)
        if not user_id:
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(user_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        self._abort_if_unique_id_configured()
        name = token.get(TOKEN_USER_NAME)
        return self.async_create_entry(title=f"Yasl ({name})" if name else "Yasl", data=data)
