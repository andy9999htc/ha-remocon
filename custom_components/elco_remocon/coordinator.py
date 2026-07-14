"""DataUpdateCoordinator for Elco Remocon-Net."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RemoconAuthError, RemoconClient, RemoconConnectionError, RemoconData
from .const import (
    CONF_FEATURES_PAYLOAD,
    CONF_GATEWAY_ID,
    CONF_READ_STRATEGY,
    CONF_ZONE,
    DEFAULT_READ_STRATEGY,
    DEFAULT_ERROR_LOG_AFTER_FAILURES,
    DEFAULT_REQUEST_RETRY_COUNT,
    DEFAULT_REQUEST_RETRY_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ElcoRemoconCoordinator(DataUpdateCoordinator[RemoconData]):
    """Coordinator to poll Elco Remocon-Net data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )
        self.client = RemoconClient(
            email=config_entry.data[CONF_EMAIL],
            password=config_entry.data[CONF_PASSWORD],
            gateway_id=config_entry.data[CONF_GATEWAY_ID],
            zone=config_entry.data.get(CONF_ZONE, "1"),
            features_payload=config_entry.data.get(CONF_FEATURES_PAYLOAD),
            read_strategy=config_entry.options.get(
                CONF_READ_STRATEGY,
                config_entry.data.get(CONF_READ_STRATEGY, DEFAULT_READ_STRATEGY),
            ),
        )
        self._consecutive_connection_failures = 0
        self._retry_count = DEFAULT_REQUEST_RETRY_COUNT
        self._retry_delay = DEFAULT_REQUEST_RETRY_DELAY
        self._error_log_after_failures = DEFAULT_ERROR_LOG_AFTER_FAILURES

    async def _async_update_data(self) -> RemoconData:
        """Fetch data from the Remocon-Net cloud API."""
        last_connection_error: RemoconConnectionError | None = None

        for attempt in range(1, self._retry_count + 1):
            try:
                data = await self.hass.async_add_executor_job(self.client.get_data)
            except RemoconAuthError as err:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            except RemoconConnectionError as err:
                last_connection_error = err
                if attempt < self._retry_count:
                    _LOGGER.debug(
                        "Remocon update attempt %s/%s failed; retrying in %s seconds",
                        attempt,
                        self._retry_count,
                        self._retry_delay,
                    )
                    await asyncio.sleep(self._retry_delay)
                    continue
                break
            except Exception as err:
                raise UpdateFailed(f"Error fetching data: {err}") from err
            else:
                if self._consecutive_connection_failures > 0:
                    _LOGGER.info(
                        "Remocon connection recovered after %s failed update cycle(s)",
                        self._consecutive_connection_failures,
                    )
                self._consecutive_connection_failures = 0
                return data

        self._consecutive_connection_failures += 1
        if (
            self._consecutive_connection_failures < self._error_log_after_failures
            and self.data is not None
        ):
            _LOGGER.debug(
                "Suppressing transient Remocon connection error (%s/%s before error escalation): %s",
                self._consecutive_connection_failures,
                self._error_log_after_failures,
                last_connection_error,
            )
            return self.data

        if self._consecutive_connection_failures == self._error_log_after_failures:
            _LOGGER.error(
                "Remocon connection failed for %s consecutive update cycle(s); escalating errors",
                self._consecutive_connection_failures,
            )

        raise UpdateFailed(f"Connection error: {last_connection_error}")
