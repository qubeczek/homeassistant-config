"""
Platforma cover dla integracji Modbus HAS.
Obsługa rolet sterowanych przez PLC Fatek via Modbus TCP.

Tablica danych rolety w rejestrach D (od bazowego adresu N):
  D[N]   — typ urządzenia PLC (21 = roleta)
  D[N+1] — numer wyjścia PLC: silnik w dół (stała konfiguracyjna)
  D[N+2] — numer wyjścia PLC: silnik w górę (stała konfiguracyjna)
  D[N+3] — całkowity czas otwarcia/zamknięcia (sekundy)
  D[N+4] — status: 0=otwarta, 1=częściowo(ruch w górę), 2=częściowo(ruch w dół), 3=zamknięta
  D[N+5] — pozycja zakończenia ostatniego ruchu (w sekundach, 0=otwarta, D[N+3]=zamknięta)

Komendy przez rejestry R:
  R[X]   — bazowy adres D rolety
  R[X+1] — kod polecenia: 0=stop, 1=down, 2=up, 3=set_position
  R[X+2] — docelowy czas w sekundach (tylko dla komendy 3)
"""
import logging
import voluptuous as vol
import datetime
import asyncio

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import callback

from homeassistant.components.modbus.const import (
    MODBUS_DOMAIN,
    CALL_TYPE_REGISTER_HOLDING,
)

from custom_components.modbushas import DATA_WRITE_CLIENT

from homeassistant.const import (
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_NAME,
)

from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
)

from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_REGISTER = "register"
CONF_COVERS = "covers"
CONF_HUB = "hub"
CONF_COMMAND_REGISTER = "command_register"

# Kody komend PLC
CMD_STOP = 0
CMD_DOWN = 1
CMD_UP = 2
CMD_SET_POSITION = 3

# Statusy PLC
STATUS_OPEN = 0
STATUS_PARTIAL_UP = 1
STATUS_PARTIAL_DOWN = 2
STATUS_CLOSED = 3

# Offsety rejestrów w tablicy danych rolety
REG_DEVICE_TYPE = 0
REG_MOTOR_DOWN = 1
REG_MOTOR_UP = 2
REG_TOTAL_TIME = 3
REG_STATUS = 4
REG_POSITION = 5
REG_COUNT = 6  # łączna liczba rejestrów na roletę

# Offset adresu Modbus: rejestry D w Fateku mają adres o 6000 wyższy niż numer rejestru D
FATEK_D_REGISTER_OFFSET = 6000

COVERS_SCHEMA = vol.Schema({
    vol.Required(CONF_REGISTER): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_SLAVE): cv.positive_int,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
})

PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): "modbushas",
    vol.Optional(CONF_HUB): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL): vol.Any(cv.positive_int, cv.positive_float),
    vol.Required(CONF_COMMAND_REGISTER): cv.positive_int,
    vol.Required(CONF_COVERS): [COVERS_SCHEMA],
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Konfiguracja platformy cover dla modbushas."""
    _LOGGER.info("=== COVER ASYNC_SETUP_PLATFORM CALLED ===")

    if not config and discovery_info:
        config = discovery_info

    scan_interval = config.get(CONF_SCAN_INTERVAL)
    hub_name = config.get(CONF_HUB, "fatek")

    if isinstance(scan_interval, (int, float)):
        scan_interval_td = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_td = datetime.timedelta(seconds=30)
    else:
        scan_interval_td = scan_interval

    command_register = config.get(CONF_COMMAND_REGISTER)

    covers_config = config.get(CONF_COVERS)
    if not covers_config:
        _LOGGER.error("No covers found in config: %s", config)
        return

    # Jeden bufor na grupę rolet (ten sam slave)
    buffer = ModbusCoverRegisterBuffer("covers", hass, hub_name, 1, scan_interval_td)

    entities = []
    for cover_cfg in covers_config:
        name = cover_cfg.get(CONF_NAME)
        register = cover_cfg.get(CONF_REGISTER)
        slave = cover_cfg.get(CONF_SLAVE, 1)
        unique_id = cover_cfg.get(CONF_UNIQUE_ID)

        entities.append(ModbusHASCover(
            hass=hass,
            hub_name=hub_name,
            name=name,
            register=register,
            slave=slave,
            unique_id=unique_id,
            command_register=command_register,
            buffer=buffer,
            scan_interval=scan_interval_td,
        ))

    _LOGGER.info("Added %d Modbus covers", len(entities))
    async_add_entities(entities)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Synchroniczna konfiguracja platformy cover (legacy wrapper)."""
    _LOGGER.info("=== COVER SETUP_PLATFORM CALLED (legacy) ===")

    if not config and discovery_info:
        config = discovery_info

    scan_interval = config.get(CONF_SCAN_INTERVAL)
    hub_name = config.get(CONF_HUB, "fatek")

    if isinstance(scan_interval, (int, float)):
        scan_interval_td = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_td = datetime.timedelta(seconds=30)
    else:
        scan_interval_td = scan_interval

    command_register = config.get(CONF_COMMAND_REGISTER)

    covers_config = config.get(CONF_COVERS)
    if not covers_config:
        _LOGGER.error("No covers found in config: %s", config)
        return

    buffer = ModbusCoverRegisterBuffer("covers", hass, hub_name, 1, scan_interval_td)

    entities = []
    for cover_cfg in covers_config:
        name = cover_cfg.get(CONF_NAME)
        register = cover_cfg.get(CONF_REGISTER)
        slave = cover_cfg.get(CONF_SLAVE, 1)
        unique_id = cover_cfg.get(CONF_UNIQUE_ID)

        entities.append(ModbusHASCover(
            hass=hass,
            hub_name=hub_name,
            name=name,
            register=register,
            slave=slave,
            unique_id=unique_id,
            command_register=command_register,
            buffer=buffer,
            scan_interval=scan_interval_td,
        ))

    _LOGGER.info("Added %d Modbus covers", len(entities))
    add_entities(entities)


class ModbusCoverRegisterBuffer:
    """Bufor odczytu rejestrów D dla rolet — analogiczny do ModbusRegisterBuffer z sensor.py."""

    def __init__(self, name, hass, hub_name, slave, scan_interval):
        self._hass = hass
        self._name = name
        self._hub_name = hub_name
        self._slave = slave
        self._scan_interval = scan_interval
        self._minreg = 99999
        self._maxreg = 0
        self._doread = True
        self._result = None
        self._lastread = datetime.datetime.now()
        self._hub = None
        self._update_lock = asyncio.Lock()
        self._register_cache = {}
        _LOGGER.debug("ModbusCoverRegisterBuffer initialized: name=%s, hub=%s, slave=%s", name, hub_name, slave)

    def checkhub(self):
        if self._hub is None:
            try:
                if MODBUS_DOMAIN in self._hass.data:
                    self._hub = self._hass.data[MODBUS_DOMAIN][self._hub_name]
                    _LOGGER.debug("Cover buffer hub found: %s", self._hub_name)
                else:
                    _LOGGER.warning("MODBUS_DOMAIN not found in hass.data")
            except (AttributeError, KeyError) as error:
                _LOGGER.error("Error accessing hub '%s': %s", self._hub_name, error)
                self._hub = None

    def set_register(self, register, count):
        if register < self._minreg:
            self._minreg = register
            self._doread = True
        if register + count - 1 > self._maxreg:
            self._maxreg = register + count - 1
            self._doread = True
        _LOGGER.debug("Cover buffer min/max %s / %s", self._minreg, self._maxreg)

    def refresh(self):
        self._doread = True
        self._register_cache.clear()

    async def async_read_register(self, register, count):
        """Odczyt rejestrów z bufora — odświeża cały zakres gdy potrzeba."""
        if self._doread or (self._scan_interval and (datetime.datetime.now() - self._lastread >= self._scan_interval)):
            if self._maxreg < self._minreg:
                _LOGGER.error("Invalid register range: min=%s, max=%s", self._minreg, self._maxreg)
                return None

            regnum = self._maxreg - self._minreg + 1
            self.checkhub()
            if self._hub is None:
                return None

            try:
                self._result = await self._hub.async_pb_call(
                    unit=self._slave,
                    address=self._minreg,
                    value=regnum,
                    use_call=CALL_TYPE_REGISTER_HOLDING
                )
            except Exception as e:
                _LOGGER.error("Error reading cover registers: %s", e)
                return None

            if not self._result:
                _LOGGER.error("Cover buffer read error from register %s for %s registers", self._minreg, regnum)
                return None

            self._register_cache.clear()
            for i, reg_addr in enumerate(range(self._minreg, self._maxreg + 1)):
                if i < len(self._result.registers):
                    self._register_cache[reg_addr] = self._result.registers[i]

            self._doread = False
            self._lastread = datetime.datetime.now()
            _LOGGER.debug("Cover buffer read %s registers from %s to %s", regnum, self._minreg, self._maxreg)

        # Zwróć żądane rejestry
        result = []
        for i in range(count):
            addr = register + i
            if addr in self._register_cache:
                result.append(self._register_cache[addr])
            else:
                _LOGGER.error("Cover register %s not in cache", addr)
                return None
        return result


class ModbusHASCover(CoverEntity):
    """Encja rolety sterowanej przez PLC Fatek via Modbus."""

    _attr_should_poll = False
    _attr_available = True
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, hass, hub_name, name, register, slave, unique_id,
                 command_register, buffer, scan_interval):
        self._hass = hass
        self._hub_name = hub_name
        self._name = name
        self._register = register  # numer rejestru D (konfiguracja PLC)
        self._modbus_register = register + FATEK_D_REGISTER_OFFSET  # adres Modbus do odczytu
        self._slave = slave
        self._command_register = command_register
        self._buffer = buffer
        self._scan_interval = scan_interval
        self._hub = None
        self._cancel_timer = None

        # Stan rolety
        self._position = None  # 0=zamknięta, 100=otwarta (konwencja HA)
        self._is_closed = None
        self._total_time = None  # D[N+3] — potrzebny do set_position

        if unique_id:
            self._attr_unique_id = unique_id
        else:
            self._attr_unique_id = f"modbushas_cover_{name}_{register}"

        # Rejestrujemy 6 rejestrów w buforze (adres Modbus = D + 6000)
        buffer.set_register(self._modbus_register, REG_COUNT)

        _LOGGER.debug("ModbusHASCover initialized: name=%s, D_register=%s, modbus_address=%s, unique_id=%s",
                       name, register, self._modbus_register, self._attr_unique_id)

    def checkhub(self):
        """Inicjalizacja połączenia z hubem modbus."""
        if self._hub is None:
            try:
                if MODBUS_DOMAIN in self._hass.data:
                    self._hub = self._hass.data[MODBUS_DOMAIN][self._hub_name]
                else:
                    _LOGGER.warning("MODBUS_DOMAIN not found in hass.data")
            except (AttributeError, KeyError) as error:
                _LOGGER.error("Error accessing hub '%s': %s", self._hub_name, error)
                self._hub = None

    async def async_added_to_hass(self):
        """Rejestracja w HA — inicjalny odczyt i cykliczny update."""
        await super().async_added_to_hass()
        await self.async_update()

        if self._scan_interval:
            scan_seconds = self._scan_interval.total_seconds()
            if scan_seconds > 0:
                self._cancel_timer = async_track_time_interval(
                    self.hass,
                    self._async_update_if_not_in_progress,
                    datetime.timedelta(seconds=scan_seconds)
                )
                _LOGGER.debug("Cover %s scheduled updates every %s seconds", self._name, scan_seconds)

    @callback
    def _async_update_if_not_in_progress(self, now=None):
        self.hass.async_create_task(self.async_update())

    async def async_will_remove_from_hass(self):
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        await super().async_will_remove_from_hass()

    @property
    def name(self):
        return self._name

    @property
    def is_closed(self):
        return self._is_closed

    @property
    def current_cover_position(self):
        return self._position

    # --- Komendy ---

    async def _async_write_command(self, command_code, target_time=None):
        """Wysyła komendę do PLC: zapisuje 3 kolejne rejestry R jednym wywołaniem Modbus (funkcja 16).

        R[X]   = bazowy adres D rolety
        R[X+1] = kod polecenia (0=stop, 1=up, 2=down, 3=set_position)
        R[X+2] = docelowy czas w sekundach (tylko dla set_position)
        """
        self.checkhub()
        if self._hub is None:
            _LOGGER.error("Cannot send command for cover %s: hub not available", self._name)
            return

        try:
            values = [self._register, command_code, target_time if target_time is not None else 0]
            write_client = self._hass.data.get(DATA_WRITE_CLIENT)
            if write_client:
                result = await write_client.async_write_registers(
                    self._command_register, values, slave=self._slave
                )
            else:
                # Fallback na główny hub jeśli write_client niedostępny
                self.checkhub()
                if self._hub is None:
                    return
                from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTERS
                result = await self._hub.async_pb_call(
                    unit=self._slave,
                    address=self._command_register,
                    value=values,
                    use_call=CALL_TYPE_WRITE_REGISTERS
                )
            if not result:
                _LOGGER.error("Failed to write command registers for cover %s", self._name)
                return

            _LOGGER.info("Cover %s command %s sent successfully (values=%s)", self._name, command_code, values)
        except Exception as e:
            _LOGGER.error("Error sending command %s for cover %s: %s", command_code, self._name, e)

    async def async_open_cover(self, **kwargs):
        _LOGGER.info("Opening cover: %s", self._name)
        await self._async_write_command(CMD_UP)

    async def async_close_cover(self, **kwargs):
        _LOGGER.info("Closing cover: %s", self._name)
        await self._async_write_command(CMD_DOWN)

    async def async_stop_cover(self, **kwargs):
        _LOGGER.info("Stopping cover: %s", self._name)
        await self._async_write_command(CMD_STOP)

    async def async_set_cover_position(self, **kwargs):
        """Ustawia pozycję rolety. HA: 0=zamknięta, 100=otwarta."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return

        if self._total_time is None or self._total_time == 0:
            _LOGGER.error("Cannot set position for cover %s: total_time unknown", self._name)
            return

        # Przeliczenie z % HA na sekundy PLC
        # HA: 0=zamknięta, 100=otwarta
        # PLC: 0=otwarta, total_time=zamknięta
        target_seconds = round((1 - position / 100) * self._total_time)
        _LOGGER.info("Setting cover %s position to %s%% (target_seconds=%s)", self._name, position, target_seconds)
        await self._async_write_command(CMD_SET_POSITION, target_time=target_seconds)

    # --- Odczyt stanu ---

    async def async_update(self):
        """Odczyt stanu rolety z PLC przez bufor rejestrów."""
        regs = await self._buffer.async_read_register(self._modbus_register, REG_COUNT)
        if regs is None:
            _LOGGER.error("Failed to read registers for cover %s", self._name)
            return

        total_time = regs[REG_TOTAL_TIME]
        status = regs[REG_STATUS]
        position_seconds = regs[REG_POSITION]

        self._total_time = total_time

        # Status ma priorytet nad pozycją
        if status == STATUS_OPEN:
            self._is_closed = False
            self._position = 100
        elif status == STATUS_CLOSED:
            self._is_closed = True
            self._position = 0
        elif status in (STATUS_PARTIAL_UP, STATUS_PARTIAL_DOWN):
            self._is_closed = False
            if total_time > 0:
                self._position = round((1 - position_seconds / total_time) * 100)
                # Ograniczenie do zakresu 0-100
                self._position = max(0, min(100, self._position))
            else:
                self._position = None
        else:
            _LOGGER.warning("Unknown cover status %s for %s", status, self._name)
            self._position = None
            self._is_closed = None

        self.async_write_ha_state()
        _LOGGER.debug("Cover %s updated: status=%s, position_sec=%s, total_time=%s, position_ha=%s",
                       self._name, status, position_seconds, total_time, self._position)
