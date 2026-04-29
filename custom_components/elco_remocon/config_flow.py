"""Config flow for Elco Remocon-Net."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .api import RemoconAuthError, RemoconClient, RemoconConnectionError, RemoconDataError
from .const import CONF_GATEWAY_ID, CONF_ZONE, DEFAULT_ZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ElcoRemoconConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elco Remocon-Net."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = RemoconClient(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    gateway_id=user_input[CONF_GATEWAY_ID],
                    zone=user_input.get(CONF_ZONE, DEFAULT_ZONE),
                )
                await self.hass.async_add_executor_job(client.login)
                # Verify we can actually get data
                await self.hass.async_add_executor_job(client.get_data)
            except RemoconAuthError as err:
                _LOGGER.error("Authentication error during setup: %s", err)
                errors["base"] = "auth"
            except RemoconConnectionError as err:
                _LOGGER.error("Connection error during setup: %s", err)
                errors["base"] = "connection"
            except RemoconDataError as err:
                _LOGGER.error("Data error during setup: %s", err)
                errors["base"] = "no_data"
            except Exception as err:
                _LOGGER.exception("Unexpected exception during setup: %s", err)
                errors["base"] = "no_data"
            else:
                await self.async_set_unique_id(user_input[CONF_GATEWAY_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Elco {user_input[CONF_GATEWAY_ID]}",
                    data=user_input,
                )

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_GATEWAY_ID): str,
            vol.Optional(CONF_ZONE, default=DEFAULT_ZONE): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
