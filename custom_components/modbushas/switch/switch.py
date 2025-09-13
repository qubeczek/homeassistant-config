"""
Support for Modbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.modbus/
"""
import logging
import voluptuous as vol
import datetime
import asyncio

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import callback

from homeassistant.components.modbus.const import (
    MODBUS_DOMAIN,
    CALL_TYPE_COIL,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
)

from homeassistant.const import (
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_NAME,
)

from homeassistant.components.switch import (
    SwitchEntity)

from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Definiuję własne stałe, ponieważ nie są już dostępne w modbus.const
CONF_COIL = "coil"
CONF_COILS = "coils"
CONF_REGISTER = "register"
CONF_REGISTERS = "registers"
CONF_COMMAND_ON = "command_on"
CONF_COMMAND_OFF = "command_off"
CONF_VERIFY_STATE = "verify_state"
CONF_VERIFY_REGISTER = "verify_register"
CONF_REGISTER_TYPE = "register_type"
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"
CONF_HUB = "hub"
# Schematy dla coils i registers
COILS_SCHEMA = vol.Schema({
    vol.Required(CONF_COIL): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_SLAVE): cv.positive_int,
    vol.Optional(CONF_UNIQUE_ID): cv.string
})

REGISTERS_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_SLAVE): cv.positive_int,
    vol.Required(CONF_REGISTER): cv.positive_int,
    vol.Required(CONF_COMMAND_ON): cv.positive_int,
    vol.Required(CONF_COMMAND_OFF): cv.positive_int,
    vol.Optional(CONF_VERIFY_STATE, default=True): cv.boolean,
    vol.Optional(CONF_VERIFY_REGISTER): cv.positive_int,
    vol.Optional(CONF_REGISTER_TYPE, default="holding"): vol.In(["holding", "input"]),
    vol.Optional(CONF_STATE_ON): cv.positive_int,
    vol.Optional(CONF_STATE_OFF): cv.positive_int,
    vol.Optional(CONF_UNIQUE_ID): cv.string
})

