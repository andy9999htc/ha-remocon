"""Elco Remocon-Net integration for Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .coordinator import ElcoRemoconCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

SERVICE_SET_DHW_MODE = "set_dhw_mode"
SERVICE_SET_DHW_TEMPERATURE = "set_dhw_temperature"
SERVICE_SET_DATA_ITEM = "set_data_item"

ATTR_ENTRY_ID = "entry_id"
ATTR_MODE = "mode"
ATTR_COMFORT = "comfort"
ATTR_REDUCED = "reduced"
ATTR_ITEM_ID = "item_id"
ATTR_VALUE = "value"
ATTR_ZONE = "zone"

SERVICE_SET_DHW_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_MODE): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
    }
)

SERVICE_SET_DHW_TEMPERATURE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_COMFORT): vol.Coerce(float),
        vol.Optional(ATTR_REDUCED): vol.Coerce(float),
    }
)

SERVICE_SET_DATA_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_ITEM_ID): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(bool, int, float, str),
        vol.Optional(ATTR_ZONE, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
    }
)


def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> ElcoRemoconCoordinator:
    """Resolve coordinator for a service call."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators = {
        eid: value
        for eid, value in domain_data.items()
        if isinstance(value, ElcoRemoconCoordinator)
    }

    if not coordinators:
        raise HomeAssistantError("No Remocon-Net entries are loaded")

    if entry_id:
        coordinator = coordinators.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(f"Entry '{entry_id}' not found")
        return coordinator

    if len(coordinators) > 1:
        raise HomeAssistantError("Multiple entries found, please provide entry_id")

    return next(iter(coordinators.values()))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elco Remocon-Net from a config entry."""
    coordinator = ElcoRemoconCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not hass.data[DOMAIN].get("services_registered", False):

        async def _async_handle_set_dhw_mode(call) -> None:
            coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
            await hass.async_add_executor_job(
                coordinator.client.set_dhw_mode,
                call.data[ATTR_MODE],
            )
            await coordinator.async_request_refresh()

        async def _async_handle_set_dhw_temperature(call) -> None:
            comfort = call.data.get(ATTR_COMFORT)
            reduced = call.data.get(ATTR_REDUCED)
            if comfort is None and reduced is None:
                raise HomeAssistantError("At least one of comfort/reduced must be provided")

            coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
            await hass.async_add_executor_job(
                coordinator.client.set_dhw_temperature,
                comfort,
                reduced,
            )
            await coordinator.async_request_refresh()

        async def _async_handle_set_data_item(call) -> None:
            coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
            await hass.async_add_executor_job(
                coordinator.client.set_data_item,
                call.data[ATTR_ITEM_ID],
                call.data[ATTR_VALUE],
                call.data[ATTR_ZONE],
            )
            await coordinator.async_request_refresh()

        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_SET_DHW_MODE,
            _async_handle_set_dhw_mode,
            schema=SERVICE_SET_DHW_MODE_SCHEMA,
        )
        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_SET_DHW_TEMPERATURE,
            _async_handle_set_dhw_temperature,
            schema=SERVICE_SET_DHW_TEMPERATURE_SCHEMA,
        )
        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_SET_DATA_ITEM,
            _async_handle_set_data_item,
            schema=SERVICE_SET_DATA_ITEM_SCHEMA,
        )
        hass.data[DOMAIN]["services_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        remaining = [
            value
            for value in hass.data[DOMAIN].values()
            if isinstance(value, ElcoRemoconCoordinator)
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, SERVICE_SET_DHW_MODE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_DHW_TEMPERATURE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_DATA_ITEM)
            hass.data[DOMAIN]["services_registered"] = False

    return unload_ok
