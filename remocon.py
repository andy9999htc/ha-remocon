#!/usr/bin/env python3
"""
Elco Remocon-Net CLI — Read and control your Elco heat pump from the terminal.

Supports reading temperatures, operation modes, and system status, plus
setting zone temperatures, operation modes, and DHW settings via the
unofficial Remocon-Net cloud API.

Based on cschnidr/remocon-net-cli (read-only) and reverse-engineered
Ariston/Elco remotethermo.com API endpoints.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import requests

# ============================================================================
# Constants
# ============================================================================

DEFAULT_BASE_URL = "https://www.remocon-net.remotethermo.com"

ZONE_MODES = {
    0: "Protection",
    1: "Automatic",
    2: "Reduction",
    3: "Comfort",
}

ZONE_MODE_MAP = {v.lower(): k for k, v in ZONE_MODES.items()}

BSB_ZONE_MODES = {
    0: "OFF",
    1: "TIME_PROGRAM",
    2: "MANUAL_NIGHT",
    3: "MANUAL",
}

DHW_MODES = {
    0: "OFF",
    1: "ON",
}

# Features payload used for v2 API calls — matches what the web UI sends.
# This may need adjustment depending on your specific heat pump model.
FEATURES_PAYLOAD = {
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

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Config:
    email: str
    password: str
    gateway_id: str
    zone_id: str = "1"
    base_url: str = DEFAULT_BASE_URL
    # MQTT
    mqtt_enabled: bool = False
    mqtt_host: Optional[str] = None
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_topic_prefix: str = "remocon/heating"
    mqtt_qos: int = 0
    mqtt_retain: bool = False


@dataclass
class HeatingData:
    current_temperature: float = 0.0
    desired_temperature: float = 0.0
    reduced_temperature: float = 0.0
    comfort_temperature: float = 0.0
    cool_comfort_temperature: Optional[float] = None
    cool_reduced_temperature: Optional[float] = None
    outside_temperature: float = 0.0
    operation_mode: str = "Unknown"
    operation_mode_value: int = 0
    heating_active: bool = False
    cooling_active: bool = False
    heat_or_cool_request: bool = False
    dhw_temperature: float = 0.0
    dhw_comfort_temp: Optional[float] = None
    dhw_reduced_temp: Optional[float] = None
    dhw_mode: str = "Unknown"
    dhw_enabled: bool = False
    boiler_status: str = "Unknown"
    heat_pump_on: bool = False
    system_pressure: Optional[float] = None
    flow_temperature: Optional[float] = None
    zone_id: str = "1"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "current_temperature": self.current_temperature,
            "desired_temperature": self.desired_temperature,
            "comfort_temperature": self.comfort_temperature,
            "reduced_temperature": self.reduced_temperature,
            "outside_temperature": self.outside_temperature,
            "operation_mode": self.operation_mode,
            "operation_mode_value": self.operation_mode_value,
            "heating_active": self.heating_active,
            "cooling_active": self.cooling_active,
            "dhw_temperature": self.dhw_temperature,
            "dhw_mode": self.dhw_mode,
            "dhw_enabled": self.dhw_enabled,
            "heat_pump_on": self.heat_pump_on,
            "system_pressure": self.system_pressure,
            "flow_temperature": self.flow_temperature,
            "zone_id": self.zone_id,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================================
# Exceptions
# ============================================================================

class RemoconError(Exception):
    exit_code: int = 1
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class ConfigError(RemoconError):
    exit_code: int = 4

class AuthError(RemoconError):
    exit_code: int = 3

class NetworkError(RemoconError):
    exit_code: int = 1

class DataError(RemoconError):
    exit_code: int = 2

class SessionExpiredError(RemoconError):
    exit_code: int = 3


# ============================================================================
# Configuration
# ============================================================================

def load_config_file(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {e}")


def build_config(args: argparse.Namespace) -> Config:
    file_data = {}
    config_file = getattr(args, "config_file", None)
    if config_file:
        file_data = load_config_file(config_file)

    def _val(cli_attr, file_key, env_key):
        v = getattr(args, cli_attr, None)
        if v is not None:
            return v
        v = os.environ.get(env_key)
        if v is not None:
            return v
        v = file_data.get(file_key)
        return v

    email = _val("email", "email", "REMOCON_EMAIL")
    password = _val("password", "password", "REMOCON_PASSWORD")
    gateway_id = _val("gateway", "gateway_id", "REMOCON_GATEWAY")
    zone_id = _val("zone", "zone_id", "REMOCON_ZONE")

    missing = [f for f, v in [("email", email), ("password", password), ("gateway", gateway_id)] if not v]
    if missing:
        raise ConfigError(f"Missing required config: {', '.join(missing)}")

    return Config(
        email=email,
        password=password,
        gateway_id=gateway_id,
        zone_id=str(zone_id or "1"),
        base_url=file_data.get("base_url", DEFAULT_BASE_URL),
        mqtt_enabled=_val("mqtt_enabled", "mqtt_enabled", "REMOCON_MQTT_ENABLED") or False,
        mqtt_host=_val("mqtt_host", "mqtt_host", "REMOCON_MQTT_HOST"),
        mqtt_port=int(_val("mqtt_port", "mqtt_port", "REMOCON_MQTT_PORT") or 1883),
        mqtt_username=_val("mqtt_username", "mqtt_username", "REMOCON_MQTT_USER"),
        mqtt_password=_val("mqtt_password", "mqtt_password", "REMOCON_MQTT_PASS"),
        mqtt_topic_prefix=_val("mqtt_topic_prefix", "mqtt_topic_prefix", "REMOCON_MQTT_TOPIC") or "remocon/heating",
        mqtt_qos=int(_val("mqtt_qos", "mqtt_qos", "REMOCON_MQTT_QOS") or 0),
        mqtt_retain=bool(_val("mqtt_retain", "mqtt_retain", "REMOCON_MQTT_RETAIN")),
    )


# ============================================================================
# API Client
# ============================================================================

class RemoconClient:
    """Low-level API client for the Elco Remocon-Net cloud service."""

    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[requests.Session] = None

    def login(self) -> None:
        """Authenticate via the R2 web login (cookie-based session)."""
        s = requests.Session()
        url = f"{self.config.base_url}/R2/Account/Login?returnUrl=HTTP/2"
        payload = (
            f"Email={quote(self.config.email, safe='')}"
            f"&Password={quote(self.config.password, safe='')}"
            f"&RememberMe=false"
        )
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": "browserUtcOffset=-120",
        }
        try:
            resp = s.post(url, headers=headers, data=payload, timeout=15)
        except requests.RequestException as e:
            raise NetworkError(f"Connection failed: {e}")

        if resp.status_code in (401, 403):
            raise AuthError("Invalid email or password")
        resp.raise_for_status()

        try:
            data = resp.json()
        except ValueError:
            raise AuthError("Could not parse login response")

        if not data.get("ok"):
            raise AuthError(data.get("message", "Login failed"))

        self.session = s

    def _ensure_session(self) -> requests.Session:
        if self.session is None:
            self.login()
        return self.session  # type: ignore

    def _request(self, method: str, path: str, **kwargs) -> Any:
        s = self._ensure_session()
        url = f"{self.config.base_url}{path}"
        kwargs.setdefault("timeout", 15)
        try:
            resp = s.request(method, url, **kwargs)
        except requests.RequestException as e:
            raise NetworkError(f"Request failed: {e}")

        if resp.status_code in (401, 403):
            raise SessionExpiredError("Session expired, re-login needed")
        resp.raise_for_status()
        return resp.json()

    # ---- Read operations ----

    def get_plant_data(self) -> dict:
        """Fetch plant + zone data via R2 API."""
        path = f"/R2/PlantHomeBsb/GetData/{self.config.gateway_id}"
        payload = {
            "useCache": True,
            "zone": int(self.config.zone_id),
            "filter": {"progIds": None, "plant": True, "zone": True},
        }
        data = self._request("POST", path, json=payload)
        return data.get("data", data)

    def get_system_items(self, item_ids: list[dict]) -> dict:
        """Fetch specific data items via the v2 API."""
        path = f"/api/v2/remote/dataItems/{self.config.gateway_id}/get?umsys=si"
        payload = {
            "useCache": False,
            "items": item_ids,
            "features": FEATURES_PAYLOAD,
            "culture": "de",
        }
        data = self._request("POST", path, json=payload)
        result = {}
        for item in data.get("items", []):
            result[item["id"]] = item.get("value")
        return result

    def get_full_data(self) -> HeatingData:
        """Retrieve all available data and return a HeatingData object."""
        raw = self.get_plant_data()
        plant = raw.get("plantData", {})
        zone = raw.get("zoneData", {})

        # Try to get system metrics via v2 API
        sys_items = {}
        try:
            sys_items = self.get_system_items([
                {"id": "HeatingCircuitPressure", "zn": 0},
                {"id": "ChFlowTemp", "zn": 0},
            ])
        except Exception:
            pass

        mode_info = zone.get("mode", {})
        mode_val = mode_info.get("value", 0)
        mode_texts = mode_info.get("allowedOptionTexts", list(ZONE_MODES.values()))
        if mode_val < len(mode_texts):
            mode_str = mode_texts[mode_val]
        else:
            mode_str = ZONE_MODES.get(mode_val, f"Mode {mode_val}")

        dhw_mode_info = plant.get("dhwMode", {})
        dhw_mode_val = dhw_mode_info.get("value", 0)
        dhw_mode_str = "Unknown"
        for opt in dhw_mode_info.get("options", []):
            if opt.get("value") == dhw_mode_val:
                dhw_mode_str = opt.get("text", "Unknown")

        pressure = sys_items.get("HeatingCircuitPressure")
        flow_temp = sys_items.get("ChFlowTemp")

        return HeatingData(
            current_temperature=float(zone.get("roomTemp", 0)),
            desired_temperature=float(zone.get("desiredRoomTemp", 0)),
            reduced_temperature=float(zone.get("chReducedTemp", {}).get("value", 0)),
            comfort_temperature=float(zone.get("chComfortTemp", {}).get("value", 0)),
            cool_comfort_temperature=_float_or_none(zone.get("coolComfortTemp", {}).get("value")),
            cool_reduced_temperature=_float_or_none(zone.get("coolReducedTemp", {}).get("value")),
            outside_temperature=float(plant.get("outsideTemp", 0)),
            operation_mode=mode_str,
            operation_mode_value=mode_val,
            heating_active=bool(zone.get("isHeatingActive", 0)),
            cooling_active=bool(zone.get("isCoolingActive", 0)),
            heat_or_cool_request=bool(zone.get("heatOrCoolRequest", 0)),
            dhw_temperature=float(plant.get("dhwStorageTemp", 0)),
            dhw_comfort_temp=_float_or_none(plant.get("dhwComfortTemp", {}).get("value")),
            dhw_reduced_temp=_float_or_none(plant.get("dhwReducedTemp", {}).get("value")),
            dhw_mode=dhw_mode_str,
            dhw_enabled=bool(plant.get("dhwEnabled", 0)),
            boiler_status="Running" if plant.get("flameSensor") else "Standby",
            heat_pump_on=bool(plant.get("heatPumpOn", 0)),
            system_pressure=float(pressure) if pressure is not None else None,
            flow_temperature=float(flow_temp) if flow_temp is not None else None,
            zone_id=self.config.zone_id,
            timestamp=datetime.now(),
        )

    # ---- Write operations (via v2 REST API) ----

    def set_zone_temperatures(
        self,
        comfort: Optional[float] = None,
        reduced: Optional[float] = None,
        is_cooling: bool = False,
    ) -> bool:
        """Set comfort and/or reduced temperature for a zone."""
        # First, read current values
        raw = self.get_plant_data()
        zone = raw.get("zoneData", {})

        if is_cooling:
            old_comf = float(zone.get("coolComfortTemp", {}).get("value", 0))
            old_econ = float(zone.get("coolReducedTemp", {}).get("value", 0))
        else:
            old_comf = float(zone.get("chComfortTemp", {}).get("value", 0))
            old_econ = float(zone.get("chReducedTemp", {}).get("value", 0))

        new_comf = comfort if comfort is not None else old_comf
        new_econ = reduced if reduced is not None else old_econ

        path = (
            f"/api/v2/remote/bsbZones/{self.config.gateway_id}"
            f"/{self.config.zone_id}/temperatures?isCooling={'true' if is_cooling else 'false'}"
        )
        payload = {
            "new": {"comf": new_comf, "econ": new_econ},
            "old": {"comf": old_comf, "econ": old_econ},
        }
        self._request("POST", path, json=payload)
        return True

    def set_zone_mode(self, mode: str, is_cooling: bool = False) -> bool:
        """Set the zone operation mode. Accepts: protection, automatic, reduction, comfort."""
        mode_lower = mode.lower()
        if mode_lower not in ZONE_MODE_MAP:
            raise DataError(
                f"Invalid mode '{mode}'. Valid modes: {', '.join(ZONE_MODE_MAP.keys())}"
            )
        new_mode = ZONE_MODE_MAP[mode_lower]

        # Read current mode
        raw = self.get_plant_data()
        old_mode = raw.get("zoneData", {}).get("mode", {}).get("value", 1)

        path = (
            f"/api/v2/remote/bsbZones/{self.config.gateway_id}"
            f"/{self.config.zone_id}/mode?isCooling={'true' if is_cooling else 'false'}"
        )
        payload = {"new": new_mode, "old": old_mode}
        self._request("POST", path, json=payload)
        return True

    def set_dhw_temperature(
        self,
        comfort: Optional[float] = None,
        reduced: Optional[float] = None,
    ) -> bool:
        """Set domestic hot water comfort/reduced temperature."""
        raw = self.get_plant_data()
        plant = raw.get("plantData", {})

        old_comf = float(plant.get("dhwComfortTemp", {}).get("value", 45))
        old_econ = float(plant.get("dhwReducedTemp", {}).get("value", 40))

        new_comf = comfort if comfort is not None else old_comf
        new_econ = reduced if reduced is not None else old_econ

        path = f"/api/v2/remote/bsbPlantData/{self.config.gateway_id}/dhwTemp"
        payload = {
            "new": {"comf": new_comf, "econ": new_econ},
            "old": {"comf": old_comf, "econ": old_econ},
        }
        self._request("POST", path, json=payload)
        return True

    def set_dhw_mode(self, mode: str) -> bool:
        """Set DHW mode: 'on' or 'off'."""
        mode_lower = mode.lower()
        if mode_lower not in ("on", "off"):
            raise DataError("DHW mode must be 'on' or 'off'")
        new_val = 1 if mode_lower == "on" else 0

        path = f"/api/v2/remote/bsbPlantData/{self.config.gateway_id}/dhwMode"
        payload = {"new": new_val}
        self._request("POST", path, json=payload)
        return True

    def set_data_item(self, item_id: str, value: Any, zone: int = 0) -> bool:
        """Set a generic data item via the v2 API."""
        # Read current value first
        current = self.get_system_items([{"id": item_id, "zn": zone}])
        old_val = current.get(item_id, 0)

        path = f"/api/v2/remote/dataItems/{self.config.gateway_id}/set?umsys=si"
        payload = {
            "items": [{"id": item_id, "prevValue": old_val, "value": value, "zone": zone}],
            "features": FEATURES_PAYLOAD,
        }
        self._request("POST", path, json=payload)
        return True


def _float_or_none(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ============================================================================
# MQTT Publisher
# ============================================================================

def publish_mqtt(config: Config, data: HeatingData) -> None:
    """Publish heating data to MQTT broker."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("Warning: paho-mqtt not installed, skipping MQTT", file=sys.stderr)
        return

    client = mqtt.Client()
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)
    try:
        client.connect(config.mqtt_host, config.mqtt_port, keepalive=10)
        client.loop_start()
        time.sleep(0.3)
    except Exception as e:
        print(f"MQTT connection failed: {e}", file=sys.stderr)
        return

    prefix = config.mqtt_topic_prefix
    qos = config.mqtt_qos
    retain = config.mqtt_retain

    topics = {
        f"{prefix}/temperature/current": f"{data.current_temperature:.1f}",
        f"{prefix}/temperature/desired": f"{data.desired_temperature:.1f}",
        f"{prefix}/temperature/comfort": f"{data.comfort_temperature:.1f}",
        f"{prefix}/temperature/reduced": f"{data.reduced_temperature:.1f}",
        f"{prefix}/temperature/outside": f"{data.outside_temperature:.1f}",
        f"{prefix}/heating/mode": data.operation_mode,
        f"{prefix}/heating/active": "true" if data.heating_active else "false",
        f"{prefix}/heating/cooling_active": "true" if data.cooling_active else "false",
        f"{prefix}/heatpump/on": "true" if data.heat_pump_on else "false",
        f"{prefix}/dhw/temperature": f"{data.dhw_temperature:.1f}",
        f"{prefix}/dhw/mode": data.dhw_mode,
        f"{prefix}/dhw/enabled": "true" if data.dhw_enabled else "false",
        f"{prefix}/zone_id": data.zone_id,
        f"{prefix}/timestamp": data.timestamp.isoformat(),
    }
    if data.system_pressure is not None:
        topics[f"{prefix}/system/pressure"] = f"{data.system_pressure:.1f}"
    if data.flow_temperature is not None:
        topics[f"{prefix}/system/flow_temperature"] = f"{data.flow_temperature:.1f}"
    if data.dhw_comfort_temp is not None:
        topics[f"{prefix}/dhw/comfort_temp"] = f"{data.dhw_comfort_temp:.1f}"

    # Also publish full JSON payload
    topics[f"{prefix}/data"] = json.dumps(data.to_dict())

    for topic, payload in topics.items():
        client.publish(topic, payload, qos=qos, retain=retain)

    client.loop_stop()
    client.disconnect()
    print(f"Published {len(topics)} MQTT topics to {prefix}", file=sys.stderr)


