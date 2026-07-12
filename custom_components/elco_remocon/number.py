"""Number entities for Elco Remocon-Net."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElcoRemoconCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elco number entities."""
    coordinator: ElcoRemoconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElcoDhwSetTemperatureNumber(coordinator, entry)])


class ElcoDhwSetTemperatureNumber(CoordinatorEntity[ElcoRemoconCoordinator], NumberEntity):
    """Writable DHW setpoint temperature."""

    _attr_has_entity_name = True
    _attr_translation_key = "dhw_set_temperature"
    _attr_native_min_value = 35.0
    _attr_native_max_value = 65.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: ElcoRemoconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        gw_id = entry.data["gateway_id"]
        self._attr_unique_id = f"{gw_id}_dhw_set_temperature"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, gw_id)},
            "name": "Remocon-Net Heat Pump",
            "manufacturer": "Elco",
            "model": "Aerotop SPK",
        }

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data.dhw_set_temp is not None and data.dhw_set_temp > 0:
            return data.dhw_set_temp
        if data.dhw_comfort_temp > 0:
            return data.dhw_comfort_temp
        return None

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(
            self.coordinator.client.set_dhw_set_temp,
            float(value),
        )
        await self.coordinator.async_request_refresh()