# Główny schemat platformy
PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_COILS, CONF_REGISTERS),
    vol.Schema({
        vol.Required("platform"): "modbushas",
        vol.Optional("hub"): cv.string,
        vol.Optional("scan_interval"): vol.Any(cv.positive_int, cv.positive_float),
        vol.Optional(CONF_COILS): [COILS_SCHEMA],
        vol.Optional(CONF_REGISTERS): [REGISTERS_SCHEMA]
    })
)


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Modbus switches."""
    _LOGGER.debug("=== ASYNC_SETUP_PLATFORM CALLED ===")
    _LOGGER.debug("Setting up Modbus Switch platform - config: %s", config)
    _LOGGER.debug("Setting up Modbus Switch platform - discovery_info: %s", discovery_info)
    _LOGGER.debug("Config keys: %s", list(config.keys()) if config else "None")
    _LOGGER.debug("Config platform: %s", config.get("platform") if config else "None")
    
    # Użyj discovery_info jeśli config jest pusty
    if not config and discovery_info:
        config = discovery_info
        _LOGGER.debug("Using discovery_info as config")
    
    switches = []
    scan_interval = config.get("scan_interval")
    hub_name = config.get("hub", "fatek")
    
    # Konwertuj scan_interval na timedelta dla EntityPlatform
    if isinstance(scan_interval, (int, float)):
        scan_interval_timedelta = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_timedelta = datetime.timedelta(seconds=30)  # domyślna wartość
    else:
        scan_interval_timedelta = scan_interval
    
    _LOGGER.debug("Switch scan interval: %s (type: %s), hub: %s", scan_interval, type(scan_interval), hub_name)
    
    # Obsługa coils
    if CONF_COILS in config:
        coils = config.get(CONF_COILS)
        _LOGGER.debug("Found %d coil switches in config", len(coils))
        buffer = ModbusCoilBuffer("test", hass, hub_name, 1, scan_interval_timedelta)
        for coil in coils:
            _LOGGER.debug("Adding coil switch: %s, coil: %s, slave: %s", 
                        coil.get(CONF_NAME), coil.get(CONF_COIL), coil.get(CONF_SLAVE, 1))
            switches.append(ModbusHASCoilSwitch(
                coil.get(CONF_NAME),
                coil.get(CONF_COIL),
                buffer,
                coil.get(CONF_UNIQUE_ID)))
    
    # Obsługa registers
    if CONF_REGISTERS in config:
        registers = config.get(CONF_REGISTERS)
        _LOGGER.debug("Found %d register switches in config", len(registers))
        for register in registers:
            _LOGGER.debug("Adding register switch: %s, register: %s, slave: %s, commands: %s/%s", 
                        register.get(CONF_NAME), register.get(CONF_REGISTER), 
                        register.get(CONF_SLAVE, 1), register.get(CONF_COMMAND_ON), 
                        register.get(CONF_COMMAND_OFF))
            switches.append(ModbusHASRegisterSwitch(
                hass,
                register.get(CONF_NAME),
                register.get(CONF_SLAVE),
                register.get(CONF_REGISTER),
                register.get(CONF_COMMAND_ON),
                register.get(CONF_COMMAND_OFF),
                register.get(CONF_VERIFY_STATE),
                register.get(CONF_VERIFY_REGISTER),
                register.get(CONF_REGISTER_TYPE),
                register.get(CONF_STATE_ON),
                register.get(CONF_STATE_OFF),
                register.get(CONF_UNIQUE_ID),
                hub_name))
    
    if not switches:
        _LOGGER.error("No switches found in config: %s", config)
        return
    
    _LOGGER.debug("Added %d Modbus switches", len(switches))
    async_add_devices(switches)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus switches - legacy wrapper for async_setup_platform."""
    _LOGGER.debug("=== SETUP_PLATFORM CALLED (legacy wrapper) ===")
    
    # Użyj discovery_info jeśli config jest pusty
    if not config and discovery_info:
        config = discovery_info
        _LOGGER.debug("Using discovery_info as config in legacy wrapper")
    
    switches = []
    scan_interval = config.get("scan_interval")
    hub_name = config.get("hub", "fatek")
    
    # Konwertuj scan_interval na timedelta dla EntityPlatform
    if isinstance(scan_interval, (int, float)):
        scan_interval_timedelta = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_timedelta = datetime.timedelta(seconds=30)  # domyślna wartość
    else:
        scan_interval_timedelta = scan_interval
    
    _LOGGER.debug("Switch scan interval: %s (type: %s), hub: %s", scan_interval, type(scan_interval), hub_name)
    
    # Obsługa coils
    if CONF_COILS in config:
        coils = config.get(CONF_COILS)
        _LOGGER.debug("Found %d coil switches in config", len(coils))
        buffer = ModbusCoilBuffer("test", hass, hub_name, 1, scan_interval_timedelta)
        for coil in coils:
            _LOGGER.debug("Adding coil switch: %s, coil: %s, slave: %s", 
                        coil.get(CONF_NAME), coil.get(CONF_COIL), coil.get(CONF_SLAVE, 1))
            switches.append(ModbusHASCoilSwitch(
                coil.get(CONF_NAME),
                coil.get(CONF_COIL),
                buffer,
                coil.get(CONF_UNIQUE_ID)))
    
    # Obsługa registers
    if CONF_REGISTERS in config:
        registers = config.get(CONF_REGISTERS)
        _LOGGER.debug("Found %d register switches in config", len(registers))
        for register in registers:
            _LOGGER.debug("Adding register switch: %s, register: %s, slave: %s, commands: %s/%s", 
                        register.get(CONF_NAME), register.get(CONF_REGISTER), 
                        register.get(CONF_SLAVE, 1), register.get(CONF_COMMAND_ON), 
                        register.get(CONF_COMMAND_OFF))
            switches.append(ModbusHASRegisterSwitch(
                hass,
                register.get(CONF_NAME),
                register.get(CONF_SLAVE),
                register.get(CONF_REGISTER),
                register.get(CONF_COMMAND_ON),
                register.get(CONF_COMMAND_OFF),
                register.get(CONF_VERIFY_STATE),
                register.get(CONF_VERIFY_REGISTER),
                register.get(CONF_REGISTER_TYPE),
                register.get(CONF_STATE_ON),
                register.get(CONF_STATE_OFF),
                register.get(CONF_UNIQUE_ID),
                hub_name))
    
    if not switches:
        _LOGGER.error("No switches found in config: %s", config)
        return
    
    _LOGGER.debug("Added %d Modbus switches", len(switches))
    add_devices(switches)