# ============================================================================
# Display
# ============================================================================

def display_status(data: HeatingData) -> None:
    print("=" * 50)
    print("  Elco Heating System Status")
    print("=" * 50)
    print(f"  Retrieved:  {data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Zone:       {data.zone_id}")
    print()

    print("  Room Temperatures")
    print("  " + "-" * 46)
    print(f"  Current:        {data.current_temperature:.1f} °C")
    print(f"  Desired:        {data.desired_temperature:.1f} °C")
    print(f"  Comfort Set:    {data.comfort_temperature:.1f} °C")
    print(f"  Reduced Set:    {data.reduced_temperature:.1f} °C")
    if data.cool_comfort_temperature is not None:
        print(f"  Cool Comfort:   {data.cool_comfort_temperature:.1f} °C")
    if data.cool_reduced_temperature is not None:
        print(f"  Cool Reduced:   {data.cool_reduced_temperature:.1f} °C")
    print()

    print("  Outside")
    print("  " + "-" * 46)
    print(f"  Temperature:    {data.outside_temperature:.1f} °C")
    print()

    print("  Heating / Cooling")
    print("  " + "-" * 46)
    print(f"  Mode:           {data.operation_mode} ({data.operation_mode_value})")
    print(f"  Heating Active: {'Yes' if data.heating_active else 'No'}")
    print(f"  Cooling Active: {'Yes' if data.cooling_active else 'No'}")
    print(f"  Heat/Cool Req:  {'Yes' if data.heat_or_cool_request else 'No'}")
    print(f"  Heat Pump:      {'On' if data.heat_pump_on else 'Off'}")
    print()

    print("  Domestic Hot Water")
    print("  " + "-" * 46)
    print(f"  Temperature:    {data.dhw_temperature:.1f} °C")
    if data.dhw_comfort_temp is not None:
        print(f"  Comfort Set:    {data.dhw_comfort_temp:.1f} °C")
    if data.dhw_reduced_temp is not None:
        print(f"  Reduced Set:    {data.dhw_reduced_temp:.1f} °C")
    print(f"  Mode:           {data.dhw_mode}")
    print(f"  Enabled:        {'Yes' if data.dhw_enabled else 'No'}")
    print()

    print("  System")
    print("  " + "-" * 46)
    print(f"  Boiler:         {data.boiler_status}")
    if data.system_pressure is not None:
        print(f"  Pressure:       {data.system_pressure:.1f} bar")
    if data.flow_temperature is not None:
        print(f"  Flow Temp:      {data.flow_temperature:.1f} °C")
    print()


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_status(client: RemoconClient, config: Config, args: argparse.Namespace) -> int:
    """Read and display current status."""
    data = client.get_full_data()
    if args.json:
        print(json.dumps(data.to_dict(), indent=2))
    else:
        display_status(data)

    if config.mqtt_enabled:
        publish_mqtt(config, data)
    return 0


