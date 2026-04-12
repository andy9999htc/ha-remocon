# ha-remocon

**Inoffizielle Home Assistant Integration für Elco Wärmepumpen über die Remocon-Net Cloud.**

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=macschlingel&repository=ha-remocon&category=integration)

Steuerung und Überwachung von Elco Wärmepumpen (z.B. Aerotop SPK) über die Remocon-Net Cloud API — direkt in Home Assistant, ohne Umweg über MQTT oder AppDaemon.

> **Hinweis:** Dies ist ein inoffizielles Community-Projekt. Es wird weder von Elco noch von der Ariston Thermo Group unterstützt oder autorisiert.

## Features

- **Climate Entity** — Solltemperatur einstellen, Betriebsmodus wechseln (Auto/Heat/Off), Presets (Comfort/Reduced)
- **Sensoren** — Außentemperatur, Vorlauftemperatur, Solltemperatur, Systemdruck
- **Binary Sensors** — Heizung aktiv, Wärmepumpe läuft, Kühlung aktiv
- **Config Flow** — Einfache Einrichtung direkt in der HA-Oberfläche
- **CLI Tool** — Standalone `remocon.py` zum Testen und Debuggen im Terminal

## Voraussetzungen

- Elco Wärmepumpe mit Remocon-Net Gateway (verbunden mit dem Internet)
- Remocon-Net Account ([remocon-net.remotethermo.com](https://www.remocon-net.remotethermo.com))
- Home Assistant >= 2024.1.0
- [HACS](https://hacs.xyz/) installiert

## Installation

### Über HACS (empfohlen)

1. HACS in Home Assistant öffnen
2. **≡ Menu** → **Custom Repositories**
3. Folgendes hinzufügen:
   - **URL:** `https://github.com/macschlingel/ha-remocon`
   - **Kategorie:** Integration
4. In HACS nach **"Remocon-Net"** suchen und installieren
5. Home Assistant neustarten

### Manuell

```bash
cd /pfad/zu/homeassistant/config/custom_components/
git clone https://github.com/macschlingel/ha-remocon.git elco_remocon_temp
cp -r elco_remocon_temp/custom_components/elco_remocon ./
rm -rf elco_remocon_temp
```

Home Assistant neustarten.

## Einrichtung

1. **Einstellungen → Integrationen → Hinzufügen**
2. Nach **"Remocon-Net"** suchen
3. Login-Daten eingeben:
   - **E-Mail:** Deine Remocon-Net E-Mail
   - **Passwort:** Dein Remocon-Net Passwort
   - **Gateway ID:** Die ID deiner Anlage (siehe unten)
   - **Zone:** Zone der Heizung (Standard: 1)

### Gateway ID finden

1. Auf [remocon-net.remotethermo.com](https://www.remocon-net.remotethermo.com) einloggen
2. Die Gateway ID steht in der URL, z.B. `A1B2C3D4E5F6` in:
   ```
   https://www.remocon-net.remotethermo.com/R2/Plant/Index/A1B2C3D4E5F6
   ```

## Entities

Nach der Einrichtung werden folgende Entities erstellt:

| Entity | Typ | Beschreibung |
|--------|-----|-------------|
| `climate.remocon_net_heat_pump` | Climate | Temperatursteuerung, Modus, Presets |
| `sensor.outside_temperature` | Sensor | Außentemperatur |
| `sensor.desired_temperature` | Sensor | Aktuelle Solltemperatur |
| `sensor.reduced_temperature` | Sensor | Reduzierte Temperatur |
| `sensor.flow_temperature` | Sensor | Vorlauftemperatur |
| `sensor.system_pressure` | Sensor | Systemdruck (bar) |
| `binary_sensor.heating_active` | Binary | Heizung aktiv |
| `binary_sensor.cooling_active` | Binary | Kühlung aktiv |
| `binary_sensor.heat_pump_on` | Binary | Wärmepumpe läuft |

### Climate Entity

Die Climate Entity unterstützt:

- **HVAC Modi:** `Heat` (Comfort), `Auto` (Zeitprogramm), `Off` (Frostschutz)
- **Presets:** `Comfort`, `Reduced`
- **Temperatur:** Einstellbar im vom System vorgegebenen Bereich

## CLI Tool

Für Tests und Debugging liegt ein Standalone-CLI-Tool bei:

```bash
pip install -r requirements.txt

# config.json anlegen
cp config.example.json config.json
# Email, Passwort und Gateway ID eintragen

# Status abfragen
python3 remocon.py --config-file config.json status

# Temperatur setzen
python3 remocon.py --config-file config.json set-temp --comfort 22.0

# Modus wechseln
python3 remocon.py --config-file config.json set-mode comfort

# Raw API Response (Debug)
python3 remocon.py --config-file config.json raw-get

# JSON Output (für Skripte)
python3 remocon.py --config-file config.json status --json
```

## Bekannte Einschränkungen

- **Cloud-Abhängig:** Die Steuerung läuft über die Remocon-Net Cloud. Bei Internetausfall ist keine Steuerung möglich.
- **Polling:** Daten werden alle 2 Minuten abgerufen (kein Echtzeit-Streaming).
- **Kein Raumtemperatur-Sensor:** Wenn kein Raumthermostat angeschlossen ist, zeigt `current_temperature` den Sollwert.
- **Read-only DHW:** Warmwasser-Entities werden angezeigt, die Steuerung ist noch nicht über die HA-Entity verfügbar (funktioniert aber über das CLI).

## Technische Details

Die Integration nutzt die gleiche API wie die Elco Remocon-Net Web-App:

- **Login:** Cookie-basierte Authentifizierung über `/R2/Account/Login`
- **Daten:** R2 Web API (`/R2/PlantHomeBsb/GetData/`) + v2 REST API (`/api/v2/remote/dataItems/`)
- **Steuerung:** v2 REST API (`/api/v2/remote/bsbZones/`, `/api/v2/remote/bsbPlantData/`)
- **Plattform:** remotethermo.com (Ariston Thermo Group)

## Mitwirken

Beiträge sind willkommen! Bitte erstelle ein Issue oder einen Pull Request.

## Lizenz

MIT
