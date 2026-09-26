"""Standalone live API test for Remocon Net.

This script performs real API calls using environment variables.

Usage (PowerShell):
    $env:REMO_EMAIL="you@example.com"
    $env:REMO_PASSWORD="your-password"
    $env:REMO_GATEWAY_ID="YOUR_GATEWAY"
    python standalone_api_live_test.py

Optional write test (set_data_item):
    $env:REMO_RUN_WRITE="1"
    $env:REMO_RUN_DATA_ITEM_WRITE="1"
    $env:REMO_ITEM_ID="ChFlowSetpointTemp"
    $env:REMO_ITEM_VALUE="28.0"
    $env:REMO_ITEM_ZONE="0"
    python standalone_api_live_test.py

Optional explicit DHW data-item write test (writes both DhwTemp and DhwTimeProgComfortTemp):
    $env:REMO_RUN_WRITE="1"
    $env:REMO_RUN_DHW_ITEM_WRITE="1"
    $env:REMO_DHW_SET_TEMP_ITEM_VALUE="48"
    $env:REMO_DHW_COMFORT_ITEM_VALUE="52"
    python standalone_api_live_test.py

Optional DHW comfort/reduced write test (uses set_dhw_temperature with the configured strategy):
    $env:REMO_RUN_WRITE="1"
    $env:REMO_RUN_DHW_WRITE="1"
    $env:REMO_DHW_COMFORT="52"
    $env:REMO_DHW_REDUCED="45"
    python standalone_api_live_test.py

Optional DHW write strategy override:
    $env:REMO_DHW_WRITE_STRATEGY="data_item"
    # or: bsb_plantdata
    python standalone_api_live_test.py

Optional forced failure test for the configured DHW write strategy:
    $env:REMO_RUN_WRITE="1"
    $env:REMO_RUN_DHW_WRITE="1"
    $env:REMO_DHW_WRITE_STRATEGY="data_item"
    $env:REMO_FORCE_DHW_PRIMARY_FAILURE="1"
    python standalone_api_live_test.py

Enable debug output:
    $env:REMO_DEBUG="1"
    python standalone_api_live_test.py

Show full legacy items list in debug output:
    $env:REMO_DEBUG="1"
    $env:REMO_DEBUG_FULL_ITEMS="1"
    python standalone_api_live_test.py

Dump full data payloads (without full request debug noise):
    $env:REMO_DUMP_ALL_DATA="1"
    python standalone_api_live_test.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import types
from typing import Any


SELECTED_LEGACY_ITEMS = [
    ("PlantMode", 0, ["PlantMode"]),
    ("OutsideTemp", 0, ["OutsideTemp"]),
    ("DHW temp", 0, ["DhwTemp", "DhwStorageTemperature"]),
    ("DHW storage temperature", 0, ["DhwStorageTemperature", "DhwTemp"]),
    ("DhwTimeProgComfortTemp", 0, ["DhwTimeProgComfortTemp"]),
    ("DhwTimeProgEconomyTemp", 0, ["DhwTimeProgEconomyTemp"]),
    ("ZoneMode", 1, ["ZoneMode"]),
    ("ZoneDesiredTemp", 1, ["ZoneDesiredTemp"]),
    ("ZoneHeatRequest", 1, ["ZoneHeatRequest"]),
    ("IsHeatingPumpOn", 0, ["IsHeatingPumpOn"]),
    ("IsQuite", 0, ["IsQuite"]),
]


def _load_api_symbols() -> tuple[type, object, object, type]:
    """Load API symbols directly from source files, bypassing HA package imports."""
    repo_root = pathlib.Path(__file__).resolve().parent
    package_root = repo_root / "custom_components" / "elco_remocon"

    if "custom_components" not in sys.modules:
        custom_components_pkg = types.ModuleType("custom_components")
        custom_components_pkg.__path__ = [str(repo_root / "custom_components")]
        sys.modules["custom_components"] = custom_components_pkg

    if "custom_components.elco_remocon" not in sys.modules:
        integration_pkg = types.ModuleType("custom_components.elco_remocon")
        integration_pkg.__path__ = [str(package_root)]
        sys.modules["custom_components.elco_remocon"] = integration_pkg

    const_name = "custom_components.elco_remocon.const"
    if const_name not in sys.modules:
        const_spec = importlib.util.spec_from_file_location(
            const_name,
            package_root / "const.py",
        )
        assert const_spec and const_spec.loader
        const_module = importlib.util.module_from_spec(const_spec)
        sys.modules[const_name] = const_module
        const_spec.loader.exec_module(const_module)

    api_name = "custom_components.elco_remocon.api"
    api_spec = importlib.util.spec_from_file_location(api_name, package_root / "api.py")
    assert api_spec and api_spec.loader
    api_module = importlib.util.module_from_spec(api_spec)
    sys.modules[api_name] = api_module
    api_spec.loader.exec_module(api_module)

    return (
        api_module.RemoconClient,
        api_module._build_features_payload,
        api_module.RemoconApiError,
        api_module.RemoconConnectionError,
    )


RemoconClient, _build_features_payload, RemoconApiError, RemoconConnectionError = _load_api_symbols()


def _debug_enabled() -> bool:
    return os.getenv("REMO_DEBUG", "0") == "1"


def _debug_full_items_enabled() -> bool:
    return os.getenv("REMO_DEBUG_FULL_ITEMS", "1") == "1"


def _dump_all_data_enabled() -> bool:
    return os.getenv("REMO_DUMP_ALL_DATA", "0") == "1"


def _debug(message: str) -> None:
    if _debug_enabled():
        print(f"[DEBUG] {message}")


def _preview(value: Any, max_len: int = 600) -> str:
    try:
        text = json.dumps(value, indent=2, ensure_ascii=True, default=str)
    except Exception:  # noqa: BLE001
        text = repr(value)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n... (truncated)"


def _dump_full_data(label: str, value: Any) -> None:
    """Print a full payload dump when REMO_DUMP_ALL_DATA=1."""
    if not _dump_all_data_enabled():
        return
    try:
        text = json.dumps(value, indent=2, ensure_ascii=True, default=str)
    except Exception:  # noqa: BLE001
        text = repr(value)
    print(f"[DUMP] {label}:\n{text}")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_features(zone: str) -> dict[str, Any] | None:
    raw = os.getenv("REMO_FEATURES_JSON")
    if not raw:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("REMO_FEATURES_JSON must decode to a JSON object")

    payload = _build_features_payload(zone, parsed)
    print("[OK] Loaded custom features payload")
    print(f"     zone override in payload: {payload.get('zones', [{}])[0].get('num')}")
    return parsed


def _coerce_value(raw: str) -> Any:
    lower = raw.strip().lower()
    if lower == "true":
        return True
    if lower == "false":
        return False

    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _optional_float_env(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    return float(raw)


def _optional_float_env_with_default(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _enable_request_debug(client: Any) -> None:
    """Wrap the client request method to print request/response diagnostics."""
    original_request = client._request

    def _wrapped_request(method: str, path: str, **kwargs: Any) -> Any:
        payload = kwargs.get("json")
        _debug(f"HTTP {method} {path}")
        if payload is not None:
            _debug(f"request json preview:\n{_preview(payload)}")

        response = original_request(method, path, **kwargs)
        if isinstance(response, dict):
            _debug(f"response keys: {sorted(response.keys())}")
        else:
            _debug(f"response type: {type(response).__name__}")
        _debug(f"response preview:\n{_preview(response)}")
        return response

    client._request = _wrapped_request


def _force_dhw_primary_failure_enabled() -> bool:
    return os.getenv("REMO_FORCE_DHW_PRIMARY_FAILURE", "0") == "1"


def _run_set_dhw_temperature_with_optional_forced_fallback(
    client: Any,
    comfort: float | None,
    reduced: float | None,
) -> None:
    if not _force_dhw_primary_failure_enabled():
        client.set_dhw_temperature(comfort=comfort, reduced=reduced)
        return

    if getattr(client, "_dhw_write_strategy", "bsb_plantdata") == "data_item":
        primary_method_name = "_set_dhw_temperature_via_data_items"
        secondary_label = "bsbPlantData"
        primary_label = "data items"
    else:
        primary_method_name = "_set_dhw_temperature_via_bsb_plantdata"
        secondary_label = "data items"
        primary_label = "bsbPlantData"

    original_primary = getattr(client, primary_method_name)

    def _forced_failure(comfort_value: float | None, reduced_value: float | None) -> None:
        raise RemoconConnectionError(
            f"Forced primary failure for standalone fallback test via {primary_label}"
        )

    print(
        "    [INFO] Forcing primary DHW write failure to exercise fallback: "
        f"{primary_label} -> {secondary_label}"
    )
    setattr(client, primary_method_name, _forced_failure)
    try:
        client.set_dhw_temperature(comfort=comfort, reduced=reduced)
    finally:
        setattr(client, primary_method_name, original_primary)


def _has_expected_raw_data(raw: Any) -> bool:
    """Return True when raw payload matches known API data shapes.

    Some models return legacy payload as `items` instead of `plantData`/`zoneData`.
    """
    if not isinstance(raw, dict):
        return False

    if raw.get("plantData") or raw.get("zoneData"):
        return True

    items = raw.get("items")
    return isinstance(items, list) and len(items) > 0


def _format_numeric_value(value: Any, decimals: Any) -> str:
    if not isinstance(value, (int, float)):
        return str(value)

    try:
        decimal_places = int(decimals or 0)
    except (TypeError, ValueError):
        decimal_places = 0

    return f"{value:.{decimal_places}f}"


def _find_option_text(item: dict[str, Any], value: Any) -> str | None:
    options = item.get("options")
    opt_texts = item.get("optTexts")
    if not isinstance(options, list) or not isinstance(opt_texts, list):
        return None
    if len(options) != len(opt_texts):
        return None

    for option, label in zip(options, opt_texts):
        if option == value:
            return str(label)
        if isinstance(option, (int, float)) and isinstance(value, (int, float)) and float(option) == float(value):
            return str(label)
    return None


def _format_item_value(item: dict[str, Any]) -> str:
    value = item.get("value")
    option_text = _find_option_text(item, value)
    if option_text is not None:
        return f"{option_text} ({_format_numeric_value(value, item.get('decimals'))})"

    if item.get("kind") == 3 and isinstance(value, (int, float)):
        state = "ON" if float(value) != 0 else "OFF"
        return f"{state} ({_format_numeric_value(value, item.get('decimals'))})"

    text = _format_numeric_value(value, item.get("decimals"))
    unit = item.get("unit")
    if unit:
        return f"{text} {unit}"
    return text


def _find_legacy_item(item_map: dict[tuple[str, int], dict[str, Any]], candidates: list[str], zone: int) -> dict[str, Any] | None:
    for candidate in candidates:
        item = item_map.get((candidate, zone))
        if item is not None:
            return item
    return None


def _print_selected_legacy_values(raw: Any, heading: str = "[INFO] Selected legacy values:") -> None:
    if not isinstance(raw, dict):
        return

    items = raw.get("items")
    if not isinstance(items, list):
        return

    item_map: dict[tuple[str, int], dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        zone = item.get("zone", 0)
        if not isinstance(item_id, str):
            continue
        try:
            zone_num = int(zone)
        except (TypeError, ValueError):
            zone_num = 0
        item_map[(item_id, zone_num)] = item

    print(heading)
    for label, zone, candidates in SELECTED_LEGACY_ITEMS:
        item = _find_legacy_item(item_map, candidates, zone)
        if item is None:
            print(f"  - {label}: <missing>")
            continue
        print(f"  - {label}: {_format_item_value(item)}")


def _warn_if_dhw_items_missing(raw: Any, custom_features: dict[str, Any] | None) -> None:
    """Print actionable hints when DHW items are absent from legacy payload."""
    if not isinstance(raw, dict):
        return
    items = raw.get("items")
    if not isinstance(items, list):
        return

    item_ids: list[str] = [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]
    dhw_ids = [item_id for item_id in item_ids if item_id.lower().startswith("dhw")]
    has_expected_dhw = any(
        key in item_ids
        for key in ("DhwTemp", "DhwStorageTemperature", "DhwTimeProgComfortTemp", "DhwTimeProgEconomyTemp")
    )

    if has_expected_dhw:
        return

    print("[INFO] No expected DHW items found in legacy payload (DhwTemp/DhwStorageTemperature/DhwTimeProg*).")
    if dhw_ids:
        print(f"[INFO] DHW-like ids returned: {', '.join(sorted(dhw_ids))}")
    else:
        print("[INFO] No Dhw* ids returned at all.")

    if custom_features is not None:
        print("[INFO] Custom features payload is active. If it is minimal, try running without REMO_FEATURES_JSON or include DHW-related feature flags.")


def _looks_like_empty_get_data(data: Any) -> bool:
    return (
        getattr(data, "outside_temp", 0.0) == 0.0
        and getattr(data, "room_temp", 0.0) == 0.0
        and getattr(data, "desired_temp", 0.0) == 0.0
        and getattr(data, "comfort_temp", 0.0) == 0.0
        and getattr(data, "reduced_temp", 0.0) == 0.0
        and getattr(data, "system_pressure", None) is None
        and getattr(data, "flow_temperature", None) is None
    )


def _debug_legacy_items(raw: Any) -> None:
    """Print full legacy items list when available."""
    if not _debug_enabled() or not _debug_full_items_enabled():
        return
    if not isinstance(raw, dict):
        return

    items = raw.get("items")
    if not isinstance(items, list):
        return

    try:
        items_text = json.dumps(items, indent=2, ensure_ascii=True, default=str)
    except Exception:  # noqa: BLE001
        items_text = repr(items)

    _debug(f"legacy items full dump ({len(items)} items):\n{items_text}")


def main() -> int:
    email = _required_env("REMO_EMAIL")
    password = _required_env("REMO_PASSWORD")
    gateway_id = _required_env("REMO_GATEWAY_ID")
    zone = os.getenv("REMO_ZONE", "1")
    dhw_write_strategy = os.getenv("REMO_DHW_WRITE_STRATEGY", "data_item")

    custom_features = _parse_features(zone)

    client = RemoconClient(
        email=email,
        password=password,
        gateway_id=gateway_id,
        zone=zone,
        features_payload=custom_features,
        dhw_write_strategy=dhw_write_strategy,
    )

    if _debug_enabled():
        _enable_request_debug(client)
        _debug("Debug mode enabled")
        _debug(
            f"gateway_id={gateway_id}, zone={zone}, "
            f"custom_features={custom_features is not None}, "
            f"dhw_write_strategy={dhw_write_strategy}, "
            f"force_dhw_primary_failure={_force_dhw_primary_failure_enabled()}"
        )

    print("[1/5] Logging in...")
    client.login()
    print("[OK] Login successful")

    print("[2/5] Testing direct legacy read path (_get_raw_legacy)...")
    legacy_raw = client._get_raw_legacy()
    _dump_full_data("Direct legacy raw payload", legacy_raw)
    _debug(f"legacy raw keys: {sorted(legacy_raw.keys()) if isinstance(legacy_raw, dict) else 'n/a'}")
    _debug(f"legacy raw preview:\n{_preview(legacy_raw)}")
    _debug_legacy_items(legacy_raw)
    has_legacy_data = _has_expected_raw_data(legacy_raw)
    if not has_legacy_data:
        raise RuntimeError("Legacy endpoint did not return known data shape (plantData/zoneData or non-empty items)")
    if isinstance(legacy_raw, dict) and isinstance(legacy_raw.get("items"), list):
        print(f"[OK] Direct legacy read returned items-format data ({len(legacy_raw['items'])} items)")
        _print_selected_legacy_values(legacy_raw)
        _warn_if_dhw_items_missing(legacy_raw, custom_features)
    else:
        print("[OK] Direct legacy read returned plant/zone structured data")

    print("[3/5] Testing normal read path...")
    data = client.get_data()
    print(
        "[OK] get_data returned: "
        f"outside_temp={data.outside_temp}, room_temp={data.room_temp}, "
        f"pressure={data.system_pressure}, flow={data.flow_temperature}"
    )
    _dump_full_data("Mapped get_data output", data.__dict__)
    if _looks_like_empty_get_data(data) and isinstance(legacy_raw, dict) and isinstance(legacy_raw.get("items"), list):
        print("[INFO] get_data returned default/empty values; this likely means the BSB path failed and the legacy items-format payload is not mapped by get_data().")

    print("[4/5] Testing fallback endpoint logic (forced BSB empty -> legacy)...")
    original_bsb = client._get_raw_bsb
    try:
        client._get_raw_bsb = lambda: {}  # force fallback path while still using real legacy endpoint
        fallback_raw = client._get_raw()
        _dump_full_data("Fallback raw payload", fallback_raw)
        has_data = _has_expected_raw_data(fallback_raw)
        if not has_data:
            raise RuntimeError("Fallback endpoint did not return known data shape (plantData/zoneData or non-empty items)")
        print("[OK] Fallback call succeeded and returned structured data")
        _print_selected_legacy_values(fallback_raw, heading="[INFO] Selected fallback values:")
        _warn_if_dhw_items_missing(fallback_raw, custom_features)
    finally:
        client._get_raw_bsb = original_bsb

    print("[5/5] Testing optional write paths...")

    run_write = os.getenv("REMO_RUN_WRITE", "0") == "1"
    run_data_item_write_requested = os.getenv("REMO_RUN_DATA_ITEM_WRITE", "0") == "1"
    run_data_item_write = run_write and run_data_item_write_requested
    if run_data_item_write:
        print("  - set_data_item write test enabled")
        item_id = _required_env("REMO_ITEM_ID")
        item_value = _coerce_value(_required_env("REMO_ITEM_VALUE"))
        item_zone = int(os.getenv("REMO_ITEM_ZONE", "0"))
        client.set_data_item(item_id, item_value, zone=item_zone)
        print(f"    [OK] set_data_item succeeded for item={item_id}, value={item_value}, zone={item_zone}")
    else:
        if run_data_item_write_requested and not run_write:
            print(
                "  - set_data_item write test skipped "
                "(set REMO_RUN_WRITE=1 and REMO_RUN_DATA_ITEM_WRITE=1 to enable)"
            )
        else:
            print("  - set_data_item write test skipped (set REMO_RUN_DATA_ITEM_WRITE=1 to enable)")

    run_dhw_item_write_requested = os.getenv("REMO_RUN_DHW_ITEM_WRITE", "0") == "1"
    run_dhw_item_write = run_write and run_dhw_item_write_requested
    if run_dhw_item_write:
        dhw_set_temp_value = _optional_float_env_with_default("REMO_DHW_SET_TEMP_ITEM_VALUE", 48.0)
        dhw_comfort_item_value = _optional_float_env_with_default("REMO_DHW_COMFORT_ITEM_VALUE", 52.0)

        print(
            "  - explicit DHW data-item write test enabled "
            f"(DhwTemp={dhw_set_temp_value}, DhwTimeProgComfortTemp={dhw_comfort_item_value})"
        )
        client.set_data_item("DhwTemp", dhw_set_temp_value, zone=0)
        print(f"    [OK] set_data_item succeeded for item=DhwTemp, value={dhw_set_temp_value}, zone=0")
        client.set_data_item("DhwTimeProgComfortTemp", dhw_comfort_item_value, zone=0)
        print(
            "    [OK] set_data_item succeeded for "
            f"item=DhwTimeProgComfortTemp, value={dhw_comfort_item_value}, zone=0"
        )

        refreshed = client.get_data()
        print(
            "    [INFO] post-item-write get_data: "
            f"dhw_set_temp={refreshed.dhw_set_temp}, "
            f"dhw_comfort_temp={refreshed.dhw_comfort_temp}, "
            f"dhw_reduced_temp={refreshed.dhw_reduced_temp}"
        )
    else:
        if run_dhw_item_write_requested and not run_write:
            print(
                "  - explicit DHW data-item write test skipped "
                "(set REMO_RUN_WRITE=1 and REMO_RUN_DHW_ITEM_WRITE=1 to enable)"
            )
        else:
            print(
                "  - explicit DHW data-item write test skipped "
                "(set REMO_RUN_DHW_ITEM_WRITE=1 to enable)"
            )

    run_dhw_write_requested = os.getenv("REMO_RUN_DHW_WRITE", "0") == "1"
    run_dhw_write = run_write and run_dhw_write_requested
    if run_dhw_write:
        comfort = _optional_float_env("REMO_DHW_COMFORT")
        reduced = _optional_float_env("REMO_DHW_REDUCED")
        if comfort is None and reduced is None:
            raise RuntimeError("REMO_RUN_DHW_WRITE=1 requires REMO_DHW_COMFORT and/or REMO_DHW_REDUCED")

        print(
            "  - set_dhw_temperature write test enabled "
            f"(comfort={comfort}, reduced={reduced}, strategy={dhw_write_strategy})"
        )
        _run_set_dhw_temperature_with_optional_forced_fallback(
            client,
            comfort,
            reduced,
        )
        print("    [OK] set_dhw_temperature call succeeded")

        refreshed = client.get_data()
        print(
            "    [INFO] post-write get_data: "
            f"dhw_set_temp={refreshed.dhw_set_temp}, "
            f"dhw_comfort_temp={refreshed.dhw_comfort_temp}, "
            f"dhw_reduced_temp={refreshed.dhw_reduced_temp}"
        )
    else:
        if run_dhw_write_requested and not run_write:
            print(
                "  - set_dhw_temperature write test skipped "
                "(set REMO_RUN_WRITE=1 and REMO_RUN_DHW_WRITE=1 to enable)"
            )
        else:
            print("  - set_dhw_temperature write test skipped (set REMO_RUN_DHW_WRITE=1 to enable)")

    print("\nAll requested live checks completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RemoconApiError as err:
        print(f"[FAIL] API error: {err}")
        raise SystemExit(2)
    except Exception as err:  # noqa: BLE001
        print(f"[FAIL] {err}")
        raise SystemExit(1)