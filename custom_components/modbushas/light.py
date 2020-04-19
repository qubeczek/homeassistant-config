"""
Support for Modbus Light sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.modbus/
"""
import logging
import voluptuous as vol
import datetime

import homeassistant.components.modbus as modbus
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
from homeassistant.components.modbus import DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN

from homeassistant.helpers.restore_state import RestoreEntity

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


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Modbus binary sensors."""
    lights = []
    scan_interval =  config.get("scan_interval")
    """_LOGGER.info("Light scan interval %s %s",scan_interval, type(scan_interval))"""
    hub = hass.data[MODBUS_DOMAIN][DEFAULT_HUB]
    buffer = ModbusCoilBuffer(hub, "test", 1, scan_interval)
    for coil in config.get(CONF_COILS):
        lights.append(ModbusHASLight(
            hub,
            coil.get(CONF_NAME),
            coil.get(CONF_SLAVE),
            coil.get(CONF_COIL),
			buffer))
    async_add_devices(lights)
    
    



class ModbusCoilBuffer():
    def __init__(self, hub, name, slave, scan_interval):
        self._hub = hub
        self._name = name
        self._slave = slave
        self._scan_interval = scan_interval
        self._mincoil = 9999
        self._maxcoil = 0
        self._doread = True
        self._result = None
        self._lastread = datetime.datetime.now()
        
        
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
    
             
    async def write_coil(self, coil, value):
        self._doread = True 
        await self._hub.write_coil(self._slave, coil, value) 
        #if(self._result):
        #    self._result.bits[bitnum] = (byte)value
        
       
    async def read_coil(self, coil):
        if(datetime.datetime.now()-self._scan_interval >= self._lastread):
            self._doread = True
        if(self._doread == True and self._maxcoil >= self._mincoil):
            coilnum  = self._maxcoil - self._mincoil + 1           
            res = await self._hub.read_coils(self._slave, self._mincoil, coilnum)
            if not res:
                _LOGGER.error("ModbusCoilBuffer read error form coil %s for %s coils", self._mincoil, coilnum)
                return
            self._result = res
            self._doread = False
            self._lastread = datetime.datetime.now()
            """_LOGGER.info("Light readed %s coils from %s ",coilnum, self._mincoil)"""       
        bitnum = coil - self._mincoil
        return bool(self._result.bits[bitnum])
        
             
        

class ModbusHASLight(Light, RestoreEntity):
    """Modbus Light."""

    def __init__(self, hub, name, slave, coil, buffer):
        """Initialize the modbus coil sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else 1
        self._coil = int(coil)
        self._state = None
        self._buffer = buffer
        buffer.set_coil(coil)
        self._block_update = False
        self._logged_coil = 1000
        

    @property
    def name(self):
        """Return the name of the light if any."""
        return self._name


    @property
    def is_on(self):
        """Return true if light is on."""
        if(self._coil == self._logged_coil):
            _LOGGER.info("is_on checked %s:", self._state)          
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MODBUS

    async def turn_on(self, **kwargs):
        """Turn the light on."""
        if(self._coil == self._logged_coil):
             _LOGGER.info("Turn on start")  
        self._block_update = True
        self._state = True
        await self._buffer.write_coil(self._coil, self._state)              
        self._block_update = False
        if(self._coil == self._logged_coil):
            _LOGGER.info("Turn on end")  

    async def turn_off(self, **kwargs):
        """Turn the light off."""
        if(self._coil == self._logged_coil):
             _LOGGER.info("Turn off start")  
        self._block_update = True    
        self._state = False
        await self._buffer.write_coil(self._coil, self._state)    
        self._block_update = False
        if(self._coil == self._logged_coil):
            _LOGGER.info("Turn off end")  


    async def async_update(self):
        """Update the state of the switch."""
        """result = modbus.HUB.read_coils(self._slave, self._coil, 1)
        if not result:
            _LOGGER.error(
                'No response from modbus slave %s coil %s',
                self._slave,
                self._coil)
            return
        self._state = bool(result.bits[0])"""
        if(self._coil == self._logged_coil):
            _LOGGER.info("Update async start")          
        if(self._block_update == True):
             return
        if(self._coil == self._logged_coil):
            _LOGGER.info("Update async request")               
        try:
            
            result = await self._buffer.read_coil(self._coil)
            if(not result is None):
                self._state = result;
        except AttributeError as error:
            _LOGGER.error(
                'Exception during response from modbus slave %s coil %s: %s',
                self._slave,
                self._coil,
                error)
        if(self._coil == self._logged_coil):
            _LOGGER.info("Update async end")     
