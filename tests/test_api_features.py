"""Unit tests for Elco Remocon-Net API client with configurable features."""

import json
from unittest.mock import MagicMock, patch

import pytest

from custom_components.elco_remocon.api import (
    DEFAULT_FEATURES_PAYLOAD,
    RemoconClient,
    RemoconConnectionError,
    RemoconDataError,
    _build_features_payload,
)
from custom_components.elco_remocon.const import (
    READ_STRATEGY_BSB_FIRST,
    READ_STRATEGY_BSB_ONLY,
    READ_STRATEGY_LEGACY_FIRST,
    READ_STRATEGY_LEGACY_ONLY,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_response_base():
    """Base mock response data from the API."""
    return {
        "ok": True,
        "data": {
            "plantData": {
                "outsideTemp": 23.0,
                "dhwStorageTemp": 76.0,
                "dhwEnabled": True,
                "dhwComfortTemp": {"value": 45.0, "min": 35.0, "max": 65.0},
                "dhwReducedTemp": {"value": 40.0, "min": 35.0, "max": 65.0},
                "dhwMode": {"value": 1, "options": [0, 1, 2, 3, 4, 5]},
                "heatPumpOn": False,
                "flameSensor": False,
            },
            "zoneData": {
                "roomTemp": 20.0,
                "desiredRoomTemp": 21.0,
                "chComfortTemp": {"value": 22.0, "min": 5.0, "max": 35.0, "step": 0.5},
                "chReducedTemp": {"value": 18.0, "min": 5.0, "max": 35.0, "step": 0.5},
                "mode": {"value": 1, "allowedOptionTexts": ["Protection", "Automatic", "Reduction", "Comfort"]},
                "isHeatingActive": False,
                "isCoolingActive": False,
                "heatOrCoolRequest": False,
                "hasRoomSensor": False,
            },
        },
    }


@pytest.fixture
def mock_v2_response():
    """Mock v2 API response for system items."""
    return {
        "items": [
            {"id": "HeatingCircuitPressure", "value": 1.5},
            {"id": "ChFlowTemp", "value": 25.0},
        ]
    }


@pytest.fixture
def mock_legacy_items_response():
    """Mock legacy items-format payload returned by some Elco models."""
    return {
        "ok": True,
        "data": {
            "items": [
                {"id": "PlantMode", "zone": 0, "value": 3.0, "options": [0, 1, 2, 3, 5], "optTexts": ["Summer", "Winter", "Heating only", "Cooling", "OFF"]},
                {"id": "OutsideTemp", "zone": 0, "value": 27.0, "decimals": 0, "unit": "\u00b0C"},
                {"id": "ZoneMode", "zone": 1, "value": 2.0, "options": [2, 3], "optTexts": ["Manual", "Time program"]},
                {"id": "ZoneComfortTemp", "zone": 1, "value": 24.0, "min": 10.0, "max": 30.0, "step": 0.5, "decimals": 1, "unit": "\u00b0C"},
                {"id": "ZoneEconomyTemp", "zone": 1, "value": 18.0, "min": 10.0, "max": 30.0, "step": 0.5, "decimals": 1, "unit": "\u00b0C"},
                {"id": "ZoneDesiredTemp", "zone": 1, "value": 24.0, "decimals": 1, "unit": "\u00b0C"},
                {"id": "ZoneMeasuredTemp", "zone": 1, "value": 0.0, "decimals": 1, "unit": "\u00b0C"},
                {"id": "ZoneHeatRequest", "zone": 1, "value": 1.0, "options": [0, 1], "optTexts": ["OFF", "ON"]},
                {"id": "DhwStorageTemperature", "zone": 0, "value": 76.0, "decimals": 0, "unit": "\u00b0C"},
                {"id": "DhwTimeProgComfortTemp", "zone": 0, "value": 55.0, "min": 35.0, "max": 65.0, "step": 1.0, "decimals": 0, "unit": "\u00b0C"},
                {"id": "DhwTimeProgEconomyTemp", "zone": 0, "value": 47.0, "min": 35.0, "max": 65.0, "step": 1.0, "decimals": 0, "unit": "\u00b0C"},
                {"id": "IsHeatingPumpOn", "zone": 0, "value": 0.0, "options": [0, 1]},
                {"id": "IsQuite", "zone": 0, "value": 1.0, "options": [0, 1]},
            ]
        },
    }


@pytest.fixture
def client():
    """Create a test client without login."""
    return RemoconClient(
        email="test@example.com",
        password="password",
        gateway_id="TEST123",
        zone="1",
    )


@pytest.fixture
def client_with_custom_features():
    """Create a test client with custom features payload."""
    custom_features = {
        "zones": [
            {
                "num": 1,
                "name": "Zone 1",
                "roomSens": True,
                "geofenceDeroga": False,
                "virtInfo": {"heatReqMode": 1, "thermoregModeHeat": 3},
                "isHidden": False,
            }
        ],
        "hpSys": True,
        "virtualZones": True,
        "hasMetering": True,
        "autoThermoReg": True,
        "hasBoiler": False,
        "hydraulicScheme": 5,
    }
    return RemoconClient(
        email="test@example.com",
        password="password",
        gateway_id="TEST123",
        zone="1",
        features_payload=custom_features,
    )


# ============================================================================
# Tests: Features Payload Building
# ============================================================================


def test_build_features_payload_with_none():
    """Test that None features uses default payload."""
    payload = _build_features_payload("1", None)
    assert payload == DEFAULT_FEATURES_PAYLOAD
    assert payload["zones"][0]["num"] == 1


def test_build_features_payload_with_custom():
    """Test that custom features are used."""
    custom = {
        "zones": [{"num": 2, "name": "Custom"}],
        "hpSys": True,
        "autoThermoReg": True,
    }
    payload = _build_features_payload("2", custom)
    assert payload["hpSys"] is True
    assert payload["autoThermoReg"] is True
    assert payload["zones"][0]["num"] == 2


def test_build_features_payload_custom_merges_with_defaults():
    """Minimal custom payload should keep default DHW-related keys."""
    custom = {
        "zones": [{"num": 1, "name": "Zone 1"}],
        "hpSys": True,
    }
    payload = _build_features_payload("1", custom)

    assert payload["hpSys"] is True
    assert payload["dhwProgSupported"] is True
    assert payload["dhwBoilerPresent"] is True
    assert payload["dhwModeChangeable"] is True
    assert payload["zones"][0]["name"] == "Zone 1"


def test_build_features_payload_zone_override():
    """Test that zone number is always set from parameter."""
    custom = {"zones": [{"num": 1, "name": "Default"}], "hpSys": False}
    payload = _build_features_payload("3", custom)
    assert payload["zones"][0]["num"] == 3


def test_build_features_payload_empty_zones():
    """Test handling of empty zones list."""
    custom = {"zones": [], "hpSys": True}
    payload = _build_features_payload("1", custom)
    assert len(payload["zones"]) == 1
    assert payload["zones"][0]["num"] == 1


# ============================================================================
# Tests: API Client Read Operations
# ============================================================================


@patch("custom_components.elco_remocon.api.requests.Session")
def test_get_data_success(mock_session_class, client, mock_response_base, mock_v2_response):
    """Test successful data retrieval with both BSB and v2 endpoints."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock login response
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    # Mock raw data response
    raw_response = MagicMock()
    raw_response.status_code = 200
    raw_response.json.return_value = mock_response_base

    # Mock v2 system items response
    v2_response = MagicMock()
    v2_response.status_code = 200
    v2_response.json.return_value = mock_v2_response

    # Setup side effects for sequential calls
    mock_session.request.side_effect = [login_response, raw_response, v2_response]

    client.login()
    data = client.get_data()

    assert data.outside_temp == 23.0
    assert data.dhw_temp == 76.0
    assert data.dhw_enabled is True
    assert data.comfort_temp == 22.0
    assert data.system_pressure == 1.5
    assert data.flow_temperature == 25.0


@patch("custom_components.elco_remocon.api.requests.Session")
def test_get_data_from_legacy_items(mock_session_class, client, mock_legacy_items_response, mock_v2_response):
    """Test mapping of legacy items-format payload to RemoconData."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    raw_response = MagicMock()
    raw_response.status_code = 200
    raw_response.json.return_value = mock_legacy_items_response

    v2_response = MagicMock()
    v2_response.status_code = 200
    v2_response.json.return_value = mock_v2_response

    mock_session.request.side_effect = [login_response, raw_response, v2_response]

    client.login()
    data = client.get_data()

    assert data.outside_temp == 27.0
    assert data.comfort_temp == 24.0
    assert data.reduced_temp == 18.0
    assert data.desired_temp == 24.0
    assert data.dhw_temp == 76.0
    assert data.dhw_comfort_temp == 55.0
    assert data.dhw_reduced_temp == 47.0
    assert data.heat_or_cool_request is True
    assert data.heat_pump_on is False
    assert data.cooling_active is True
    assert data.zone_mode == 3
    assert data.system_pressure == 1.5
    assert data.flow_temperature == 25.0


@patch("custom_components.elco_remocon.api.requests.Session")
def test_get_raw_fallback_on_error(mock_session_class, client, mock_response_base):
    """Test that fallback to legacy endpoint happens on BSB error."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    # First call (BSB) returns data without expected keys, triggers fallback
    # Second call (legacy) succeeds with full data
    incomplete_response = MagicMock()
    incomplete_response.status_code = 200
    incomplete_response.json.return_value = {"ok": True, "data": {}}  # Missing plantData/zoneData

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = mock_response_base

    mock_session.request.side_effect = [login_response, incomplete_response, success_response]

    client.login()

    # Should not raise, fallback should kick in
    raw = client._get_raw()
    assert raw["plantData"]["outsideTemp"] == 23.0


@patch("custom_components.elco_remocon.api.requests.Session")
def test_get_raw_with_custom_features(mock_session_class, client_with_custom_features, mock_response_base):
    """Test that custom features payload is used in legacy read."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    raw_response = MagicMock()
    raw_response.status_code = 200
    raw_response.json.return_value = mock_response_base

    mock_session.request.side_effect = [login_response, raw_response]

    client_with_custom_features.login()

    # Capture the actual request payload
    with patch.object(client_with_custom_features, "_request") as mock_request:
        mock_request.return_value = mock_response_base

        client_with_custom_features._get_raw_legacy()

        # Verify custom features were passed
        call_args = mock_request.call_args
        assert "json" in call_args.kwargs
        payload = call_args.kwargs["json"]
        assert payload["features"]["hpSys"] is True
        assert payload["features"]["autoThermoReg"] is True


# ============================================================================
# Tests: API Client Write Operations
# ============================================================================


@patch("custom_components.elco_remocon.api.requests.Session")
def test_set_dhw_temperature(mock_session_class, client, mock_response_base):
    """Test setting DHW temperatures."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    raw_response = MagicMock()
    raw_response.status_code = 200
    raw_response.json.return_value = mock_response_base

    set_response = MagicMock()
    set_response.status_code = 200
    set_response.json.return_value = {"ok": True}

    mock_session.request.side_effect = [login_response, raw_response, set_response]

    client.login()
    client.set_dhw_temperature(comfort=50.0, reduced=45.0)

    # Verify the write request was made with correct payload
    calls = [c for c in mock_session.request.call_args_list if "/api/v2/remote/bsbPlantData/" in str(c)]
    assert len(calls) > 0


@patch("custom_components.elco_remocon.api.requests.Session")
def test_set_dhw_mode(mock_session_class, client, mock_response_base):
    """Test setting DHW mode."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    set_response = MagicMock()
    set_response.status_code = 200
    set_response.json.return_value = {"ok": True}

    mock_session.request.side_effect = [login_response, set_response]

    client.login()
    client.set_dhw_mode(2)

    # Verify endpoint was called
    calls = [c for c in mock_session.request.call_args_list if "dhwMode" in str(c)]
    assert len(calls) > 0


@patch("custom_components.elco_remocon.api.requests.Session")
def test_set_data_item(mock_session_class, client, mock_response_base, mock_v2_response):
    """Test setting arbitrary data items."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    v2_response = MagicMock()
    v2_response.status_code = 200
    v2_response.json.return_value = mock_v2_response

    set_response = MagicMock()
    set_response.status_code = 200
    set_response.json.return_value = {"ok": True}

    mock_session.request.side_effect = [login_response, v2_response, set_response]

    client.login()
    client.set_data_item("ChFlowSetpointTemp", 28.0, zone=0)

    # Verify the write request was made
    calls = [c for c in mock_session.request.call_args_list if "dataItems" in str(c) and "set" in str(c)]
    assert len(calls) > 0


# ============================================================================
# Tests: Error Handling
# ============================================================================


@patch("custom_components.elco_remocon.api.requests.Session")
def test_login_auth_error(mock_session_class, client):
    """Test authentication error handling."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    error_response = MagicMock()
    error_response.status_code = 401
    mock_session.request.return_value = error_response

    from custom_components.elco_remocon.api import RemoconAuthError

    with pytest.raises(RemoconAuthError):
        client.login()


@patch("custom_components.elco_remocon.api.requests.Session")
def test_empty_data_error(mock_session_class, client):
    """Test error when API returns no data."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"ok": True}

    empty_response = MagicMock()
    empty_response.status_code = 200
    empty_response.json.return_value = {"ok": True, "data": None}

    # legacy_first now retries via BSB when legacy returns empty data.
    mock_session.request.side_effect = [login_response, empty_response, empty_response]

    client.login()

    with pytest.raises(RemoconDataError):
        client._get_raw()


# ============================================================================
# Tests: Feature Flag Combinations
# ============================================================================


def test_features_with_multiple_zones():
    """Test that multiple zones are preserved except first zone number."""
    custom = {
        "zones": [
            {"num": 1, "name": "Zone 1"},
            {"num": 2, "name": "Zone 2"},
            {"num": 3, "name": "Zone 3"},
        ],
        "hpSys": True,
    }
    payload = _build_features_payload("1", custom)
    assert len(payload["zones"]) == 3
    assert payload["zones"][0]["num"] == 1  # First zone overridden
    assert payload["zones"][1]["num"] == 2  # Other zones unchanged
    assert payload["zones"][2]["num"] == 3


def test_features_payload_preserves_custom_fields():
    """Test that all custom fields are preserved in payload."""
    custom = {
        "zones": [{"num": 1, "customField": "customValue"}],
        "hpSys": True,
        "customTopLevel": "value",
        "customNumber": 42,
    }
    payload = _build_features_payload("1", custom)
    assert payload["zones"][0]["customField"] == "customValue"
    assert payload["customTopLevel"] == "value"
    assert payload["customNumber"] == 42
    assert payload["hpSys"] is True


# ============================================================================
# Tests: Read strategy selection
# ============================================================================


def test_get_raw_legacy_first_fallbacks_to_bsb_on_legacy_error(client):
    """Legacy-first strategy should fall back to BSB when legacy fails."""
    client._read_strategy = READ_STRATEGY_LEGACY_FIRST

    with patch.object(client, "_get_raw_legacy", side_effect=RemoconConnectionError("legacy failed")) as mock_legacy:
        with patch.object(client, "_get_raw_bsb", return_value={"plantData": {"outsideTemp": 23.0}}) as mock_bsb:
            raw = client._get_raw()

    assert raw["plantData"]["outsideTemp"] == 23.0
    mock_legacy.assert_called_once()
    mock_bsb.assert_called_once()


def test_get_raw_bsb_first_fallbacks_to_legacy_on_bsb_error(client):
    """BSB-first strategy should fall back to legacy when BSB fails."""
    client._read_strategy = READ_STRATEGY_BSB_FIRST

    with patch.object(client, "_get_raw_bsb", side_effect=RemoconConnectionError("bsb failed")) as mock_bsb:
        with patch.object(client, "_get_raw_legacy", return_value={"plantData": {"outsideTemp": 21.0}}) as mock_legacy:
            raw = client._get_raw()

    assert raw["plantData"]["outsideTemp"] == 21.0
    mock_bsb.assert_called_once()
    mock_legacy.assert_called_once()


def test_get_raw_legacy_only_does_not_call_bsb(client):
    """Legacy-only strategy should not call BSB endpoint."""
    client._read_strategy = READ_STRATEGY_LEGACY_ONLY

    with patch.object(client, "_get_raw_legacy", return_value={"plantData": {"outsideTemp": 19.0}}) as mock_legacy:
        with patch.object(client, "_get_raw_bsb") as mock_bsb:
            raw = client._get_raw()

    assert raw["plantData"]["outsideTemp"] == 19.0
    mock_legacy.assert_called_once()
    mock_bsb.assert_not_called()


def test_get_raw_bsb_only_does_not_call_legacy(client):
    """BSB-only strategy should not call legacy endpoint."""
    client._read_strategy = READ_STRATEGY_BSB_ONLY

    with patch.object(client, "_get_raw_bsb", return_value={"plantData": {"outsideTemp": 17.0}}) as mock_bsb:
        with patch.object(client, "_get_raw_legacy") as mock_legacy:
            raw = client._get_raw()

    assert raw["plantData"]["outsideTemp"] == 17.0
    mock_bsb.assert_called_once()
    mock_legacy.assert_not_called()
