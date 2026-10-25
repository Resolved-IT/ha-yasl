"""Sign-in with Yasl: OAuth with PKCE against Yasl's built-in client."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.yasl.const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, TOKEN_URL

from .conftest import USER_ID

REDIRECT = "https://example.com/auth/external/callback"


def token(user_id: str | None = USER_ID) -> dict[str, Any]:
    """Yasl's token response."""
    response = {
        "access_token": "yasl_access",
        "refresh_token": "yaslr_refresh",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "lists:read lists:write",
        "yasl_user_name": "Anna",
    }
    if user_id:
        response["yasl_user_id"] = user_id
    return response


async def sign_in(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    flow_id: str | None = None,
) -> dict[str, Any]:
    """Run the sign-in up to the token request; returns the flow result."""
    if flow_id is None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    else:
        result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    query = parse_qs(urlparse(result["url"]).query)
    assert result["url"].startswith(AUTHORIZE_URL)
    assert query["client_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [REDIRECT]
    assert query["scope"] == ["lists:read lists:write"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) >= 43

    state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT})
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=c0de&state={state}")
    assert resp.status == 200

    aioclient_mock.clear_requests()
    aioclient_mock.post(TOKEN_URL, json=response)
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_sign_in_creates_one_entry_per_account(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator, aioclient_mock: AiohttpClientMocker
) -> None:
    """The consent in Yasl ends in an entry named after the account; the token request carries the PKCE verifier."""
    result = await sign_in(hass, hass_client_no_auth, aioclient_mock, token())

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Yasl (Anna)"
    assert result["result"].unique_id == USER_ID
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["refresh_token"] == "yaslr_refresh"
    _, _, form, _ = aioclient_mock.mock_calls[0]
    assert form["grant_type"] == "authorization_code"
    assert form["client_id"] == CLIENT_ID
    assert form["code"] == "c0de"
    assert len(form["code_verifier"]) >= 43
    assert "client_secret" not in form

    # The same account again
    again = await sign_in(hass, hass_client_no_auth, aioclient_mock, token())
    assert again["type"] is FlowResultType.ABORT
    assert again["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_token_without_account_is_refused(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without yasl_user_id accounts cannot be told apart."""
    result = await sign_in(hass, hass_client_no_auth, aioclient_mock, token(user_id=None))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_keeps_the_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Signing in again updates the token; another account is refused."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    wrong = await sign_in(hass, hass_client_no_auth, aioclient_mock, token(user_id="someone-else"), flow_id=result["flow_id"])
    assert wrong["type"] is FlowResultType.ABORT
    assert wrong["reason"] == "wrong_account"

    result = await config_entry.start_reauth_flow(hass)
    response = token() | {"access_token": "yasl_new"}
    done = await sign_in(hass, hass_client_no_auth, aioclient_mock, response, flow_id=result["flow_id"])
    assert done["type"] is FlowResultType.ABORT
    assert done["reason"] == "reauth_successful"
    assert config_entry.data["token"]["access_token"] == "yasl_new"
