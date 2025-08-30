"""
Support for Modbus Light sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.modbus/
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
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
)

from homeassistant.const import (
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
)

from homeassistant.const import CONF_NAME

from homeassistant.components.light import (
    LightEntity, ColorMode)
    
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Definiuję własne stałe, ponieważ nie są już dostępne w modbus.const
CONF_COIL = "coil"
CONF_COILS = "coils"

# Dla prostych świateł on/off nie potrzebuję specjalnych funkcji
SUPPORT_MODBUS = 0

# Tworzę własny schemat zamiast importować z sensor
PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): "modbushas",
    vol.Optional("hub"): cv.string,
    vol.Optional("scan_interval"): vol.Any(cv.positive_int, cv.positive_float),
    vol.Required(CONF_COILS): [{
        vol.Required(CONF_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string
    }]
})


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Modbus binary sensors."""
    _LOGGER.info("=== ASYNC_SETUP_PLATFORM CALLED ===")
    _LOGGER.info("Setting up Modbus Light platform - config: %s", config)
    _LOGGER.info("Setting up Modbus Light platform - discovery_info: %s", discovery_info)
    _LOGGER.info("Config keys: %s", list(config.keys()) if config else "None")
    _LOGGER.info("Config platform: %s", config.get("platform") if config else "None")
    
    # Użyj discovery_info jeśli config jest pusty
    if not config and discovery_info:
        config = discovery_info
        _LOGGER.info("Using discovery_info as config")
    
    lights = []
    scan_interval = config.get("scan_interval")
    hub_name = config.get("hub", "fatek")
    
    # Konwertuj scan_interval na timedelta dla EntityPlatform
    if isinstance(scan_interval, (int, float)):
        scan_interval_timedelta = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_timedelta = datetime.timedelta(seconds=30)  # domyślna wartość
    else:
        scan_interval_timedelta = scan_interval
    
    _LOGGER.debug("Light scan interval: %s (type: %s), hub: %s", scan_interval, type(scan_interval), hub_name)
    
    buffer = ModbusCoilBuffer("test", hass, hub_name, 1, scan_interval_timedelta)
    
    # Sprawdź czy coils istnieje w config
    coils = config.get("coils")
    if not coils:
        _LOGGER.error("No coils found in config: %s", config)
        return
    
    for coil in coils:
        _LOGGER.debug("Adding light: %s, coil: %s", coil.get(CONF_NAME), coil.get(CONF_COIL))
        lights.append(ModbusHASLight(
            coil.get(CONF_NAME),
            coil.get(CONF_COIL),
            buffer,
            coil.get(CONF_UNIQUE_ID)))
    
    _LOGGER.info("Added %d Modbus lights", len(lights))
    async_add_devices(lights)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus binary sensors - legacy wrapper for async_setup_platform."""
    _LOGGER.info("=== SETUP_PLATFORM CALLED (legacy wrapper) ===")
    
    # Użyj discovery_info jeśli config jest pusty
    if not config and discovery_info:
        config = discovery_info
        _LOGGER.info("Using discovery_info as config in legacy wrapper")
    
    lights = []
    scan_interval = config.get("scan_interval")
    hub_name = config.get("hub", "fatek")
    
    # Konwertuj scan_interval na timedelta dla EntityPlatform
    if isinstance(scan_interval, (int, float)):
        scan_interval_timedelta = datetime.timedelta(seconds=scan_interval)
    elif scan_interval is None:
        scan_interval_timedelta = datetime.timedelta(seconds=30)  # domyślna wartość
    else:
        scan_interval_timedelta = scan_interval
    
    _LOGGER.debug("Light scan interval: %s (type: %s), hub: %s", scan_interval, type(scan_interval), hub_name)
    
    buffer = ModbusCoilBuffer("test", hass, hub_name, 1, scan_interval_timedelta)
    
    # Sprawdź czy coils istnieje w config
    coils = config.get("coils")
    if not coils:
        _LOGGER.error("No coils found in config: %s", config)
        return
    
    for coil in coils:
        _LOGGER.debug("Adding light: %s, coil: %s", coil.get(CONF_NAME), coil.get(CONF_COIL))
        lights.append(ModbusHASLight(
            coil.get(CONF_NAME),
            coil.get(CONF_COIL),
            buffer,
            coil.get(CONF_UNIQUE_ID)))
    
    _LOGGER.info("Added %d Modbus lights", len(lights))
    add_devices(lights)


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
        # Czyścimy cache dla tego coila
        if coil in self._coil_cache:
            del self._coil_cache[coil]
        # Odczytujemy pojedynczy coil
        return await self.async_read_single_coil(coil)
    
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
    
    async def smart_read_coils(self, coils_to_read=None):
        """Inteligentny odczyt coilów - używa cache'a gdy możliwe, odczytuje tylko gdy trzeba."""
        if coils_to_read is None:
            coils_to_read = list(range(self._mincoil, self._maxcoil + 1))
        
        coils_to_read = list(set(coils_to_read))  # Usuwamy duplikaty
        
        # Sprawdzamy które coile są już w cache'u i aktualne
        coils_in_cache = [coil for coil in coils_to_read if coil in self._coil_cache]
        coils_not_in_cache = [coil for coil in coils_to_read if coil not in self._coil_cache]
        
        _LOGGER.debug("Smart read: %d coils in cache, %d coils need reading", 
                     len(coils_in_cache), len(coils_not_in_cache))
        
        # Jeśli wszystkie coile są w cache'u i cache jest aktualny, zwracamy wyniki z cache'a
        if not coils_not_in_cache and not self.should_refresh_cache():
            _LOGGER.debug("All coils in cache, returning cached values")
            return {coil: self._coil_cache[coil] for coil in coils_to_read}
        
        # Odczytujemy coile których nie ma w cache'u
        if coils_not_in_cache:
            for coil in coils_not_in_cache:
                await self.async_read_single_coil(coil)
        
        # Zwracamy wszystkie żądane coile (z cache'a lub świeżo odczytane)
        return {coil: self._coil_cache.get(coil, False) for coil in coils_to_read}
    
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

    async def async_read_single_coil(self, coil):
        """Odczyt pojedynczego coila - szybszy niż odczyt całego zakresu."""
        _LOGGER.debug("Reading single coil: %s", coil)
        self.checkhub()
        if(self._hub is None):
            _LOGGER.error("Cannot read coil %s: hub not available", coil)
            return False
        
        try:
            # Używamy async_pb_call dla pojedynczego coila
            result = await self._hub.async_pb_call(
                unit=self._slave,
                address=coil,
                value=1,
                use_call=CALL_TYPE_COIL
            )
            if result and hasattr(result, 'bits') and len(result.bits) > 0:
                coil_state = bool(result.bits[0])
                # Aktualizujemy cache
                self._coil_cache[coil] = coil_state
                _LOGGER.debug("Single coil %s read successfully: %s", coil, coil_state)
                return coil_state
            else:
                _LOGGER.error("Failed to read single coil %s", coil)
                return False
        except Exception as e:
            _LOGGER.error("Error reading single coil %s: %s", coil, e)
            return False

    async def async_read_coil(self, coil):
        """Async version of read_coil for use in async context."""
        # Sprawdz czy minął scan_interval (scan_interval to już timedelta)
        if self._scan_interval and (datetime.datetime.now() - self._lastread >= self._scan_interval):
            self._doread = True
            _LOGGER.debug("Scan interval exceeded, forcing read")
            
        # Sprawdzamy cache dla pojedynczego coila
        if coil in self._coil_cache:
            _LOGGER.debug("Using cached value for coil %s: %s", coil, self._coil_cache[coil])
            return self._coil_cache[coil]
            
        if(self._doread == True and self._maxcoil >= self._mincoil):
            coilnum = self._maxcoil - self._mincoil + 1   
            self.checkhub()
            if(self._hub is None):
                _LOGGER.error("Cannot read coil %s: hub not available", coil)
                return False
                
            _LOGGER.debug("Reading %d coils from %s to %s", coilnum, self._mincoil, self._maxcoil)
            
            try:
                # Używamy async_pb_call bezpośrednio z hub
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
                
            self._doread = False
            self._lastread = datetime.datetime.now()
            _LOGGER.debug("Successfully read %s coils from %s", coilnum, self._mincoil)
            
            # Aktualizujemy cache dla wszystkich odczytanych coilów
            for i, coil_addr in enumerate(range(self._mincoil, self._maxcoil + 1)):
                if i < len(self._result.bits):
                    self._coil_cache[coil_addr] = bool(self._result.bits[i])
            
        if self._result is None:
            _LOGGER.error("No result available for coil %s", coil)
            return False
            
        bitnum = coil - self._mincoil
        if bitnum < 0 or bitnum >= len(self._result.bits):
            _LOGGER.error("Coil %s out of range (bit %s, max %s)", coil, bitnum, len(self._result.bits))
            return False
            
        result = bool(self._result.bits[bitnum])
        _LOGGER.debug("Coil %s (bit %s) state: %s", coil, bitnum, result)
        return result

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
                    await asyncio.sleep(0.1)
                    verified_state = await self.async_read_single_coil(coil)
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


