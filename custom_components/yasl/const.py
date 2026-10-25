"""Constants for the Yasl integration."""

import logging
from datetime import timedelta

DOMAIN = "yasl"
LOGGER = logging.getLogger(__package__)

API_URL = "https://yasl-api.resolved-it.de"
APP_URL = "https://yasl-app.resolved-it.de"
AUTHORIZE_URL = f"{APP_URL}/oauth/authorize"
TOKEN_URL = f"{API_URL}/oauth/token"

# Built-in public client of this integration (PKCE); Yasl lets every user authorize it
CLIENT_ID = "home-assistant-yasl"
SCOPES = ["lists:read", "lists:write"]

# Reads of this integration do not count against Yasl's free daily quota; changes do
UPDATE_INTERVAL = timedelta(seconds=30)

# Extra fields of Yasl's token response
TOKEN_USER_ID = "yasl_user_id"
TOKEN_USER_NAME = "yasl_user_name"

DEFAULT_UNIT = "pcs"
