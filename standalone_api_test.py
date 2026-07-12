"""Standalone smoke tests for the Remocon API client.

Run with:
    python standalone_api_test.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _load_api_symbols() -> tuple[type, object]:
    """Load API symbols directly from source files, bypassing HA package imports."""
    repo_root = pathlib.Path(__file__).resolve().parent
    package_root = repo_root / "custom_components" / "elco_remocon"

    # Create namespace package stubs so relative imports (e.g. .const) work.
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
    api_spec = importlib.util.spec_from_file_location(
        api_name,
        package_root / "api.py",
    )
    assert api_spec and api_spec.loader
    api_module = importlib.util.module_from_spec(api_spec)
    sys.modules[api_name] = api_module
    api_spec.loader.exec_module(api_module)

    return api_module.RemoconClient, api_module._build_features_payload


RemoconClient, _build_features_payload = _load_api_symbols()


def _mock_json_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    return response


class TestRemoconApiStandalone(unittest.TestCase):
    """Simple standalone checks for newly added API behavior."""

    def test_configurable_features_payload(self) -> None:
        custom_features = {
            "zones": [{"num": 99, "name": "Custom Zone", "roomSens": True}],
            "hpSys": True,
            "autoThermoReg": True,
        }

        payload = _build_features_payload("2", custom_features)

        self.assertTrue(payload["hpSys"])
        self.assertTrue(payload["autoThermoReg"])
        self.assertEqual(payload["zones"][0]["num"], 2)
        self.assertEqual(payload["zones"][0]["name"], "Custom Zone")

    @patch("custom_components.elco_remocon.api.requests.Session")
    def test_fallback_from_bsb_to_legacy(self, mock_session_class: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        login_response = _mock_json_response({"ok": True})
        bsb_incomplete = _mock_json_response({"ok": True, "data": {}})
        legacy_success = _mock_json_response(
            {
                "ok": True,
                "data": {
                    "plantData": {"outsideTemp": 23.0},
                    "zoneData": {"roomTemp": 20.0},
                },
            }
        )

        mock_session.request.side_effect = [
            login_response,
            bsb_incomplete,
            legacy_success,
        ]

        client = RemoconClient(
            email="test@example.com",
            password="password",
            gateway_id="TEST123",
            zone="1",
        )

        client.login()
        raw = client._get_raw()

        self.assertEqual(raw["plantData"]["outsideTemp"], 23.0)
        self.assertEqual(raw["zoneData"]["roomTemp"], 20.0)

    @patch("custom_components.elco_remocon.api.requests.Session")
    def test_set_data_item_payload(self, mock_session_class: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        login_response = _mock_json_response({"ok": True})
        get_item_response = _mock_json_response(
            {
                "items": [
                    {"id": "ChFlowSetpointTemp", "value": 25.0},
                ]
            }
        )
        set_response = _mock_json_response({"ok": True})

        mock_session.request.side_effect = [
            login_response,
            get_item_response,
            set_response,
        ]

        client = RemoconClient(
            email="test@example.com",
            password="password",
            gateway_id="TEST123",
            zone="1",
        )

        client.login()
        client.set_data_item("ChFlowSetpointTemp", 28.0, zone=0)

        calls = mock_session.request.call_args_list
        self.assertGreaterEqual(len(calls), 3)

        set_call = calls[-1]
        method = set_call.args[0]
        url = set_call.args[1]
        payload = set_call.kwargs["json"]

        self.assertEqual(method, "POST")
        self.assertIn("/api/v2/remote/dataItems/TEST123/set?umsys=si", url)
        self.assertEqual(payload["items"][0]["id"], "ChFlowSetpointTemp")
        self.assertEqual(payload["items"][0]["prevValue"], 25.0)
        self.assertEqual(payload["items"][0]["value"], 28.0)
        self.assertEqual(payload["items"][0]["zone"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)