class ModbusHASLight(LightEntity):
    """Modbus Light."""

    _attr_should_poll = False
    _attr_available = True

    def __init__(self, name, coil, buffer, unique_id=None):
        """Initialize the modbus coil sensor."""
        self._name = name
        self._coil = int(coil)
        self._state = None
        self._buffer = buffer
        self._cancel_timer = None
        
        # Generujemy unikalny ID dla encji - używamy podany lub generujemy domyślny
        if unique_id:
            self._attr_unique_id = unique_id
        else:
            self._attr_unique_id = f"modbushas_light_{name}_{coil}"
        
        buffer.set_coil(coil)
        _LOGGER.debug("ModbusHASLight initialized: name=%s, coil=%s, unique_id=%s", name, coil, self._attr_unique_id)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        
        # Schedule initial update
        self.async_schedule_update_ha_state(force_refresh=True)
        
        # Schedule regular updates based on scan_interval
        if hasattr(self._buffer, '_scan_interval') and self._buffer._scan_interval:
            scan_seconds = self._buffer._scan_interval.total_seconds()
            if scan_seconds > 0:
                self._cancel_timer = async_track_time_interval(
                    self.hass,
                    self._async_update_if_not_in_progress,
                    datetime.timedelta(seconds=scan_seconds)
                )
                _LOGGER.debug("Light %s scheduled updates every %s seconds", self._name, scan_seconds)
        
        _LOGGER.debug("Light %s added to hass", self._name)

    @callback
    def _async_update_if_not_in_progress(self, now=None):
        """Update the entity state if not already in progress."""
        _LOGGER.debug("Scheduled update for light: %s", self._name)
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_will_remove_from_hass(self):
        """Handle entity which will be removed."""
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        await super().async_will_remove_from_hass()

    @property
    def name(self):
        """Return the name of the light if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MODBUS

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self):
        """Flag supported color modes."""
        return {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        _LOGGER.debug("Async turning on light: %s", self._name)
        if await self._buffer.async_write_coil(self._coil, True, verify_after_write=True):
            self._state = True
            # Nie potrzebujemy refresh - cache jest już zaktualizowany
            self.async_write_ha_state()
            _LOGGER.debug("Light %s turned ON successfully", self._name)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        _LOGGER.debug("Async turning off light: %s", self._name)
        if await self._buffer.async_write_coil(self._coil, False, verify_after_write=True):
            self._state = False
            # Nie potrzebujemy refresh - cache jest już zaktualizowany
            self.async_write_ha_state()
            _LOGGER.debug("Light %s turned OFF successfully", self._name)
    
    async def force_refresh_state(self):
        """Wymusza odświeżenie stanu światła z pominięciem cache'a."""
        _LOGGER.debug("Force refreshing light state: %s", self._name)
        self._state = await self._buffer.force_read_coil(self._coil)
        self.async_write_ha_state()
        _LOGGER.debug("Light %s force refreshed state: %s", self._name, self._state)
    
    def get_cache_info(self):
        """Zwraca informacje o cache'u dla tego światła."""
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
        _LOGGER.debug("Async updating light state: %s", self._name)
        
        # Sprawdzamy cache najpierw
        if hasattr(self._buffer, '_coil_cache') and self._coil in self._buffer._coil_cache:
            cached_state = self._buffer._coil_cache[self._coil]
            _LOGGER.debug("Light %s using cached state: %s", self._name, cached_state)
            self._state = cached_state
        else:
            # Jeśli nie ma w cache, odczytujemy pojedynczy coil
            self._state = await self._buffer.async_read_single_coil(self._coil)
            _LOGGER.debug("Light %s read single coil state: %s", self._name, self._state)
        
        _LOGGER.debug("Light %s async updated state: %s", self._name, self._state)
        
        # Debug cache performance
        if hasattr(self._buffer, 'get_performance_stats'):
            stats = self._buffer.get_performance_stats()
            _LOGGER.debug("Buffer performance: %s", stats)
    
    def debug_light_state(self):
        """Debuguje stan światła i cache'a."""
        _LOGGER.debug("=== Light Debug Info ===")
        _LOGGER.debug("Name: %s", self._name)
        _LOGGER.debug("Coil: %s", self._coil)
        _LOGGER.debug("Current state: %s", self._state)
        _LOGGER.debug("Buffer cache stats: %s", self._buffer.get_performance_stats())
        _LOGGER.debug("Coil in cache: %s", self._buffer.is_coil_cached(self._coil))
        if self._buffer.is_coil_cached(self._coil):
            _LOGGER.debug("Cached coil state: %s", self._buffer.get_cached_coil_state(self._coil))
        _LOGGER.debug("=======================")