def cmd_set_temp(client: RemoconClient, config: Config, args: argparse.Namespace) -> int:
    """Set zone temperature setpoints."""
    if args.comfort is None and args.reduced is None:
        print("Error: specify --comfort and/or --reduced temperature", file=sys.stderr)
        return 1

    result = client.set_zone_temperatures(
        comfort=args.comfort,
        reduced=args.reduced,
        is_cooling=args.cooling,
    )
    print(f"Zone {config.zone_id} temperatures updated "
          f"(comfort={args.comfort}, reduced={args.reduced}, "
          f"cooling={args.cooling})")
    return 0


def cmd_set_mode(client: RemoconClient, config: Config, args: argparse.Namespace) -> int:
    """Set zone operation mode."""
    result = client.set_zone_mode(args.mode, is_cooling=args.cooling)
    print(f"Zone {config.zone_id} mode set to: {args.mode}")
    return 0


def cmd_set_dhw_temp(client: RemoconClient, config: Config, args: argparse.Namespace) -> int:
    """Set DHW temperature setpoints."""
    if args.comfort is None and args.reduced is None:
        print("Error: specify --comfort and/or --reduced temperature", file=sys.stderr)
        return 1

    result = client.set_dhw_temperature(comfort=args.comfort, reduced=args.reduced)
    print(f"DHW temperatures updated (comfort={args.comfort}, reduced={args.reduced})")
    return 0


