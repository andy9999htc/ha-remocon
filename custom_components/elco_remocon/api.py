"""API client for the Elco Remocon-Net cloud service."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import requests

from .const import (
    DEFAULT_ERROR_LOG_AFTER_FAILURES,
    DEFAULT_READ_STRATEGY,
    MODE_AUTOMATIC,
    MODE_COMFORT,
    MODE_PROTECTION,
    MODE_REDUCTION,
    READ_STRATEGY_BSB_FIRST,
    READ_STRATEGY_BSB_ONLY,
    READ_STRATEGIES,
    READ_STRATEGY_LEGACY_FIRST,
    READ_STRATEGY_LEGACY_ONLY,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.remocon-net.remotethermo.com"

DEFAULT_FEATURES_PAYLOAD = {
    "zones": [{"num": 1, "name": "", "roomSens": False, "geofenceDeroga": False,
               "virtInfo": None, "isHidden": False}],
    "solar": False, "convBoiler": False, "commBoiler": False, "hpSys": False,
    "hybridSys": False, "cascadeSys": False, "dhwProgSupported": True,
    "virtualZones": False, "hasVmc": False, "extendedTimeProg": False,
    "hasBoiler": True, "pilotSupported": False, "isVmcR2": False,
    "isEvo2": False, "dhwHidden": False, "dhwBoilerPresent": True,
    "dhwModeChangeable": True, "hvInputOff": False, "autoThermoReg": False,
    "hasMetering": False, "hasFireplace": False, "hasSlp": False,
    "hasEm20": False, "hasEm30": False, "systemServices": 0,
    "hasTwoCoolingTemp": False, "bmsActive": False, "hpCascadeSys": False,
    "hpCascadeConfig": -1, "bufferTimeProgAvailable": False,
    "distinctHeatCoolSetpoints": False, "hasZoneNames": False,
    "zoneManagerStandAlone": False, "hydraulicScheme": None,
    "preHeatingSupported": False, "hasGahp": False, "zigbeeActive": False,
    "hasSlpAloneOnBus": False, "isSlpCascade": False,
    "hasZeroColdWaterProg": False, "weatherProvider": 0,
    "hasDhwTimeProgTemperatures": 2, "isGSWHCommercialAloneOnBus": False,
}


def _deep_merge_features(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge feature payload dictionaries.

    Dict values are merged recursively, while non-dict values (including lists)
    replace the base value.
    """
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_features(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _build_features_payload(zone: str, custom_features: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Build the features payload sent to the v2 API."""
    payload = deepcopy(DEFAULT_FEATURES_PAYLOAD)
    if custom_features:
        payload = _deep_merge_features(payload, custom_features)
    zone_num = int(zone)

    zones = payload.get("zones")
    if not isinstance(zones, list) or not zones:
        payload["zones"] = [{
            "num": zone_num,
            "name": "",
            "roomSens": False,
            "geofenceDeroga": False,
            "virtInfo": None,
            "isHidden": False,
        }]
        return payload

    first_zone = zones[0]
    if not isinstance(first_zone, dict):
        zones[0] = {
            "num": zone_num,
            "name": "",
            "roomSens": False,
            "geofenceDeroga": False,
            "virtInfo": None,
            "isHidden": False,
        }
    else:
            first_zone["num"] = zone_num

    return payload


class RemoconApiError(Exception):
    """Base exception for API errors."""


class RemoconAuthError(RemoconApiError):
    """Authentication failed."""


class RemoconConnectionError(RemoconApiError):
    """Connection error."""


class RemoconDataError(RemoconApiError):
    """Data error."""


@dataclass
class RemoconData:
    """All data from the heating system."""

    # Zone
    comfort_temp: float = 0.0
    comfort_temp_min: float = 5.0
    comfort_temp_max: float = 35.0
    comfort_temp_step: float = 0.5
    reduced_temp: float = 0.0
    desired_temp: float = 0.0
    room_temp: float = 0.0
    zone_mode: int = MODE_AUTOMATIC
    zone_mode_texts: list[str] = field(default_factory=list)
    heating_active: bool = False
    cooling_active: bool = False
    heat_or_cool_request: bool = False
    # Plant
    outside_temp: float = 0.0
    dhw_temp: float = 0.0
    dhw_set_temp: Optional[float] = None
    dhw_comfort_temp: float = 0.0
    dhw_reduced_temp: float = 0.0
    dhw_mode: int = 0
    dhw_enabled: bool = False
    plant_mode: Optional[int] = None
    heat_pump_on: bool = False
    flame_sensor: bool = False
    # System (from v2 API)
    system_pressure: Optional[float] = None
    flow_temperature: Optional[float] = None
    # Meta
    has_room_sensor: bool = False


class RemoconClient:
    """Synchronous API client for Elco Remocon-Net."""

    def __init__(
        self,
        email: str,
        password: str,
        gateway_id: str,
        zone: str = "1",
        features_payload: Optional[dict[str, Any]] = None,
        read_strategy: str = DEFAULT_READ_STRATEGY,
    ) -> None:
        self._email = email
        self._password = password
        self._gateway_id = gateway_id
        self._zone = zone
        self._features_payload = _build_features_payload(zone, features_payload)
        self._read_strategy = read_strategy if read_strategy in READ_STRATEGIES else DEFAULT_READ_STRATEGY
        self._session: Optional[requests.Session] = None
        self._consecutive_request_failures = 0
        self._error_log_after_failures = DEFAULT_ERROR_LOG_AFTER_FAILURES

    def login(self) -> None:
        """Authenticate and store session cookie."""
        s = requests.Session()
        url = f"{BASE_URL}/R2/Account/Login?returnUrl=HTTP/2"
        payload = (
            f"Email={quote(self._email, safe='')}"
            f"&Password={quote(self._password, safe='')}"
            f"&RememberMe=false"
        )
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": "browserUtcOffset=-120",
        }
        try:
            resp = s.request("POST", url, headers=headers, data=payload, timeout=15)
        except requests.RequestException as err:
            raise RemoconConnectionError(str(err)) from err

        if resp.status_code in (401, 403):
            raise RemoconAuthError("Invalid credentials")
        resp.raise_for_status()

        try:
            data = resp.json()
        except ValueError as err:
            raise RemoconAuthError("Could not parse login response") from err

        if not data.get("ok"):
            raise RemoconAuthError(data.get("message", "Login failed"))

        self._session = s

    def _get_session(self) -> requests.Session:
        if self._session is None:
            self.login()
        return self._session  # type: ignore[return-value]

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        s = self._get_session()
        url = f"{BASE_URL}{path}"
        kwargs.setdefault("timeout", 15)
        try:
            resp = s.request(method, url, **kwargs)
            if resp.status_code in (401, 403):
                raise RemoconAuthError("Session expired")
            resp.raise_for_status()
        except requests.RequestException as err:
            self._consecutive_request_failures += 1
            err_msg = str(err)
            response = getattr(err, "response", None)
            is_bsb_get_data_500 = (
                response is not None
                and response.status_code == 500
                and path.startswith("/R2/PlantHomeBsb/GetData/")
            )
            if response is not None:
                response_text = response.text.strip()
                content_type = response.headers.get("Content-Type", "")
                is_html = (
                    "html" in content_type.lower()
                    or response_text.lower().startswith("<!doctype html")
                    or response_text.lower().startswith("<html")
                )
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    err_msg += f" - Response: {response.text}"
                elif is_html:
                    err_msg += " - Response body omitted (HTML error page; enable debug logging for full body)"
            if is_bsb_get_data_500:
                if self._consecutive_request_failures >= self._error_log_after_failures:
                    _LOGGER.info(
                        "BSB endpoint returned HTTP 500 for %s; using legacy endpoint fallback when strategy allows",
                        path,
                    )
                else:
                    _LOGGER.debug(
                        "Transient BSB HTTP 500 (%s/%s before escalation) for %s",
                        self._consecutive_request_failures,
                        self._error_log_after_failures,
                        path,
                    )
            else:
                if self._consecutive_request_failures >= self._error_log_after_failures:
                    _LOGGER.error(
                        "API Request failed (%s consecutive failures): %s",
                        self._consecutive_request_failures,
                        err_msg,
                    )
                else:
                    _LOGGER.debug(
                        "Transient API request failure (%s/%s before error logging): %s",
                        self._consecutive_request_failures,
                        self._error_log_after_failures,
                        err_msg,
                    )
            raise RemoconConnectionError(err_msg) from err

        if self._consecutive_request_failures > 0:
            if self._consecutive_request_failures >= self._error_log_after_failures:
                _LOGGER.info(
                    "Remocon API request recovered after %s consecutive failure(s)",
                    self._consecutive_request_failures,
                )
            self._consecutive_request_failures = 0
        
        try:
            return resp.json()
        except ValueError as err:
            _LOGGER.error("Invalid JSON response from API: %s", resp.text)
            raise RemoconDataError("Could not parse API response") from err

    def _get_raw_bsb(self) -> dict:
        """Fetch data from the newer BSB endpoint."""
        path = f"/R2/PlantHomeBsb/GetData/{self._gateway_id}"
        payload = {
            "useCache": True,
            "zone": int(self._zone),
            "filter": {"progIds": None, "plant": True, "zone": True},
        }
        data = self._request("POST", path, json=payload)
        return data.get("data", data) if isinstance(data, dict) else data

    def _get_raw_legacy(self) -> dict:
        """Fetch data from the legacy PlantHome endpoint.

        Some heat pump models return more complete data with this request shape.
        """
        path = f"/R2/PlantHome/GetData/{self._gateway_id}?umsys=si"
        payload = {
            "features": self._features_payload,
            "useCache": True,
            "zone": int(self._zone),
            "filter": {
                "notEssentials": True,
                "progId": None,
                "plant": True,
                "zone": True,
                "dhw": True,
            },
        }
        data = self._request("POST", path, json=payload)
        return data.get("data", data) if isinstance(data, dict) else data

    def _get_raw(self) -> dict:
        """Fetch raw data according to configured strategy."""

        def _is_empty_payload(candidate: Any) -> bool:
            return candidate is None or candidate == {}

        strategy = self._read_strategy

        if strategy == READ_STRATEGY_LEGACY_ONLY:
            data = self._get_raw_legacy()
        elif strategy == READ_STRATEGY_BSB_ONLY:
            data = self._get_raw_bsb()
        elif strategy == READ_STRATEGY_LEGACY_FIRST:
            try:
                data = self._get_raw_legacy()
            except RemoconApiError:
                data = self._get_raw_bsb()

            if _is_empty_payload(data):
                data = self._get_raw_bsb()
            elif isinstance(data, dict) and not data.get("zoneData") and not data.get("plantData") and not data.get("items"):
                data = self._get_raw_bsb()
        else:  # READ_STRATEGY_BSB_FIRST
            try:
                data = self._get_raw_bsb()
            except RemoconApiError:
                data = self._get_raw_legacy()

            if _is_empty_payload(data):
                data = self._get_raw_legacy()
                if not data:
                    raise RemoconDataError("Empty data received from API")

            if isinstance(data, dict) and not data.get("zoneData") and not data.get("plantData") and not data.get("items"):
                data = self._get_raw_legacy()

        if data is None:
            raise RemoconDataError("Empty data received from API")
        if isinstance(data, dict) and not data.get("ok", True):
            _LOGGER.error("API returned error: %s", data)
            raise RemoconDataError(data.get("message", "API returned error"))
        if not isinstance(data, dict):
            raise RemoconDataError(f"Unexpected raw data format: {type(data)}")

        return data

    def _get_system_items(self, item_ids: list[dict]) -> dict[str, Any]:
        path = f"/api/v2/remote/dataItems/{self._gateway_id}/get?umsys=si"
        payload = {
            "useCache": False,
            "items": item_ids,
            "features": self._features_payload,
            "culture": "de",
        }
        data = self._request("POST", path, json=payload)
        return {item["id"]: item.get("value") for item in data.get("items", [])} if isinstance(data, dict) else {}

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value) != 0
        return bool(value)

    @staticmethod
    def _legacy_option_text(item: dict[str, Any]) -> str | None:
        options = item.get("options")
        opt_texts = item.get("optTexts")
        value = item.get("value")
        if not isinstance(options, list) or not isinstance(opt_texts, list):
            return None
        if len(options) != len(opt_texts):
            return None

        for option, text in zip(options, opt_texts):
            if option == value:
                return str(text)
            if isinstance(option, (int, float)) and isinstance(value, (int, float)) and float(option) == float(value):
                return str(text)
        return None

    def _legacy_items_to_remocon_data(self, items: list[dict[str, Any]]) -> RemoconData:
        """Map legacy `items` payload to RemoconData fields."""
        zone_num = int(self._zone)
        by_key: dict[tuple[str, int], dict[str, Any]] = {}

        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str):
                continue
            try:
                item_zone = int(item.get("zone", 0))
            except (TypeError, ValueError):
                item_zone = 0
            by_key[(item_id, item_zone)] = item

        def _item(item_id: str, zone: int | None = None) -> dict[str, Any] | None:
            if zone is None:
                zone = zone_num
            return by_key.get((item_id, zone)) or by_key.get((item_id, 0))

        def _value(item_id: str, zone: int | None = None, default: Any = 0) -> Any:
            entry = _item(item_id, zone)
            if not entry:
                return default
            return entry.get("value", default)

        comfort_item = _item("ZoneComfortTemp") or {}
        reduced_item = _item("ZoneEconomyTemp") or {}
        desired_item = _item("ZoneDesiredTemp") or {}
        measured_item = _item("ZoneMeasuredTemp") or {}
        zone_mode_item = _item("ZoneMode") or {}
        plant_mode_item = _item("PlantMode", 0) or {}
        heat_request_item = _item("ZoneHeatRequest") or {}

        zone_mode_value = int(float(zone_mode_item.get("value", MODE_AUTOMATIC)))
        zone_mode_text = (self._legacy_option_text(zone_mode_item) or "").lower()

        mapped_zone_mode = MODE_AUTOMATIC
        if "time" in zone_mode_text or "program" in zone_mode_text:
            mapped_zone_mode = MODE_AUTOMATIC
        elif "manual" in zone_mode_text:
            desired = float(desired_item.get("value", 0))
            comfort = float(comfort_item.get("value", 0))
            reduced = float(reduced_item.get("value", 0))
            if reduced > 0 and abs(desired - reduced) < abs(desired - comfort):
                mapped_zone_mode = MODE_REDUCTION
            else:
                mapped_zone_mode = MODE_COMFORT
        elif zone_mode_value in (MODE_PROTECTION, MODE_AUTOMATIC, MODE_REDUCTION, MODE_COMFORT):
            mapped_zone_mode = zone_mode_value

        plant_mode_text = (self._legacy_option_text(plant_mode_item) or "").lower()
        plant_mode_value = plant_mode_item.get("value")
        cooling_active = "cool" in plant_mode_text or plant_mode_value == 3

        measured_temp = float(measured_item.get("value", 0))

        return RemoconData(
            comfort_temp=float(comfort_item.get("value", 0)),
            comfort_temp_min=float(comfort_item.get("min", 5)),
            comfort_temp_max=float(comfort_item.get("max", 35)),
            comfort_temp_step=float(comfort_item.get("step", 0.5)),
            reduced_temp=float(reduced_item.get("value", 0)),
            desired_temp=float(desired_item.get("value", 0)),
            room_temp=measured_temp,
            zone_mode=mapped_zone_mode,
            zone_mode_texts=zone_mode_item.get("optTexts", []),
            heating_active=self._coerce_bool(_value("IsHeatingPumpOn", 0, 0)) and not cooling_active,
            cooling_active=cooling_active,
            heat_or_cool_request=self._coerce_bool(heat_request_item.get("value", 0)),
            outside_temp=float(_value("OutsideTemp", 0, 0)),
            dhw_temp=float(_value("DhwStorageTemperature", 0, _value("DhwTemp", 0, 0))),
            dhw_set_temp=float(_value("DhwTemp", 0, _value("DhwTimeProgComfortTemp", 0, 0))),
            dhw_comfort_temp=float(_value("DhwTimeProgComfortTemp", 0, 0)),
            dhw_reduced_temp=float(_value("DhwTimeProgEconomyTemp", 0, 0)),
            dhw_mode=int(float(_value("DhwMode", 0, 0))),
            dhw_enabled=self._coerce_bool(_value("DhwMode", 0, 0)),
            plant_mode=int(float(plant_mode_value)) if plant_mode_value is not None else None,
            heat_pump_on=self._coerce_bool(_value("IsHeatingPumpOn", 0, 0)),
            flame_sensor=False,
            system_pressure=None,
            flow_temperature=None,
            has_room_sensor=measured_temp > 0,
        )

    def get_data(self) -> RemoconData:
        """Fetch all data and return a RemoconData object."""
        raw = self._get_raw()
        if not isinstance(raw, dict):
            raise RemoconDataError(f"Unexpected data format from API: {type(raw)}")

        if isinstance(raw.get("items"), list) and not raw.get("plantData") and not raw.get("zoneData"):
            try:
                data = self._legacy_items_to_remocon_data(raw["items"])
            except Exception as err:
                _LOGGER.error("Could not parse legacy items payload: %s", err)
            else:
                # Try to enrich with v2 system items when available.
                try:
                    sys_items = self._get_system_items([
                        {"id": "HeatingCircuitPressure", "zn": 0},
                        {"id": "ChFlowTemp", "zn": 0},
                    ])
                    pressure = sys_items.get("HeatingCircuitPressure")
                    flow = sys_items.get("ChFlowTemp")
                    if pressure is not None:
                        data.system_pressure = float(pressure)
                    if flow is not None:
                        data.flow_temperature = float(flow)
                except Exception as err:
                    _LOGGER.debug("Could not enrich legacy items data with v2 system items: %s", err)
                return data
            
        plant = raw.get("plantData") or {}
        zone = raw.get("zoneData") or {}

        sys_items: dict[str, Any] = {}
        try:
            sys_items = self._get_system_items([
                {"id": "HeatingCircuitPressure", "zn": 0},
                {"id": "ChFlowTemp", "zn": 0},
            ])
        except Exception as err:
            _LOGGER.debug("Could not fetch system items from v2 API: %s", err)

        ch_comfort = zone.get("chComfortTemp") or {}
        ch_reduced = zone.get("chReducedTemp") or {}
        mode_info = zone.get("mode") or {}

        pressure = sys_items.get("HeatingCircuitPressure")
        flow = sys_items.get("ChFlowTemp")

        dhw_comfort = plant.get("dhwComfortTemp") or {}
        dhw_reduced = plant.get("dhwReducedTemp") or {}
        dhw_mode_info = plant.get("dhwMode") or {}

        return RemoconData(
            comfort_temp=float(ch_comfort.get("value", 0)),
            comfort_temp_min=float(ch_comfort.get("min", 5)),
            comfort_temp_max=float(ch_comfort.get("max", 35)),
            comfort_temp_step=float(ch_comfort.get("step", 0.5)),
            reduced_temp=float(ch_reduced.get("value", 0)),
            desired_temp=float(zone.get("desiredRoomTemp", 0)),
            room_temp=float(zone.get("roomTemp", 0)),
            zone_mode=mode_info.get("value", MODE_AUTOMATIC),
            zone_mode_texts=mode_info.get("allowedOptionTexts", []),
            heating_active=bool(zone.get("isHeatingActive", 0)),
            cooling_active=bool(zone.get("isCoolingActive", 0)),
            heat_or_cool_request=bool(zone.get("heatOrCoolRequest", 0)),
            outside_temp=float(plant.get("outsideTemp", 0)),
            dhw_temp=float(plant.get("dhwStorageTemp", 0)),
            dhw_set_temp=float(dhw_comfort.get("value", 0)),
            dhw_comfort_temp=float(dhw_comfort.get("value", 0)),
            dhw_reduced_temp=float(dhw_reduced.get("value", 0)),
            dhw_mode=dhw_mode_info.get("value", 0),
            dhw_enabled=bool(plant.get("dhwEnabled", 0)),
            plant_mode=None,
            heat_pump_on=bool(plant.get("heatPumpOn", 0)),
            flame_sensor=bool(plant.get("flameSensor", 0)),
            system_pressure=float(pressure) if pressure is not None else None,
            flow_temperature=float(flow) if flow is not None else None,
            has_room_sensor=bool(zone.get("hasRoomSensor", 0)),
        )

    def set_zone_temperatures(
        self, comfort: float | None = None, reduced: float | None = None
    ) -> None:
        """Set comfort and/or reduced temperature."""
        raw = self._get_raw()
        if not isinstance(raw, dict):
            raw = {}
        zone = raw.get("zoneData") or {}
        ch_comf = zone.get("chComfortTemp") or {}
        ch_red = zone.get("chReducedTemp") or {}
        old_comf = float(ch_comf.get("value", 0))
        old_econ = float(ch_red.get("value", 0))

        new_comf = comfort if comfort is not None else old_comf
        new_econ = reduced if reduced is not None else old_econ

        path = (
            f"/api/v2/remote/bsbZones/{self._gateway_id}"
            f"/{self._zone}/temperatures?isCooling=false"
        )
        self._request("POST", path, json={
            "new": {"comf": new_comf, "econ": new_econ},
            "old": {"comf": old_comf, "econ": old_econ},
        })

    def set_zone_mode(self, mode: int) -> None:
        """Set zone operation mode."""
        raw = self._get_raw()
        if not isinstance(raw, dict):
            raw = {}
        zone = raw.get("zoneData") or {}
        mode_info = zone.get("mode") or {}
        old_mode = mode_info.get("value", MODE_AUTOMATIC)

        path = (
            f"/api/v2/remote/bsbZones/{self._gateway_id}"
            f"/{self._zone}/mode?isCooling=false"
        )
        self._request("POST", path, json={"new": mode, "old": old_mode})

    def set_dhw_temperature(
        self, comfort: float | None = None, reduced: float | None = None
    ) -> None:
        """Set DHW temperatures."""
        raw = self._get_raw()
        if not isinstance(raw, dict):
            raw = {}
        plant = raw.get("plantData") or {}
        dhw_comf = plant.get("dhwComfortTemp") or {}
        dhw_red = plant.get("dhwReducedTemp") or {}
        old_comf = float(dhw_comf.get("value", 0))
        old_econ = float(dhw_red.get("value", 0))

        new_comf = comfort if comfort is not None else old_comf
        new_econ = reduced if reduced is not None else old_econ

        path = f"/api/v2/remote/bsbPlantData/{self._gateway_id}/dhwTemp"
        self._request("POST", path, json={
            "new": {"comf": new_comf, "econ": new_econ},
            "old": {"comf": old_comf, "econ": old_econ},
        })

    def set_dhw_mode(self, mode: int) -> None:
        """Set DHW mode."""
        path = f"/api/v2/remote/bsbPlantData/{self._gateway_id}/dhwMode"
        self._request("POST", path, json={"new": mode})

    def set_data_item(self, item_id: str, value: Any, zone: int = 0) -> None:
        """Set a generic v2 data item value."""
        current = self._get_system_items([{"id": item_id, "zn": zone}])
        old_val = current.get(item_id, 0)

        path = f"/api/v2/remote/dataItems/{self._gateway_id}/set?umsys=si"
        payload = {
            "items": [{"id": item_id, "prevValue": old_val, "value": value, "zone": zone}],
            "features": self._features_payload,
        }
        self._request("POST", path, json=payload)

    def set_dhw_set_temp(self, value: float) -> None:
        """Set DHW setpoint temperature via generic data item write."""
        self.set_data_item("DhwTemp", value, zone=0)

    def set_plant_mode(self, value: int) -> None:
        """Set plant mode via generic data item write."""
        self.set_data_item("PlantMode", value, zone=0)

    def reauth(self) -> None:
        """Force re-authentication."""
        self._session = None
        self.login()
