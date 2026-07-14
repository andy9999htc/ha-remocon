# ha-remocon

**Unofficial Home Assistant integration for Elco heat pumps via the Remocon-Net cloud service.**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=macschlingel&repository=ha-remocon&category=integration)

Control and monitor your Elco heat pump (e.g. Aerotop SPK) through the Remocon-Net cloud API — directly in Home Assistant, no MQTT or AppDaemon needed.

> **Disclaimer:** This is an unofficial community project. It is not endorsed by or affiliated with Elco or the Ariston Thermo Group.

## Changelog

### Unreleased

- No unreleased changes yet.

### v0.2.4

- Improved cloud polling robustness with coordinator-level retries (3 attempts with 10-second delay) for transient Remocon connectivity failures.
- Added delayed connection error escalation: transient failures are kept at debug level and only escalated after repeated consecutive failures.
- Reduced API log noise by suppressing immediate error-level logs for intermittent request failures; persistent failures still escalate and recovery is logged.

### v0.2.3

- Reduced noisy error logging when the BSB GetData endpoint returns HTTP 500 on unsupported models.
- Added explicit info-level logging for this compatibility case and clarified that legacy endpoint fallback is used when the configured read strategy allows it.

### v0.2.2

- Added writable Home Assistant Number entity for DHW setpoint temperature (maps to `DhwTemp`).
- Added writable Home Assistant Select entity for Plant Mode (maps to `PlantMode`).
- Added dedicated API helpers for the new setters (`set_dhw_set_temp`, `set_plant_mode`).
- Fixed DHW temperature mapping so sensor value prefers storage temperature (`DhwStorageTemperature`) with `DhwTemp` as fallback.
- Added translations and test coverage for the new writable entities and setters.

### v0.2.1

- Added configurable API read strategy with integration/UI support (`legacy_first` default, plus `bsb_first`, `legacy_only`, `bsb_only`).
- Added options-flow support to change read strategy after initial setup.
- Improved compatibility for models that return legacy `items` payloads instead of `plantData/zoneData` by mapping known climate/sensor values into integration data.
- Added safer custom features handling: custom `features_payload` now merges with defaults (instead of replacing them), avoiding accidental loss of required DHW/legacy flags.
- Fixed DHW temperature mapping for legacy items payloads: `DhwStorageTemperature` is now preferred for reported DHW temperature, with `DhwTemp` as fallback.
- Reduced noisy non-debug logging for HTTP 500 HTML error pages (concise message by default, full body only in debug).
- Extended standalone live test diagnostics with direct legacy read validation, selected key-value output for legacy/fallback data, and optional full legacy `items` debug dump.
- Added standalone full-data dump mode (`REMO_DUMP_ALL_DATA=1`) to print full payload details without request-level debug noise.
- Added and documented validated automation item IDs and examples for real-device writes (`DhwTemp`, `PlantMode`) in the README.

## Features

- **Climate entity** — Set target temperature, switch operation mode (Auto / Heat / Off), presets (Comfort / Reduced)
- **Sensors** — Outside temperature, flow temperature, target temperature, system pressure
- **Binary sensors** — Heating active, cooling active, heat pump running
- **Config flow** — Easy setup directly in the Home Assistant UI
- **Writable controls** — DHW setpoint Number + Plant Mode Select entities
- **CLI tool** — Standalone `remocon.py` for testing and debugging from the terminal

## Requirements

