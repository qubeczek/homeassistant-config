"""
Support for Modbus Light sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.modbus/
"""
import logging
import voluptuous as vol
import datetime

import homeassistant.components.modbus as modbus

from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COILS,
    CONF_HUB,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
    DEFAULT_HUB,
    MODBUS_DOMAIN,
)

from homeassistant.const import CONF_NAME

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_WHITE_VALUE,
    ATTR_XY_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP,
    SUPPORT_WHITE_VALUE, Light)
    
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_STATE, CONF_BRIGHTNESS, CONF_RGB,
    CONF_COLOR_TEMP)
    
from homeassistant.helpers import config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COIL = "coil"
CONF_COILS = "coils"
CONF_SLAVE = "slave"

SUPPORT_MODBUS = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                SUPPORT_WHITE_VALUE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COILS): [{
        vol.Required(CONF_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus binary sensors."""
    lights = []
    scan_interval =  config.get("scan_interval")
#    hub = hass.data[MODBUS_DOMAIN][DEFAULT_HUB];
    """_LOGGER.info("Light scan interval %s %s",scan_interval, type(scan_interval))"""
    buffer = ModbusCoilBuffer("test", hass, 1, scan_interval)
    for coil in config.get("coils"):
        lights.append(ModbusHASLight(
            coil.get(CONF_NAME),
            coil.get(CONF_COIL),
			buffer))
    add_devices(lights)
    
    



class ModbusCoilBuffer():
    def __init__(self, name, hass, slave, scan_interval):
        self._hass = hass
        self._name = name
        self._slave = slave
        self._scan_interval = scan_interval
        self._mincoil = 9999
        self._maxcoil = 0
        self._doread = True
        self._result = None
        self._lastread = datetime.datetime.now()
        self._hub = None;
    
    def checkhub(self):
        if(self._hub is None):
            try:
                if(MODBUS_DOMAIN in self._hass.data):
                    self._hub = self._hass.data[MODBUS_DOMAIN][DEFAULT_HUB] 
            except AttributeError as error:
                self._hub = None
        
    def set_coil(self, coil):
        if(coil < self._mincoil):
            self._mincoil = coil
            self._doread = True
        if(coil > self._maxcoil):
            self._maxcoil = coil
            self._doread = True

    def refresh(self):
        self._doread = True
        """_LOGGER.info("Loght do refresh")"""

    def read_coil(self, coil):
        if(datetime.datetime.now()-self._scan_interval >= self._lastread):
            self._doread = True
        if(self._doread == True and self._maxcoil >= self._mincoil):
            coilnum  = self._maxcoil - self._mincoil + 1   
            self.checkhub()
            if(self._hub is None):
                return
            self._result = self._hub.read_coils(self._slave, self._mincoil, coilnum)
            if not self._result:
                _LOGGER.error("ModbusCoilBuffer read error form coil %s for %s coils", self._mincoil, coilnum)
                return
            self._doread = False
            self._lastread = datetime.datetime.now()
            """_LOGGER.info("Light readed %s coils from %s ",coilnum, self._mincoil)"""       
        bitnum = coil - self._mincoil
        return bool(self._result.bits[bitnum])
        
    def write_coil(self, coil, value):
        self.checkhub()
        if(self._hub is None):
            return
        self._hub.write_coil(self._slave, coil, value )

      
        
             
        

class ModbusHASLight(Light):
    """Modbus Light."""

    def __init__(self, name, coil, buffer):
        """Initialize the modbus coil sensor."""
        self._name = name
        self._coil = int(coil)
        self._state = None
        self._buffer = buffer
        buffer.set_coil(coil)
		

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

    def turn_on(self, **kwargs):
        """Turn the light on."""
        self._buffer.write_coil(self._coil, True )
        self._state = True
        self._buffer.refresh()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._buffer.write_coil(self._coil, False )
        self._state = False
        self._buffer.refresh()

    def update(self):
        """Update the state of the switch."""
        """result = modbus.HUB.read_coils(self._slave, self._coil, 1)
        if not result:
            _LOGGER.error(
                'No response from modbus slave %s coil %s',
                self._slave,
                self._coil)
            return
        self._state = bool(result.bits[0])"""
        self._state = self._buffer.read_coil(self._coil)

