# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant configuration for an SDI (home automation) installation. Contains both standard HA YAML configs and a custom integration called **modbushas** that communicates with a Fatek PLC over Modbus TCP (192.168.100.3:502).

The project language context is Polish — comments, commit messages, and some YAML names are in Polish.

## Running Home Assistant

```bash
py -m homeassistant --config c:\priv\dom\sdi\homeassistant-config --open-ui
```

HA version: 2026.3.4 (check `.HA_VERSION` for current).

## Architecture

### Configuration structure

- `configuration.yaml` — main entry point; uses `!include` and `!include_dir_merge_list` to split config across files
- `include/` — YAML configs for entities: lights, binary sensors, switches, sensors (split into `sensors/`), scenes, groups, automations, notify, climate, media player
- `customize.yaml` — entity display customization (friendly names, icons)
- `secrets.yaml` — sensitive values (not committed)

### Custom integration: modbushas (`custom_components/modbushas/`)

A custom Home Assistant integration that wraps the built-in `modbus` integration to provide specialized entity platforms for the Fatek PLC:

- **`__init__.py`** — Integration setup; discovers and loads platforms from YAML config. Handles both dict and list config structures from `!include` expansion.
- **`light/light.py`** — Light entities controlled via Modbus coils/registers
- **`binary_sensor/binary_sensor.py`** — Binary sensor entities reading Modbus inputs
- **`sensor/sensor.py`** — Sensor entities (temperature, etc.) reading Modbus registers
- **`switch/switch.py`** — Switch entities controlled via Modbus coils
- **`climate.py`**, **`cover.py`**, **`notify.py`** — Additional platform implementations

Each platform subdir has its own `__init__.py` that re-exports `async_setup_platform`.

The integration is configured under the `modbushas:` key in `configuration.yaml`, with each platform referencing an include file.

### core-master/

A local copy of the Home Assistant core repository, used as reference. It is gitignored and not part of this project's code.

## Key Patterns

- Entity configs in `include/*.yaml` use `platform: modbushas` and specify Modbus addresses (coils, registers, slave IDs)
- The modbushas integration uses `discovery.load_platform()` (YAML-based setup, not config entries)
- Logging for modbushas can be enabled in `configuration.yaml` under `logger.logs`