def cmd_set_dhw_mode(client: RemoconClient, config: Config, args: argparse.Namespace) -> int:
    """Set DHW mode (on/off)."""
    result = client.set_dhw_mode(args.mode)
    print(f"DHW mode set to: {args.mode}")
    return 0


def cmd_raw_get(client: RemoconClient, config: Config, args: argparse.Namespace) -> int:
    """Fetch and display raw plant data (for debugging/exploration)."""
    raw = client.get_plant_data()
    print(json.dumps(raw, indent=2))
    return 0


# ============================================================================
# Argument Parser
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="remocon",
        description="Control your Elco heat pump via the Remocon-Net cloud API",
    )
    # Global config options
    _add_config_args(parser)

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    p_status = sub.add_parser("status", help="Show current heating system status")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    _add_config_args(p_status)

    # set-temp
    p_temp = sub.add_parser("set-temp", help="Set zone temperature setpoints")
    p_temp.add_argument("--comfort", type=float, help="Comfort temperature (°C)")
    p_temp.add_argument("--reduced", type=float, help="Reduced temperature (°C)")
    p_temp.add_argument("--cooling", action="store_true", help="Set cooling temperatures")
    _add_config_args(p_temp)

    # set-mode
    p_mode = sub.add_parser("set-mode", help="Set zone operation mode")
    p_mode.add_argument("mode", choices=list(ZONE_MODE_MAP.keys()),
                        help="Operation mode")
    p_mode.add_argument("--cooling", action="store_true", help="Set cooling mode")
    _add_config_args(p_mode)

    # set-dhw-temp
    p_dhw_temp = sub.add_parser("set-dhw-temp", help="Set DHW temperatures")
    p_dhw_temp.add_argument("--comfort", type=float, help="DHW comfort temperature (°C)")
    p_dhw_temp.add_argument("--reduced", type=float, help="DHW reduced temperature (°C)")
    _add_config_args(p_dhw_temp)

    # set-dhw-mode
    p_dhw_mode = sub.add_parser("set-dhw-mode", help="Set DHW mode (on/off)")
    p_dhw_mode.add_argument("mode", choices=["on", "off"], help="DHW mode")
    _add_config_args(p_dhw_mode)

    # raw-get
    p_raw = sub.add_parser("raw-get", help="Fetch raw API response (debug)")
    _add_config_args(p_raw)

    return parser


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    """Add configuration arguments to a parser or subparser.

    Uses argparse.SUPPRESS as default so that args provided on the main
    parser are not overwritten by None from a subparser.
    """
    SUP = argparse.SUPPRESS
    parser.add_argument("--email", type=str, help="Remocon-Net email", default=SUP)
    parser.add_argument("--password", type=str, help="Remocon-Net password", default=SUP)
    parser.add_argument("--gateway", type=str, help="Gateway ID", default=SUP)
    parser.add_argument("--zone", type=str, help="Zone ID (default: 1)", default=SUP)
    parser.add_argument("--config-file", type=str, help="Path to config JSON file", default=SUP)
    parser.add_argument("--mqtt-enabled", action="store_true", dest="mqtt_enabled", default=SUP)
    parser.add_argument("--mqtt-host", type=str, dest="mqtt_host", default=SUP)
    parser.add_argument("--mqtt-port", type=int, dest="mqtt_port", default=SUP)
    parser.add_argument("--mqtt-topic", type=str, dest="mqtt_topic_prefix", default=SUP)
    parser.add_argument("--mqtt-retain", action="store_true", dest="mqtt_retain", default=SUP)


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        config = build_config(args)
        client = RemoconClient(config)

        # Auto-retry once on expired session
        try:
            cmd_func = {
                "status": cmd_status,
                "set-temp": cmd_set_temp,
                "set-mode": cmd_set_mode,
                "set-dhw-temp": cmd_set_dhw_temp,
                "set-dhw-mode": cmd_set_dhw_mode,
                "raw-get": cmd_raw_get,
            }[args.command]
            return cmd_func(client, config, args)
        except SessionExpiredError:
            client.login()
            return cmd_func(client, config, args)

    except ConfigError as e:
        print(f"Config error: {e.message}", file=sys.stderr)
        return e.exit_code
    except AuthError as e:
        print(f"Auth error: {e.message}", file=sys.stderr)
        return e.exit_code
    except NetworkError as e:
        print(f"Network error: {e.message}", file=sys.stderr)
        return e.exit_code
    except DataError as e:
        print(f"Data error: {e.message}", file=sys.stderr)
        return e.exit_code
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
