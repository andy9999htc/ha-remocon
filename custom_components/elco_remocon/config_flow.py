"""Config flow for Elco Remocon-Net."""

from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .api import RemoconAuthError, RemoconClient, RemoconConnectionError, RemoconDataError
from .const import (
    CONF_FEATURES_PAYLOAD,
    CONF_GATEWAY_ID,
    CONF_READ_STRATEGY,
    CONF_ZONE,
    DEFAULT_READ_STRATEGY,
    DEFAULT_ZONE,
    DOMAIN,
    READ_STRATEGIES,
)

_LOGGER = logging.getLogger(__name__)


class ElcoRemoconConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elco Remocon-Net."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get options flow for this handler."""
        return ElcoRemoconOptionsFlow(config_entry)

    def _build_user_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        return vol.Schema({
            vol.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, "")): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Required(CONF_GATEWAY_ID, default=defaults.get(CONF_GATEWAY_ID, "")): str,
            vol.Optional(CONF_ZONE, default=defaults.get(CONF_ZONE, DEFAULT_ZONE)): str,
            vol.Optional(CONF_READ_STRATEGY, default=defaults.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY)): vol.In(READ_STRATEGIES),
            vol.Optional(CONF_FEATURES_PAYLOAD, default=defaults.get(CONF_FEATURES_PAYLOAD, "")): str,
        })

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            features_payload = None
            features_raw = user_input.get(CONF_FEATURES_PAYLOAD, "")
            if features_raw:
                try:
                    features_payload = json.loads(features_raw)
                    if not isinstance(features_payload, dict):
                        raise ValueError("Features payload must be a JSON object")
                except ValueError:
                    errors["base"] = "invalid_features"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._build_user_schema({
                        CONF_EMAIL: user_input.get(CONF_EMAIL, ""),
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                        CONF_GATEWAY_ID: user_input.get(CONF_GATEWAY_ID, ""),
                        CONF_ZONE: user_input.get(CONF_ZONE, DEFAULT_ZONE),
                        CONF_READ_STRATEGY: user_input.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY),
                        CONF_FEATURES_PAYLOAD: features_raw,
                    }),
                    errors=errors,
                )

            try:
                client = RemoconClient(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    gateway_id=user_input[CONF_GATEWAY_ID],
                    zone=user_input.get(CONF_ZONE, DEFAULT_ZONE),
                    features_payload=features_payload,
                    read_strategy=user_input.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY),
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

                entry_data = {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_GATEWAY_ID: user_input[CONF_GATEWAY_ID],
                    CONF_ZONE: user_input.get(CONF_ZONE, DEFAULT_ZONE),
                    CONF_READ_STRATEGY: user_input.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY),
                }
                if features_payload is not None:
                    entry_data[CONF_FEATURES_PAYLOAD] = features_payload

                return self.async_create_entry(
                    title=f"Elco {user_input[CONF_GATEWAY_ID]}",
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema({}),
            errors=errors,
        )


class ElcoRemoconOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Elco Remocon-Net."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={
                CONF_READ_STRATEGY: user_input.get(
                    CONF_READ_STRATEGY,
                    self.config_entry.options.get(
                        CONF_READ_STRATEGY,
                        self.config_entry.data.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY),
                    ),
                )
            })

        current_strategy = self.config_entry.options.get(
            CONF_READ_STRATEGY,
            self.config_entry.data.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_READ_STRATEGY, default=current_strategy): vol.In(READ_STRATEGIES),
            }),
        )
