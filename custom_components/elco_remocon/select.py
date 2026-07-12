"""Select entities for Elco Remocon-Net."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElcoRemoconCoordinator

PLANT_MODE_OPTIONS: dict[str, int] = {
    "Summer": 0,
    "Winter": 1,
    "Heating only": 2,
    "Cooling": 3,
    "OFF": 5,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elco select entities."""
    coordinator: ElcoRemoconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElcoPlantModeSelect(coordinator, entry)])


class ElcoPlantModeSelect(CoordinatorEntity[ElcoRemoconCoordinator], SelectEntity):
    """Writable PlantMode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "plant_mode"

    def __init__(self, coordinator: ElcoRemoconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        gw_id = entry.data["gateway_id"]
        self._attr_unique_id = f"{gw_id}_plant_mode"
        self._attr_options = list(PLANT_MODE_OPTIONS.keys())
        self._attr_device_info = {
            "identifiers": {(DOMAIN, gw_id)},
            "name": "Remocon-Net Heat Pump",
            "manufacturer": "Elco",
            "model": "Aerotop SPK",
        }

    @property
    def current_option(self) -> str | None:
        plant_mode = self.coordinator.data.plant_mode
        if plant_mode is None:
            return None
        for label, value in PLANT_MODE_OPTIONS.items():
            if value == plant_mode:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        if option not in PLANT_MODE_OPTIONS:
            return
        await self.hass.async_add_executor_job(
            self.coordinator.client.set_plant_mode,
            PLANT_MODE_OPTIONS[option],
        )
        await self.coordinator.async_request_refresh()
