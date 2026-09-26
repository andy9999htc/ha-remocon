"""Number entities for Elco Remocon-Net."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElcoRemoconCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elco number entities."""
    coordinator: ElcoRemoconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ElcoDhwSetTemperatureNumber(coordinator, entry),
        ElcoDhwComfortTemperatureNumber(coordinator, entry),
        ElcoDhwReducedTemperatureNumber(coordinator, entry),
    ])


class _BaseDhwTemperatureNumber(CoordinatorEntity, NumberEntity):
    """Shared DHW temperature number entity."""

    _attr_has_entity_name = True
    _attr_native_min_value = 35.0
    _attr_native_max_value = 65.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: ElcoRemoconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        gw_id = entry.data["gateway_id"]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, gw_id)},
            "name": "Remocon-Net Heat Pump",
            "manufacturer": "Elco",
            "model": "Aerotop SPK",
        }


class ElcoDhwSetTemperatureNumber(_BaseDhwTemperatureNumber):
    """Writable DHW setpoint temperature."""

    _attr_translation_key = "dhw_set_temperature"

    def __init__(self, coordinator: ElcoRemoconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        gw_id = entry.data["gateway_id"]
        self._attr_unique_id = f"{gw_id}_dhw_set_temperature"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data.dhw_set_temp is not None and data.dhw_set_temp > 0:
            return data.dhw_set_temp
        if data.dhw_comfort_temp > 0:
            return data.dhw_comfort_temp
        return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_execute_write_operation(
            f"set dhw temp auf {float(value):g} C",
            self.coordinator.client.set_dhw_set_temp,
            float(value),
        )
        await self.coordinator.async_request_refresh()


class ElcoDhwComfortTemperatureNumber(_BaseDhwTemperatureNumber):
    """Writable DHW comfort temperature."""

    _attr_translation_key = "dhw_comfort_temperature"

    def __init__(self, coordinator: ElcoRemoconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        gw_id = entry.data["gateway_id"]
        self._attr_unique_id = f"{gw_id}_dhw_comfort_temperature"

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.dhw_comfort_temp
        return value if value > 0 else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_execute_write_operation(
            f"set dhw comfort temp auf {float(value):g} C",
            self.coordinator.client.set_dhw_temperature,
            float(value),
            None,
        )
        await self.coordinator.async_request_refresh()


class ElcoDhwReducedTemperatureNumber(_BaseDhwTemperatureNumber):
    """Writable DHW reduced temperature."""

    _attr_translation_key = "dhw_reduced_temperature"

    def __init__(self, coordinator: ElcoRemoconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        gw_id = entry.data["gateway_id"]
        self._attr_unique_id = f"{gw_id}_dhw_reduced_temperature"

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.dhw_reduced_temp
        return value if value > 0 else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_execute_write_operation(
            f"set dhw reduced temp auf {float(value):g} C",
            self.coordinator.client.set_dhw_temperature,
            None,
            float(value),
        )
        await self.coordinator.async_request_refresh()