class ModbusCoilBuffer():
    def __init__(self, name, hass, hub_name, slave, scan_interval):
        self._hass = hass
        self._name = name
        self._hub_name = hub_name
        self._slave = slave
        self._scan_interval = scan_interval
        self._mincoil = 9999
        self._maxcoil = 0
        self._doread = True
        self._result = None
        self._lastread = datetime.datetime.now()
        self._hub = None
        self._update_lock = asyncio.Lock()
        # Dodajemy cache dla pojedynczych coilów
        self._coil_cache = {}
        _LOGGER.debug("ModbusCoilBuffer initialized: name=%s, hub_name=%s, slave=%s, scan_interval=%s", 
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
        
    def set_coil(self, coil):
        if(coil < self._mincoil):
            self._mincoil = coil
            self._doread = True
            _LOGGER.debug("Updated mincoil to: %s", coil)
        if(coil > self._maxcoil):
            self._maxcoil = coil
            self._doread = True
            _LOGGER.debug("Updated maxcoil to: %s", coil)

    def refresh(self):
        self._doread = True
        # Czyścimy cache przy refresh
        self._coil_cache.clear()
        _LOGGER.debug("Buffer refresh requested")
    
    def clear_coil_cache(self, coil=None):
        """Czyści cache dla konkretnego coila lub całego cache'a."""
        if coil is None:
            self._coil_cache.clear()
            _LOGGER.debug("Cleared entire coil cache")
        else:
            if coil in self._coil_cache:
                del self._coil_cache[coil]
                _LOGGER.debug("Cleared cache for coil: %s", coil)
    
    async def force_read_coil(self, coil):
        """Wymusza odczyt coila z pominięciem cache'a."""
        _LOGGER.debug("Force reading coil: %s", coil)
        # Czyścimy cały cache i wymuszamy odczyt
        self._doread = True 
        # Odczytujemy stan coila (z odświeżeniem bufora jeśli potrzeba)
        return await self.async_read_coil(coil)
    
    def is_coil_cached(self, coil):
        """Sprawdza czy coil jest w cache'u."""
        return coil in self._coil_cache
    
    def get_cached_coil_state(self, coil):
        """Zwraca stan coila z cache'a (None jeśli nie ma w cache)."""
        return self._coil_cache.get(coil)
    
    def debug_cache(self):
        """Debuguje zawartość cache'a."""
        _LOGGER.debug("Cache contents: %s", self._coil_cache)
        _LOGGER.debug("Cache size: %d", len(self._coil_cache))
        _LOGGER.debug("Min coil: %s, Max coil: %s", self._mincoil, self._maxcoil)
    
    def should_refresh_cache(self):
        """Sprawdza czy cache wymaga odświeżenia na podstawie scan_interval."""
        if not self._scan_interval:
            return False
        time_since_last_read = datetime.datetime.now() - self._lastread
        return time_since_last_read >= self._scan_interval
    
    
    def get_performance_stats(self):
        """Zwraca statystyki wydajności cache'a."""
        total_coils = self._maxcoil - self._mincoil + 1 if self._maxcoil >= self._mincoil else 0
        cached_coils = len(self._coil_cache)
        cache_hit_rate = (cached_coils / total_coils * 100) if total_coils > 0 else 0
        
        return {
            'total_coils': total_coils,
            'cached_coils': cached_coils,
            'cache_hit_rate': round(cache_hit_rate, 2),
            'last_read': self._lastread.isoformat() if self._lastread else None,
            'scan_interval': str(self._scan_interval) if self._scan_interval else None
        }

    async def async_read_coil(self, coil):
        """Odczyt stanu pojedynczego coila - bufor sam zarządza odświeżaniem."""
        _LOGGER.debug("Reading coil: %s", coil)
        
        # Sprawdzamy czy bufor wymaga odświeżenia
        if self._doread or (self._scan_interval and (datetime.datetime.now() - self._lastread >= self._scan_interval)):
            _LOGGER.debug("Buffer needs refresh, reading all coils from %s to %s", self._mincoil, self._maxcoil)
            
            if self._maxcoil < self._mincoil:
                _LOGGER.error("Invalid coil range: min=%s, max=%s", self._mincoil, self._maxcoil)
                return False
                
            coilnum = self._maxcoil - self._mincoil + 1
            self.checkhub()
            if self._hub is None:
                _LOGGER.error("Cannot read coils: hub not available")
                return False
                
            try:
                # Odczytujemy cały zakres coilów
                self._result = await self._hub.async_pb_call(
                    unit=self._slave,
                    address=self._mincoil,
                    value=coilnum,
                    use_call=CALL_TYPE_COIL
                )
            except Exception as e:
                _LOGGER.error("Error reading coils: %s", e)
                return False
                
            if not self._result:
                _LOGGER.error("ModbusCoilBuffer read error from coil %s for %s coils", self._mincoil, coilnum)
                return False
                
            # Aktualizujemy cache dla wszystkich odczytanych coilów
            self._coil_cache.clear()
            for i, coil_addr in enumerate(range(self._mincoil, self._maxcoil + 1)):
                if i < len(self._result.bits):
                    self._coil_cache[coil_addr] = bool(self._result.bits[i])
                    
            self._doread = False
            self._lastread = datetime.datetime.now()
            _LOGGER.debug("Successfully read %s coils from %s to %s", coilnum, self._mincoil, self._maxcoil)
        
        # Zwracamy stan z cache'a
        if coil in self._coil_cache:
            result = self._coil_cache[coil]
            _LOGGER.debug("Coil %s state from cache: %s", coil, result)
            return result
        else:
            _LOGGER.error("Coil %s not found in cache after refresh", coil)
            return False

    async def async_write_coil(self, coil, value, verify_after_write=True):
        """Async version of write_coil with optional verification."""
        _LOGGER.debug("Async writing coil %s to value: %s (verify: %s)", coil, value, verify_after_write)
        self.checkhub()
        if(self._hub is None):
            _LOGGER.error("Cannot write coil %s: hub not available", coil)
            return False
        
        try:
            # Używamy async_pb_call bezpośrednio z hub
            result = await self._hub.async_pb_call(
                unit=self._slave,
                address=coil,
                value=value,
                use_call=CALL_TYPE_WRITE_COIL
            )
            if result:
                _LOGGER.debug("Successfully wrote coil %s to value: %s", coil, value)
                
                # Aktualizujemy cache
                self._coil_cache[coil] = value
                
                # Jeśli włączona jest weryfikacja, odczytujemy stan coila
                if verify_after_write:
                    _LOGGER.debug("Verifying coil %s after write", coil)
                    # Krótkie opóźnienie przed weryfikacją
                    await asyncio.sleep(0.3)
                    # Wymuszamy odczyt z PLC (pomijając cache)
                    self._doread = True
                    verified_state = await self.async_read_coil(coil)
                    if verified_state == value:
                        _LOGGER.debug("Coil %s verification successful: %s", coil, verified_state)
                    else:
                        _LOGGER.warning("Coil %s verification failed: expected %s, got %s", coil, value, verified_state)
                
                return True
            else:
                _LOGGER.error("Failed to write coil %s", coil)
                return False
        except Exception as e:
            _LOGGER.error("Error writing coil %s: %s", coil, e)
            return False
        
             
        


class ModbusHASCoilSwitch(SwitchEntity):
    """Modbus Coil Switch."""

    _attr_should_poll = False
    _attr_available = True

    def __init__(self, name, coil, buffer, unique_id=None):
        """Initialize the modbus coil switch."""
        self._name = name
        self._coil = int(coil)
        self._state = None
        self._buffer = buffer
        self._cancel_timer = None
        
        # Generujemy unikalny ID dla encji - używamy podany lub generujemy domyślny
        if unique_id:
            self._attr_unique_id = unique_id
        else:
            self._attr_unique_id = f"modbushas_switch_{name}_{coil}"
        
        buffer.set_coil(coil)
        _LOGGER.debug("ModbusHASCoilSwitch initialized: name=%s, coil=%s, unique_id=%s", name, coil, self._attr_unique_id)

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
                _LOGGER.debug("Switch %s scheduled updates every %s seconds", self._name, scan_seconds)
        
        _LOGGER.debug("Switch %s added to hass", self._name)

    @callback
    def _async_update_if_not_in_progress(self, now=None):
        """Update the entity state if not already in progress."""
        _LOGGER.debug("Scheduled update for switch: %s", self._name)
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
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.info("Async turning on switch: %s", self._name)
        if await self._buffer.async_write_coil(self._coil, True, verify_after_write=True):
            self._state = True
            # Nie potrzebujemy refresh - cache jest już zaktualizowany
            self.async_write_ha_state()
            _LOGGER.debug("Switch %s turned ON successfully", self._name)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        _LOGGER.info("Async turning off switch: %s", self._name)
        if await self._buffer.async_write_coil(self._coil, False, verify_after_write=True):
            self._state = False
            # Nie potrzebujemy refresh - cache jest już zaktualizowany
            self.async_write_ha_state()
            _LOGGER.debug("Switch %s turned OFF successfully", self._name)
    
    async def force_refresh_state(self):
        """Wymusza odświeżenie stanu przełącznika z pominięciem cache'a."""
        _LOGGER.debug("Force refreshing switch state: %s", self._name)
        self._state = await self._buffer.force_read_coil(self._coil)
        self.async_write_ha_state()
        _LOGGER.debug("Switch %s force refreshed state: %s", self._name, self._state)
    
    def get_cache_info(self):
        """Zwraca informacje o cache'u dla tego przełącznika."""
        return {
            'name': self._name,
            'coil': self._coil,
            'current_state': self._state,
            'cached': self._buffer.is_coil_cached(self._coil),
            'cached_state': self._buffer.get_cached_coil_state(self._coil),
            'buffer_stats': self._buffer.get_performance_stats()
        }

    async def async_update(self):
        """Async update the state of the switch."""
        _LOGGER.debug("Async updating switch state: %s", self._name)
        
        # Odczytujemy stan coila - bufor sam zarządza odświeżaniem
        self._state = await self._buffer.async_read_coil(self._coil)
        _LOGGER.debug("Switch %s read coil state: %s", self._name, self._state)
        
        # Aktualizujemy stan encji w HA
        self.async_write_ha_state()
        
        # Debug cache performance
        if hasattr(self._buffer, 'get_performance_stats'):
            stats = self._buffer.get_performance_stats()
            _LOGGER.debug("Buffer performance: %s", stats)
    
    def debug_switch_state(self):
        """Debuguje stan przełącznika i cache'a."""
        _LOGGER.debug("=== Switch Debug Info ===")
        _LOGGER.debug("Name: %s", self._name)
        _LOGGER.debug("Coil: %s", self._coil)
        _LOGGER.debug("Current state: %s", self._state)
        _LOGGER.debug("Buffer cache stats: %s", self._buffer.get_performance_stats())
        _LOGGER.debug("Coil in cache: %s", self._buffer.is_coil_cached(self._coil))
        if self._buffer.is_coil_cached(self._coil):
            _LOGGER.debug("Cached coil state: %s", self._buffer.get_cached_coil_state(self._coil))
        _LOGGER.debug("=======================")


class ModbusHASRegisterSwitch(ModbusHASCoilSwitch):
    """Modbus Register Switch - inherits from ModbusHASCoilSwitch.
    
    Inherits from ModbusHASCoilSwitch:
    - async_added_to_hass()
    - async_will_remove_from_hass() 
    - name property
    - is_on property
    - _attr_should_poll, _attr_available
    """

    def __init__(self, hass, name, slave, register, command_on, command_off, 
                 verify_state, verify_register, register_type, state_on, state_off, 
                 unique_id=None, hub_name="fatek"):
        """Initialize the modbus register switch."""
        # Nie wywołujemy super().__init__() - inicjalizujemy ręcznie
        # ponieważ mamy inne parametry niż klasa bazowa
        self._hass = hass
        self._name = name
        self._slave = slave or 1
        self._register = register
        self._command_on = command_on
        self._command_off = command_off
        self._verify_state = verify_state
        self._verify_register = verify_register or register
        self._register_type = register_type
        self._state_on = state_on or command_on
        self._state_off = state_off or command_off
        self._state = None
        self._hub = None
        self._hub_name = hub_name
        self._cancel_timer = None
        
        # Dodajemy atrybut _buffer dla kompatybilności z klasą bazową
        # Tworzymy dummy buffer z scan_interval
        self._buffer = type('DummyBuffer', (), {
            '_scan_interval': datetime.timedelta(seconds=30)  # domyślny scan_interval
        })()
        
        # Dodajemy atrybuty wymagane przez klasę bazową
        self._attr_should_poll = False
        self._attr_available = True
        
        # Generujemy unikalny ID dla encji - używamy podany lub generujemy domyślny
        if unique_id:
            self._attr_unique_id = unique_id
        else:
            self._attr_unique_id = f"modbushas_register_switch_{name}_{register}"
        
        _LOGGER.debug("ModbusHASRegisterSwitch initialized: name=%s, register=%s, unique_id=%s", 
                     name, register, self._attr_unique_id)

    def checkhub(self):
        """Check and initialize hub connection."""
        if self._hub is None:
            try:
                if MODBUS_DOMAIN in self._hass.data:
                    self._hub = self._hass.data[MODBUS_DOMAIN][self._hub_name]
                    _LOGGER.debug("Hub found: %s (name: %s)", self._hub, self._hub_name)
                else:
                    _LOGGER.warning("MODBUS_DOMAIN not found in hass.data")
            except AttributeError as error:
                _LOGGER.error("Error accessing hub: %s", error)
                self._hub = None
            except KeyError as error:
                _LOGGER.error("Hub '%s' not found in MODBUS_DOMAIN", self._hub_name)
                self._hub = None

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.info("Async turning on register switch: %s", self._name)
        self.checkhub()
        if self._hub is not None:
            try:
                result = await self._hub.async_pb_call(
                    unit=self._slave,
                    address=self._register,
                    value=self._command_on,
                    use_call=CALL_TYPE_WRITE_REGISTER
                )
                if result:
                    self._state = True
                    self.async_write_ha_state()
                    _LOGGER.debug("Register switch %s turned ON successfully", self._name)
                else:
                    _LOGGER.error("Failed to write register %s for switch %s", self._register, self._name)
            except Exception as e:
                _LOGGER.error("Error writing register %s for switch %s: %s", self._register, self._name, e)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        _LOGGER.info("Async turning off register switch: %s", self._name)
        self.checkhub()
        if self._hub is not None:
            try:
                result = await self._hub.async_pb_call(
                    unit=self._slave,
                    address=self._register,
                    value=self._command_off,
                    use_call=CALL_TYPE_WRITE_REGISTER
                )
                if result:
                    self._state = False
                    self.async_write_ha_state()
                    _LOGGER.debug("Register switch %s turned OFF successfully", self._name)
                else:
                    _LOGGER.error("Failed to write register %s for switch %s", self._register, self._name)
            except Exception as e:
                _LOGGER.error("Error writing register %s for switch %s: %s", self._register, self._name, e)

    async def async_update(self):
        """Async update the state of the register switch."""
        if not self._verify_state:
            return

        _LOGGER.debug("Async updating register switch state: %s", self._name)
        self.checkhub()
        if self._hub is None:
            _LOGGER.error("Cannot read register %s: hub not available", self._register)
            return

        try:
            # Określ typ odczytu na podstawie register_type
            if self._register_type == "input":
                call_type = CALL_TYPE_REGISTER_INPUT
            else:
                call_type = CALL_TYPE_REGISTER_HOLDING

            result = await self._hub.async_pb_call(
                unit=self._slave,
                address=self._verify_register,
                value=1,
                use_call=call_type
            )

            if result and hasattr(result, 'registers') and len(result.registers) > 0:
                value = int(result.registers[0])
                if value == self._state_on:
                    self._state = True
                elif value == self._state_off:
                    self._state = False
                else:
                    _LOGGER.warning(
                        'Unexpected response from modbus slave %s register %s, got 0x%2x',
                        self._slave,
                        self._verify_register,
                        value)
                _LOGGER.debug("Register switch %s read state: %s (value: %s)", self._name, self._state, value)
            else:
                _LOGGER.error("Failed to read register %s for switch %s", self._verify_register, self._name)
        except Exception as e:
            _LOGGER.error("Error reading register %s for switch %s: %s", self._verify_register, self._name, e)

        # Aktualizujemy stan encji w HA
        self.async_write_ha_state()


