"""Pytest configuration and fixtures."""

import sys
from pathlib import Path
from types import ModuleType


class _BaseEntity:
    """Minimal mock Entity base for HA entity classes used in tests."""

    def __init__(self, *args, **kwargs):
        self._attr_unique_id = None
        self._attr_device_info = None


class _CoordinatorEntity(_BaseEntity):
    """Minimal mock CoordinatorEntity base that carries coordinator state."""

    def __init__(self, coordinator=None):
        super().__init__()
        self.coordinator = coordinator


class _NumberEntity(_BaseEntity):
    """Minimal mock NumberEntity base."""


class _SelectEntity(_BaseEntity):
    """Minimal mock SelectEntity base."""


class _ClimateEntity(_BaseEntity):
    """Minimal mock ClimateEntity base."""


class _BinarySensorEntity(_BaseEntity):
    """Minimal mock BinarySensorEntity base."""


class _SensorEntity(_BaseEntity):
    """Minimal mock SensorEntity base."""


class _ConfigEntry:
    """Minimal mock ConfigEntry placeholder."""

    def __init__(self, data=None):
        self.data = data or {}
        self.options = {}


class _HomeAssistant:
    """Minimal mock HomeAssistant placeholder."""


# Create module-like stubs for the subset of Home Assistant used by the integration
homeassistant = ModuleType("homeassistant")
config_entries = ModuleType("homeassistant.config_entries")
const = ModuleType("homeassistant.const")
core = ModuleType("homeassistant.core")
exceptions = ModuleType("homeassistant.exceptions")
helpers = ModuleType("homeassistant.helpers")
helpers_service = ModuleType("homeassistant.helpers.service")
helpers_cv = ModuleType("homeassistant.helpers.config_validation")
helpers_update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
helpers_entity_platform = ModuleType("homeassistant.helpers.entity_platform")
components = ModuleType("homeassistant.components")
components_climate = ModuleType("homeassistant.components.climate")
components_sensor = ModuleType("homeassistant.components.sensor")
components_binary_sensor = ModuleType("homeassistant.components.binary_sensor")
components_number = ModuleType("homeassistant.components.number")
components_select = ModuleType("homeassistant.components.select")

config_entries.ConfigEntry = _ConfigEntry
config_entries.ConfigFlow = type("ConfigFlow", (), {})
config_entries.OptionsFlow = type("OptionsFlow", (), {})
const.CONF_EMAIL = "email"
const.CONF_PASSWORD = "password"
const.CONF_ZONE = "zone"
const.Platform = type("Platform", (), {"CLIMATE": "climate", "SENSOR": "sensor", "BINARY_SENSOR": "binary_sensor", "NUMBER": "number", "SELECT": "select"})
const.EntityCategory = type("EntityCategory", (), {"DIAGNOSTIC": "diagnostic"})
const.UnitOfPressure = type("UnitOfPressure", (), {"BAR": "bar"})
const.UnitOfTemperature = type("UnitOfTemperature", (), {"CELSIUS": "°C"})
core.HomeAssistant = _HomeAssistant
exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
helpers.config_validation = helpers_cv
helpers_service.async_register_admin_service = lambda *args, **kwargs: None
helpers_cv.string = str
helpers_cv.boolean = bool
helpers_update_coordinator.CoordinatorEntity = _CoordinatorEntity
helpers_update_coordinator.BaseCoordinatorEntity = _CoordinatorEntity

class _DataUpdateCoordinator:
    def __class_getitem__(cls, item):
        return cls

helpers_update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
helpers_update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})
helpers_entity_platform.AddEntitiesCallback = lambda *args, **kwargs: None
helpers_typing = ModuleType("homeassistant.helpers.typing")
helpers_typing.StateType = object
helpers.typing = helpers_typing
components_climate.ClimateEntity = _ClimateEntity
components_climate.ClimateEntityFeature = type("ClimateEntityFeature", (), {"TARGET_TEMPERATURE": 1, "PRESET_MODE": 2})
components_climate.HVACMode = type("HVACMode", (), {"HEAT": "heat", "AUTO": "auto", "OFF": "off"})
components_climate.HVACAction = type("HVACAction", (), {"HEATING": "heating", "OFF": "off"})
components_sensor.SensorEntity = _SensorEntity
components_sensor.SensorDeviceClass = type("SensorDeviceClass", (), {"TEMPERATURE": "temperature", "PRESSURE": "pressure"})
components_sensor.SensorEntityDescription = type("SensorEntityDescription", (), {})
components_sensor.SensorStateClass = type("SensorStateClass", (), {"MEASUREMENT": "measurement"})
components_binary_sensor.BinarySensorEntity = _BinarySensorEntity
components_binary_sensor.BinarySensorDeviceClass = type("BinarySensorDeviceClass", (), {"HEAT": "heat", "COLD": "cold", "RUNNING": "running"})
components_binary_sensor.BinarySensorEntityDescription = type("BinarySensorEntityDescription", (), {})
components_number.NumberEntity = _NumberEntity
components_select.SelectEntity = _SelectEntity
homeassistant.helpers = helpers
homeassistant.components = components
homeassistant.const = const
homeassistant.config_entries = config_entries
homeassistant.core = core
homeassistant.exceptions = exceptions
homeassistant.data_entry_flow = ModuleType("homeassistant.data_entry_flow")
homeassistant.data_entry_flow.FlowResult = dict

sys.modules['homeassistant'] = homeassistant
sys.modules['homeassistant.config_entries'] = config_entries
sys.modules['homeassistant.const'] = const
sys.modules['homeassistant.core'] = core
sys.modules['homeassistant.exceptions'] = exceptions
sys.modules['homeassistant.helpers'] = helpers
sys.modules['homeassistant.helpers.service'] = helpers_service
sys.modules['homeassistant.helpers.config_validation'] = helpers_cv
sys.modules['homeassistant.helpers.update_coordinator'] = helpers_update_coordinator
sys.modules['homeassistant.helpers.entity_platform'] = helpers_entity_platform
sys.modules['homeassistant.helpers.typing'] = helpers_typing
sys.modules['homeassistant.data_entry_flow'] = homeassistant.data_entry_flow
sys.modules['homeassistant.components'] = components
sys.modules['homeassistant.components.climate'] = components_climate
sys.modules['homeassistant.components.sensor'] = components_sensor
sys.modules['homeassistant.components.binary_sensor'] = components_binary_sensor
sys.modules['homeassistant.components.number'] = components_number
sys.modules['homeassistant.components.select'] = components_select

# Add the custom_components directory to the path so imports work
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))
