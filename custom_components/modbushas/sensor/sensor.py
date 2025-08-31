"""
Support for Modbus Register sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modbus/
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
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
)

from homeassistant.const import (
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)

from homeassistant.components.sensor import (
    SensorEntity)
    
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Definiuję własne stałe, ponieważ nie są już dostępne w modbus.const
CONF_REGISTER = "register"
CONF_REGISTERS = "registers"
CONF_COUNT = "count"
CONF_OFFSET = "offset"
CONF_PRECISION = "precision"
CONF_SCALE = "scale"
CONF_SIGNED = "signed"

# Tworzę własny schemat zamiast importować z sensor
PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): "modbushas",
    vol.Optional("hub"): cv.string,
    vol.Optional("scan_interval"): vol.Any(cv.positive_int, cv.positive_float),
    vol.Required(CONF_REGISTERS): [{
        vol.Required(CONF_REGISTER): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_COUNT, default=1): cv.positive_int,
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_SIGNED, default=0): cv.positive_int
    }]
})


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Modbus sensors."""
    _LOGGER.info("=== ASYNC_SETUP_PLATFORM CALLED ===")
    _LOGGER.info("Setting up Modbus Sensor platform - config: %s", config)
    _LOGGER.info("Setting up Modbus Sensor platform - discovery_info: %s", discovery_info)
    _LOGGER.info("Config keys: %s", list(config.keys()) if config else "None")
    _LOGGER.info("Config platform: %s", config.get("platform") if config else "None")
    
    # Użyj discovery_info jeśli config jest pusty
    if not config and discovery_info:
        config = discovery_info
        _LOGGER.info("Using discovery_info as config")
    
    sensors = []
    scan_interval = config.get("scan_interval")
    hub_name = config.get("hub", "fatek")
    
    # Konwertuj scan_interval na timedelta dla EntityPlatform
    if isinstance(scan_interval, (int, float)):
        scan_interval_timedelta = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_timedelta = datetime.timedelta(seconds=30)  # domyślna wartość
    else:
        scan_interval_timedelta = scan_interval
    
    _LOGGER.debug("Sensor scan interval: %s (type: %s), hub: %s", scan_interval, type(scan_interval), hub_name)
    
    buffer = ModbusRegisterBuffer("test", hass, hub_name, 1, scan_interval_timedelta)
    
    # Sprawdź czy registers istnieje w config
    registers = config.get("registers")
    if not registers:
        _LOGGER.error("No registers found in config: %s", config)
        return
    
    for register in registers:
        _LOGGER.debug("Adding sensor: %s, register: %s", register.get(CONF_NAME), register.get(CONF_REGISTER))
        _LOGGER.debug("Register config: %s", register)
        
        # Pobieramy wszystkie parametry z domyślnymi wartościami
        name = register.get(CONF_NAME)
        slave = register.get(CONF_SLAVE, 1)
        reg = register.get(CONF_REGISTER)
        unit = register.get(CONF_UNIT_OF_MEASUREMENT)
        count = register.get(CONF_COUNT, 1)
        scale = register.get(CONF_SCALE, 1.0)
        offset = register.get(CONF_OFFSET, 0.0)
        precision = register.get(CONF_PRECISION, 0)
        signed = register.get(CONF_SIGNED, 0)
        unique_id = register.get(CONF_UNIQUE_ID)
        
        _LOGGER.debug("Sensor params: name=%s, slave=%s, register=%s, count=%s, scale=%s, offset=%s, precision=%s, signed=%s", 
                     name, slave, reg, count, scale, offset, precision, signed)
        
        sensors.append(ModbusHASRegisterSensor(
            name, slave, reg, unit, count, scale, offset, precision, signed, unique_id, buffer))
    
    _LOGGER.info("Added %d Modbus sensors", len(sensors))
    async_add_devices(sensors)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus sensors - legacy wrapper for async_setup_platform."""
    _LOGGER.info("=== SETUP_PLATFORM CALLED (legacy wrapper) ===")
    
    # Użyj discovery_info jeśli config jest pusty
    if not config and discovery_info:
        config = discovery_info
        _LOGGER.info("Using discovery_info as config in legacy wrapper")
    
    sensors = []
    scan_interval = config.get("scan_interval")
    hub_name = config.get("hub", "fatek")
    
    # Konwertuj scan_interval na timedelta dla EntityPlatform
    if isinstance(scan_interval, (int, float)):
        scan_interval_timedelta = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_timedelta = datetime.timedelta(seconds=30)  # domyślna wartość
    else:
        scan_interval_timedelta = scan_interval
    
    _LOGGER.debug("Sensor scan interval: %s (type: %s), hub: %s", scan_interval, type(scan_interval), hub_name)
    
    buffer = ModbusRegisterBuffer("test", hass, hub_name, 1, scan_interval_timedelta)
    
    # Sprawdź czy registers istnieje w config
    registers = config.get("registers")
    if not registers:
        _LOGGER.error("No registers found in config: %s", config)
        return
    
    for register in registers:
        _LOGGER.debug("Adding sensor: %s, register: %s", register.get(CONF_NAME), register.get(CONF_REGISTER))
        _LOGGER.debug("Register config: %s", register)
        
        # Pobieramy wszystkie parametry z domyślnymi wartościami
        name = register.get(CONF_NAME)
        slave = register.get(CONF_SLAVE, 1)
        reg = register.get(CONF_REGISTER)
        unit = register.get(CONF_UNIT_OF_MEASUREMENT)
        count = register.get(CONF_COUNT, 1)
        scale = register.get(CONF_SCALE, 1.0)
        offset = register.get(CONF_OFFSET, 0.0)
        precision = register.get(CONF_PRECISION, 0)
        signed = register.get(CONF_SIGNED, 0)
        unique_id = register.get(CONF_UNIQUE_ID)
        
        _LOGGER.debug("Sensor params: name=%s, slave=%s, register=%s, count=%s, scale=%s, offset=%s, precision=%s, signed=%s", 
                     name, slave, reg, count, scale, offset, precision, signed)
        
        sensors.append(ModbusHASRegisterSensor(
            name, slave, reg, unit, count, scale, offset, precision, signed, unique_id, buffer))
    
    _LOGGER.info("Added %d Modbus sensors", len(sensors))
    add_devices(sensors)


class ModbusRegisterBuffer():
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
        # Dodajemy cache dla pojedynczych rejestrów
        self._register_cache = {}
        _LOGGER.debug("ModbusRegisterBuffer initialized: name=%s, hub_name=%s, slave=%s, scan_interval=%s", 
                     name, hub_name, slave, scan_interval)
    
    def checkhub(self):
        if(self._hub is None):
            try:
                if(MODBUS_DOMAIN in self._hass.data):
                    self._hub = self._hass.data[MODBUS_DOMAIN][self._hub_name]
                    _LOGGER.debug("Hub found: %s (name: %s)", self._hub, self._hub_name)
                    _LOGGER.debug("Hub methods: %s", [method for method in dir(self._hub) if not method.startswith('_')])
                else:
                    _LOGGER.warning("MODBUS_DOMAIN not found in hass.data")
            except AttributeError as error:
                _LOGGER.error("Error accessing hub: %s", error)
                self._hub = None
            except KeyError as error:
                _LOGGER.error("Hub '%s' not found in MODBUS_DOMAIN", self._hub_name)
                self._hub = None
        
    def set_register(self, register, count):
        if(register < self._minreg):
            self._minreg = register
            self._doread = True
            _LOGGER.debug("Updated minreg to: %s", register)
        if(register+count-1 > self._maxreg):
            self._maxreg = register+count-1
            self._doread = True
            _LOGGER.debug("Updated maxreg to: %s", register+count-1)
        _LOGGER.debug("Sensor buffer min/max %s / %s", self._minreg, self._maxreg)

    def refresh(self):
        self._doread = True
        # Czyścimy cache przy refresh
        self._register_cache.clear()
        _LOGGER.debug("Buffer refresh requested")
    
    def clear_register_cache(self, register=None):
        """Czyści cache dla konkretnego rejestru lub całego cache'a."""
        if register is None:
            self._register_cache.clear()
            _LOGGER.debug("Cleared entire register cache")
        else:
            if register in self._register_cache:
                del self._register_cache[register]
                _LOGGER.debug("Cleared cache for register: %s", register)
    
    async def force_read_register(self, register, count):
        """Wymusza odczyt rejestru z pominięciem cache'a."""
        _LOGGER.debug("Force reading register: %s", register)
        # Czyścimy cache dla tego rejestru
        if register in self._register_cache:
            del self._register_cache[register]
        # Odczytujemy pojedynczy rejestr
        return await self.async_read_single_register(register, count)
    
    def is_register_cached(self, register):
        """Sprawdza czy rejestr jest w cache'u."""
        return register in self._register_cache
    
    def get_cached_register_value(self, register):
        """Zwraca wartość rejestru z cache'a (None jeśli nie ma w cache)."""
        return self._register_cache.get(register)
    
    def debug_cache(self):
        """Debuguje zawartość cache'a."""
        _LOGGER.debug("Cache contents: %s", self._register_cache)
        _LOGGER.debug("Cache size: %d", len(self._register_cache))
        _LOGGER.debug("Min register: %s, Max register: %s", self._minreg, self._maxreg)
    
    def should_refresh_cache(self):
        """Sprawdza czy cache wymaga odświeżenia na podstawie scan_interval."""
        if not self._scan_interval:
            return False
        time_since_last_read = datetime.datetime.now() - self._lastread
        return time_since_last_read >= self._scan_interval
    
    async def async_read_single_register(self, register, count):
        """Odczyt pojedynczego rejestru - szybszy niż odczyt całego zakresu."""
        _LOGGER.debug("Reading single register: %s, count: %s", register, count)
        self.checkhub()
        if(self._hub is None):
            _LOGGER.error("Cannot read register %s: hub not available", register)
            return None
        
        try:
            # Używamy async_pb_call dla pojedynczego rejestru
            result = await self._hub.async_pb_call(
                unit=self._slave,
                address=register,
                value=count,
                use_call=CALL_TYPE_REGISTER_HOLDING
            )
            if result and hasattr(result, 'registers') and len(result.registers) > 0:
                register_values = list(result.registers)
                # Aktualizujemy cache
                self._register_cache[register] = register_values
                _LOGGER.debug("Single register %s read successfully: %s", register, register_values)
                return register_values
            else:
                _LOGGER.error("Failed to read single register %s", register)
                return None
        except Exception as e:
            _LOGGER.error("Error reading single register %s: %s", register, e)
            return None

    async def async_read_register(self, register, count):
        """Async version of read_register for use in async context."""
        # Sprawdz czy minął scan_interval (scan_interval to już timedelta)
        if self._scan_interval and (datetime.datetime.now() - self._lastread >= self._scan_interval):
            self._doread = True
            _LOGGER.debug("Scan interval exceeded, forcing read")
            
        # Sprawdzamy cache dla pojedynczego rejestru
        if register in self._register_cache:
            _LOGGER.debug("Using cached value for register %s: %s", register, self._register_cache[register])
            return self._register_cache[register]
            
        if(self._doread == True and self._maxreg >= self._minreg):
            regnum = self._maxreg - self._minreg + 1   
            self.checkhub()
            if(self._hub is None):
                _LOGGER.error("Cannot read register %s: hub not available", register)
                return None
                
            _LOGGER.debug("Reading %d registers from %s to %s", regnum, self._minreg, self._maxreg)
            
            try:
                # Używamy async_pb_call bezpośrednio z hub
                self._result = await self._hub.async_pb_call(
                    unit=self._slave,
                    address=self._minreg,
                    value=regnum,
                    use_call=CALL_TYPE_REGISTER_HOLDING
                )
            except Exception as e:
                _LOGGER.error("Error reading registers: %s", e)
                return None
                
            if not self._result:
                _LOGGER.error("ModbusRegisterBuffer read error from register %s for %s registers", self._minreg, regnum)
                return None
                
            self._doread = False
            self._lastread = datetime.datetime.now()
            _LOGGER.debug("Successfully read %s registers from %s", regnum, self._minreg)
            
            # Aktualizujemy cache dla wszystkich odczytanych rejestrów
            for i, reg_addr in enumerate(range(self._minreg, self._maxreg + 1)):
                if i < len(self._result.registers):
                    self._register_cache[reg_addr] = [self._result.registers[i]]
            
        if self._result is None:
            _LOGGER.error("No result available for register %s", register)
            return None
            
        regnum = register - self._minreg
        if regnum < 0 or regnum >= len(self._result.registers):
            _LOGGER.error("Register %s out of range (reg %s, max %s)", register, regnum, len(self._result.registers))
            return None
            
        # Zwracamy listę wartości dla żądanego rejestru i count
        result_values = []
        for i in range(count):
            if regnum + i < len(self._result.registers):
                result_values.append(self._result.registers[regnum + i])
            else:
                _LOGGER.error("Register %s+%s out of range", register, i)
                break
        
        _LOGGER.debug("Register %s (reg %s) values: %s", register, regnum, result_values)
        return result_values

    def get_performance_stats(self):
        """Zwraca statystyki wydajności cache'a."""
        total_registers = self._maxreg - self._minreg + 1 if self._maxreg >= self._minreg else 0
        cached_registers = len(self._register_cache)
        cache_hit_rate = (cached_registers / total_registers * 100) if total_registers > 0 else 0
        
        return {
            'total_registers': total_registers,
            'cached_registers': cached_registers,
            'cache_hit_rate': round(cache_hit_rate, 2),
            'last_read': self._lastread.isoformat() if self._lastread else None,
            'scan_interval': str(self._scan_interval) if self._scan_interval else None
        }