- Elco heat pump with a Remocon-Net gateway (connected to the internet)
- Remocon-Net account ([remocon-net.remotethermo.com](https://www.remocon-net.remotethermo.com))
- Home Assistant >= 2024.1.0
- [HACS](https://hacs.xyz/) installed

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. **≡ Menu** → **Custom Repositories**
3. Add:
   - **URL:** `https://github.com/andy9999htc/ha-remocon`
   - **Category:** Integration
4. Search for **"Remocon-Net"** in HACS and install
5. Restart Home Assistant

### Manual

```bash
cd /path/to/homeassistant/config/custom_components/
git clone https://github.com/andy9999htc/ha-remocon.git elco_remocon_temp
cp -r elco_remocon_temp/custom_components/elco_remocon ./
rm -rf elco_remocon_temp
```

Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Remocon-Net"**
3. Enter your credentials:
   - **Email:** Your Remocon-Net login email
   - **Password:** Your Remocon-Net login password
   - **Gateway ID:** Your system's gateway ID (see below)
   - **Zone:** Heating zone (default: 1)
   - **Read strategy:** API read order/selection (default: `legacy_first`)
   - **Custom features payload (JSON, optional):** For model-specific API features

### Read strategy options

The integration supports selectable API read strategies:

- `legacy_first` (default): Read legacy PlantHome first, fallback to BSB
- `bsb_first`: Read BSB first, fallback to legacy PlantHome
- `legacy_only`: Use only legacy PlantHome
- `bsb_only`: Use only BSB

You can change this later via **Settings → Devices & Services → Remocon-Net → Configure** (options flow).

### Finding your Gateway ID

1. Log in at [remocon-net.remotethermo.com](https://www.remocon-net.remotethermo.com)
2. The gateway ID is shown in the URL, e.g. `A1B2C3D4E5F6` in:
   ```
   https://www.remocon-net.remotethermo.com/R2/Plant/Index/A1B2C3D4E5F6
   ```

## Entities

After setup, the following entities are created:

| Entity | Type | Description |
|--------|------|-------------|
| `climate.remocon_net_heat_pump` | Climate | Temperature control, mode, presets |
| `sensor.outside_temperature` | Sensor | Outside temperature |
| `sensor.desired_temperature` | Sensor | Current target temperature |
| `sensor.reduced_temperature` | Sensor | Reduced setpoint temperature |
| `sensor.flow_temperature` | Sensor | Flow temperature |
| `sensor.system_pressure` | Sensor | System pressure (bar) |
| `number.dhw_set_temperature` | Number | Writable DHW setpoint temperature |
| `select.plant_mode` | Select | Writable plant mode (`Summer/Winter/Heating only/Cooling/OFF`) |
| `binary_sensor.heating_active` | Binary | Heating is active |
| `binary_sensor.cooling_active` | Binary | Cooling is active |
| `binary_sensor.heat_pump_on` | Binary | Heat pump is running |

## Services

The integration also registers admin services for advanced model-specific control:

- `elco_remocon.set_dhw_mode`
- `elco_remocon.set_dhw_temperature`
- `elco_remocon.set_data_item`

If multiple Remocon entries are configured, pass `entry_id` in the service data.

### Climate entity

The climate entity supports:

- **HVAC modes:** `Heat` (Comfort), `Auto` (time program), `Off` (frost protection)
- **Presets:** `Comfort`, `Reduced`
- **Temperature:** Adjustable within the range configured on the heat pump

## CLI Tool

A standalone CLI tool is included for testing and debugging:

```bash
pip install -r requirements.txt

# Create config
cp config.example.json config.json
# Edit config.json with your email, password and gateway ID

# Check status
python3 remocon.py --config-file config.json status

# Set temperature
python3 remocon.py --config-file config.json set-temp --comfort 22.0

# Change mode
python3 remocon.py --config-file config.json set-mode comfort

# Raw API response (debug)
python3 remocon.py --config-file config.json raw-get

# JSON output (for scripting)
python3 remocon.py --config-file config.json status --json
```

## Standalone API test scripts

Two standalone scripts are included for API-focused validation outside Home Assistant.

### 1) Mocked script (no real cloud connection)

`standalone_api_test.py` runs unit-style checks with mocked HTTP calls.

It validates:

- Configurable `features` payload handling
- Fallback from BSB endpoint to legacy endpoint
- `set_data_item` request payload construction

Run:

```bash
python standalone_api_test.py
```

### 2) Live script (real Remocon-Net connection)

`standalone_api_live_test.py` performs real API calls using environment variables.

Default behavior:

- Logs in
- Tests direct legacy read path
- Runs read checks (`get_data`)
- Exercises fallback logic (forces empty BSB result and verifies legacy endpoint data)
- Prints selected legacy/fallback values for key items
- Skips write test unless explicitly enabled

PowerShell example:

```powershell
$env:REMO_EMAIL="you@example.com"
$env:REMO_PASSWORD="your-password"
$env:REMO_GATEWAY_ID="YOUR_GATEWAY"
python standalone_api_live_test.py
```

Optional write test (`set_data_item`):

```powershell
$env:REMO_RUN_WRITE="1"
$env:REMO_ITEM_ID="ChFlowSetpointTemp"
$env:REMO_ITEM_VALUE="28.0"
$env:REMO_ITEM_ZONE="0"
python standalone_api_live_test.py
```

Optional custom features payload for live test:

```powershell
$env:REMO_FEATURES_JSON='{"zones":[{"num":1,"name":"Zone 1"}],"hpSys":true}'
python standalone_api_live_test.py
```

Known-good Elco example (returns DHW and extended legacy items on some models):

```powershell
$env:REMO_FEATURES_JSON='{"zones":[{"num":1,"name":"Zone 1"}],"hpSys":true,"dhwProgSupported":true,"virtualZones":true,"dhwBoilerPresent":true,"dhwModeChangeable":true,"autoThermoReg":true,"hasMetering":true,"useCache":true,"zone":1,"filter":{"notEssentials":true,"progId":null,"plant":true,"zone":true,"dhw":true}}'
python standalone_api_live_test.py
```

Note: custom features are merged with integration defaults. You can provide only model-specific overrides and keep baseline flags.

Optional debug output for live test:

```powershell
$env:REMO_DEBUG="1"
python standalone_api_live_test.py
```

Optional full legacy `items` dump in debug mode:

```powershell
$env:REMO_DEBUG="1"
$env:REMO_DEBUG_FULL_ITEMS="1"
python standalone_api_live_test.py
```

### Automation item IDs (validated)

The following `set_data_item` IDs have been validated with real-device testing:

- `DhwTemp` (zone `0`) — DHW setpoint temperature write
- `PlantMode` (zone `0`) — plant mode read (and candidate for mode switching writes)

Set DHW setpoint to 45 C:

```powershell
$env:REMO_RUN_WRITE="1"
$env:REMO_ITEM_ID="DhwTemp"
$env:REMO_ITEM_VALUE="45"
$env:REMO_ITEM_ZONE="0"
python standalone_api_live_test.py
```

PlantMode values observed in payload:

- `0` = Summer
- `1` = Winter
- `2` = Heating only
- `3` = Cooling
- `5` = OFF

Try a PlantMode write (example: Winter):

```powershell
$env:REMO_RUN_WRITE="1"
$env:REMO_ITEM_ID="PlantMode"
$env:REMO_ITEM_VALUE="1"
$env:REMO_ITEM_ZONE="0"
python standalone_api_live_test.py
```

### Home Assistant automation examples

Set DHW setpoint to 45 C via Number entity:

```yaml
action:
   - service: number.set_value
      target:
         entity_id: number.dhw_set_temperature
      data:
         value: 45
```

Set Plant Mode to Winter via Select entity:

```yaml
action:
   - service: select.select_option
      target:
         entity_id: select.plant_mode
      data:
         option: Winter
```

## Known limitations

- **Cloud-dependent:** Control goes through the Remocon-Net cloud. No control possible during internet outages.
- **Polling:** Data is fetched every 2 minutes (no real-time streaming).
- **No room sensor:** If no room thermostat is connected, `current_temperature` shows the target value.
- **Model differences:** Writable item availability and accepted value ranges can vary by model/firmware; verify values with the standalone live script when in doubt.

- **Model-specific features:** Some models require custom `features` payload values to expose all readable/writable data items.

- **Model-specific payload shape:** Some models return legacy `items` format instead of `plantData/zoneData`; this integration now maps known legacy items for core climate/sensor values.

## Technical details

The integration uses the same API as the Elco Remocon-Net web app:

- **Login:** Cookie-based authentication via `/R2/Account/Login`
- **Data:** R2 Web API (`/R2/PlantHome/GetData/`, `/R2/PlantHomeBsb/GetData/`) + v2 REST API (`/api/v2/remote/dataItems/`)
- **Control:** v2 REST API (`/api/v2/remote/bsbZones/`, `/api/v2/remote/bsbPlantData/`)
- **Platform:** remotethermo.com (Ariston Thermo Group)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT
