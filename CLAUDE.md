# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The project language context is Polish — comments, commit messages, and some YAML names are in Polish.

## Project Overview

Home Assistant configuration for an SDI (home automation) installation in a two-story house. Contains both standard HA YAML configs and a custom integration called **modbushas** that communicates with a Fatek PLC over Modbus TCP (192.168.100.3:502).

The system controls: lights (~60 on/off via Modbus coils), roller shutters/covers (~25 via Modbus registers), temperature sensors, heating (CO/CWU), garden irrigation, alarm, and media player (Onkyo).

## Environments

### Working directory (this repo)

`d:\priv\dom\SDI\homeassistant-config` — local development/editing on Windows. HA can be run locally for testing:

```bash
py -m homeassistant --config c:\priv\dom\sdi\homeassistant-config --open-ui
```

### Production (Raspberry Pi 5)

- Accessible as mapped network drive **Y:** (Samba share from the Pi)
- HA version on production: **2026.7.4** (check `Y:\.HA_VERSION` for current)
- HA is running on the Pi — `Y:\.ha_run.lock` indicates active instance
- Python version on Pi: **3.14** (visible from `__pycache__` .pyc files)

### Deployment

Script `deploy.sh` (bash) copies changed files from this repo to `Y:`:
- Copies `.py`, `.md`, `.json`, `.yaml` files from root (without recursion), `custom_components/` and `include/` (recursively)
- Skips `secrets.yaml`
- Only copies files that differ (uses `diff -q`)
- Run with: `bash deploy.sh`

After deploying, HA on the Pi needs to be restarted to pick up changes.

## Configuration structure

- `configuration.yaml` — main entry point; uses `!include` to load platform configs
- `include/` — YAML configs for entities:
  - `light.yaml` — ~60 lights (Modbus coils, grouped by floor/room)
  - `binary_sensor.yaml` — binary sensors (heating state, pump status)
  - `switch.yaml` — switches (heating calendar, vacation mode, CO/CWU control via Modbus registers)
  - `covers.yaml` — ~25 roller shutters (Modbus registers, grouped by room)
  - `sensors/sensors-modbus.yaml` — Modbus register sensors (temperatures, heater stats)
  - `sensors/sensors-template.yaml` — template sensors (derived values)
  - `sensors/sensors-weather.yaml` — weather sensors
  - `climate.yaml`, `mediaplayer.yaml`, `notify.yaml`, `scene.yaml` — other platforms
  - `automation/` — sunrise/sunset automations (light scripts)
  - `group/` — entity groups by floor (parter, pietro, otoczenie, ogrzewanie)
- `customize.yaml` — entity display customization (friendly names, icons)
- `secrets.yaml` — sensitive values (not committed, not deployed)
- `automations.yaml` — HA automations (alarm-triggered scene)
- `scripts.yaml` — HA scripts (gate control, night/day lighting scenes, irrigation, bedroom scene)
- `scenes.yaml` — HA scenes

## Custom integration: modbushas (`custom_components/modbushas/`)

A custom Home Assistant integration that wraps the built-in `modbus` integration to provide specialized entity platforms for the Fatek PLC. Version 1.0.0, depends on `modbus`, iot_class: `local_polling`.

### Core (`__init__.py`)

- **ModbusWriteClient** — dedicated Modbus TCP connection for write operations (separate from the main hub's read connection to avoid lock contention)
- **PlcCommandSender** — sends structured commands to PLC via registers. Command format: `R[X]` = program code, `R[X+1..]` = parameters (count = code // 100). Command register configured as `command_register: 190` in YAML
- **Service `modbushas.write_register`** — HA service for writing a single Modbus register (used in scripts.yaml for gate, irrigation, phone notification commands)
- Auto-discovers host/port from the `modbus:` config section (hub "fatek")

### Platform modules

Each platform lives in its own subdirectory with `__init__.py` (re-exports `async_setup_platform`) and the main module:

| Platform | File | Modbus type | Buffer class | Entity |
|---|---|---|---|---|
| **light** | `light/light.py` | Coils (on/off) | `ModbusCoilBuffer` | `ModbusHASLight` |
| **binary_sensor** | `binary_sensor/binary_sensor.py` | Coils (read-only) | `ModbusCoilBuffer` | `ModbusHASBinarySensor` |
| **sensor** | `sensor/sensor.py` | Holding registers | `ModbusRegisterBuffer` | `ModbusHASSensor` |
| **switch** | `switch/switch.py` | Coils or registers | Both buffer types | `ModbusHASSwitch` |
| **cover** | `cover/cover.py` | Holding registers | `ModbusCoverRegisterBuffer` | `ModbusHASCover` |
| **climate** | `climate.py` | — | — | Climate entity |
| **notify** | `notify.py` | — | — | Notification service |

### Key patterns

- **Buffer pattern**: Each platform uses a shared buffer (`ModbusCoilBuffer` or `ModbusRegisterBuffer`) that reads a contiguous range of coils/registers in one Modbus call, then serves individual entity reads from cache. Reduces Modbus traffic significantly.
- **Dual write path**: Write operations use `ModbusWriteClient` (dedicated TCP connection) if available, falling back to the main `modbus` hub. This prevents writes from blocking behind the hub's global asyncio.Lock on reads.
- **Fatek D register offset**: D registers in Fatek PLC have Modbus address = D number + 6000 (constant `FATEK_D_REGISTER_OFFSET`).
- **Cover set_position simulation**: PLC doesn't support set_position natively. HA calculates movement time from current/target position and sends UP/DOWN + delayed STOP.
- **Cover register layout**: 6 consecutive D registers per cover: device_type, motor_down, motor_up, total_time (deciseconds), status (0-6), position (deciseconds).
- **Cover commands**: Via PlcCommandSender, program 301 with 3 params: [base_register, command_code (0=stop, 1=down, 2=up), 0].
- Entity configs in `include/*.yaml` use `platform: modbushas` and specify Modbus addresses (coils, registers, slave IDs).
- The integration uses `discovery.load_platform()` (YAML-based setup, not config entries).
- `should_poll = False` on all entities — updates are driven by `async_track_time_interval` callbacks.

### Modbus address map (Fatek PLC, slave 1)

- **Coils 0-77**: Lights (on/off)
- **Coils 43-48, 148, 161**: Heating/pump binary sensors
- **Registers 190+**: Command register (PlcCommandSender)
- **Registers 501-549**: Heating sensors and switches (working time, temperatures, CO/CWU control)
- **Register 1000+**: Notification commands (e.g. 1000=phone, 1049=garden)
- **Registers 1204-1719**: Cover data (D registers, groups of 7 per cover)
- **Registers 7923+**: Temperature setpoints

## Other files

- `start.bat` — launches HA locally on Windows
- `rolety.csv` — reference data for roller shutter configuration
- `core-master/` — local copy of HA core repo (gitignored, reference only)
- `blueprints/` — HA blueprint configs
- `.storage/` — HA internal storage (partially gitignored)
- `deps/` — HA dependency cache (gitignored)
- `h:/`, `y:/` — artifacts of mapped drive paths, can be ignored in git

## Logging

Configured in `configuration.yaml` under `logger.logs`:
- `custom_components.modbushas: info` — modbushas integration logging enabled
- Default level: `warning`