class ModbusHASRegisterSensor(SensorEntity):
    """Modbus Register Sensor."""

    _attr_should_poll = False
    _attr_available = True

    def __init__(self, name, slave, register, unit_of_measurement, count, scale, offset, precision, signed, unique_id, buffer):
        """Initialize the modbus register sensor."""
        self._name = name
        self._slave = int(slave) if slave else 1
        self._register = int(register)
        self._unit_of_measurement = unit_of_measurement
        self._count = int(count) if count else 1
        self._scale = scale if scale is not None else 1.0
        self._offset = offset if offset is not None else 0.0
        self._precision = precision if precision is not None else 0
        self._signed = signed if signed is not None else 0
        self._buffer = buffer
        self._value = None
        self._cancel_timer = None
        
        # Generujemy unikalny ID dla encji - używamy podany lub generujemy domyślny
        if unique_id:
            self._attr_unique_id = unique_id
        else:
            self._attr_unique_id = f"modbushas_sensor_{name}_{register}"
        
        buffer.set_register(register, count)
        _LOGGER.debug("ModbusHASRegisterSensor initialized: name=%s, register=%s, unique_id=%s", name, register, self._attr_unique_id)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        
        # Schedule initial update - odczytujemy dane z PLC
        await self.async_update()
        
        # Schedule regular updates based on scan_interval
        if hasattr(self._buffer, '_scan_interval') and self._buffer._scan_interval:
            scan_seconds = self._buffer._scan_interval.total_seconds()
            if scan_seconds > 0:
                self._cancel_timer = async_track_time_interval(
                    self.hass,
                    self._async_update_if_not_in_progress,
                    datetime.timedelta(seconds=scan_seconds)
                )
                _LOGGER.debug("Sensor %s scheduled updates every %s seconds", self._name, scan_seconds)
        
        _LOGGER.debug("Sensor %s added to hass", self._name)

    @callback
    def _async_update_if_not_in_progress(self, now=None):
        """Update the entity state if not already in progress."""
        _LOGGER.debug("Scheduled update for sensor: %s", self._name)
        # Wywołujemy async_update aby odczytać dane z PLC
        self.hass.async_create_task(self.async_update())

    async def async_will_remove_from_hass(self):
        """Handle entity which will be removed."""
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        await super().async_will_remove_from_hass()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement
    
    async def force_refresh_state(self):
        """Wymusza odświeżenie stanu sensora z pominięciem cache'a."""
        _LOGGER.debug("Force refreshing sensor state: %s", self._name)
        raw_value = await self._buffer.force_read_register(self._register, self._count)
        
        # Przetwarzamy surowe wartości rejestrów
        if raw_value:
            try:
                val = 0
                for i, res in enumerate(raw_value):
                    r = int(res)
                    if i == 0 and self._signed == 1 and r > 32768:
                        r = 0 - (r - 65536)
                        r = 0 - r
                    val += r * (2**(i*16))
                
                # Aplikujemy skalę i offset
                processed_value = self._scale * val + self._offset
                
                # Formatujemy z precyzją
                self._value = format(processed_value, ".{}f".format(self._precision))
                
                _LOGGER.debug("Sensor %s force refreshed: raw=%s, processed=%s", self._name, raw_value, self._value)
            except Exception as e:
                _LOGGER.error("Error processing sensor %s force refresh value: %s", self._name, e)
                self._value = None
        else:
            _LOGGER.error("No raw value available for sensor %s force refresh", self._name)
            self._value = None
        
        self.async_write_ha_state()
        _LOGGER.debug("Sensor %s force refreshed state: %s", self._name, self._value)
    
    def get_cache_info(self):
        """Zwraca informacje o cache'u dla tego sensora."""
        return {
            'name': self._name,
            'register': self._register,
            'current_value': self._value,
            'cached': self._buffer.is_register_cached(self._register),
            'cached_value': self._buffer.get_cached_register_value(self._register),
            'buffer_stats': self._buffer.get_performance_stats()
        }

    async def async_update(self):
        """Async update the state of the sensor."""
        _LOGGER.debug("Async updating sensor state: %s", self._name)
        
        # Sprawdzamy cache najpierw
        if hasattr(self._buffer, '_register_cache') and self._register in self._buffer._register_cache:
            cached_value = self._buffer._register_cache[self._register]
            _LOGGER.debug("Sensor %s using cached value: %s", self._name, cached_value)
            raw_value = cached_value
        else:
            # Jeśli nie ma w cache, odczytujemy pojedynczy rejestr
            raw_value = await self._buffer.async_read_single_register(self._register, self._count)
            _LOGGER.debug("Sensor %s read single register value: %s", self._name, raw_value)
        
        # Przetwarzamy surowe wartości rejestrów
        if raw_value:
            try:
                val = 0
                for i, res in enumerate(raw_value):
                    r = int(res)
                    if i == 0 and self._signed == 1 and r > 32768:
                        r = 0 - (r - 65536)
                        r = 0 - r
                    val += r * (2**(i*16))
                
                # Aplikujemy skalę i offset
                processed_value = self._scale * val + self._offset
                
                # Formatujemy z precyzją
                self._value = format(processed_value, ".{}f".format(self._precision))
                
                _LOGGER.debug("Sensor %s processed value: raw=%s, processed=%s", self._name, raw_value, self._value)
            except Exception as e:
                _LOGGER.error("Error processing sensor %s value: %s", self._name, e)
                self._value = None
        else:
            _LOGGER.error("No raw value available for sensor %s", self._name)
            self._value = None
        
        _LOGGER.debug("Sensor %s async updated value: %s", self._name, self._value)
        
        # Aktualizujemy stan encji w HA
        self.async_write_ha_state()
        
        # Debug cache performance
        if hasattr(self._buffer, 'get_performance_stats'):
            stats = self._buffer.get_performance_stats()
            _LOGGER.debug("Buffer performance: %s", stats)
    
    def debug_sensor_state(self):
        """Debuguje stan sensora i cache'a."""
        _LOGGER.debug("=== Sensor Debug Info ===")
        _LOGGER.debug("Name: %s", self._name)
        _LOGGER.debug("Register: %s", self._register)
        _LOGGER.debug("Current value: %s", self._value)
        _LOGGER.debug("Buffer cache stats: %s", self._buffer.get_performance_stats())
        _LOGGER.debug("Register in cache: %s", self._buffer.is_register_cached(self._register))
        if self._buffer.is_register_cached(self._register):
            _LOGGER.debug("Cached register value: %s", self._buffer.get_cached_register_value(self._register))
        _LOGGER.debug("=======================")
