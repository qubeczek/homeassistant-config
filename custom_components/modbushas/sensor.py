"""
Support for Modbus Register sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modbus/
"""
import logging
import voluptuous as vol
import datetime
import pymodbus

import homeassistant.components.modbus as modbus
from homeassistant.const import (
    CONF_NAME, CONF_OFFSET, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.modbus import DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COUNT = "count"
CONF_PRECISION = "precision"
CONF_REGISTER = "register"
CONF_REGISTERS = "registers"
CONF_SCALE = "scale"
CONF_SLAVE = "slave"
CONF_SIGNED = "signed"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_REGISTERS): [{
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_REGISTER): cv.positive_int,
        vol.Optional(CONF_COUNT, default=1): cv.positive_int,
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_SIGNED, default=0): cv.positive_int
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus sensors."""
    sensors = []
    scan_interval =  config.get("scan_interval")
    hub = hass.data[MODBUS_DOMAIN][DEFAULT_HUB]
    buffer = ModbusRegisterBuffer(hub, "buffer",1,scan_interval)
    for register in config.get(CONF_REGISTERS):
        sensors.append(ModbusHASRegisterSensor(
            hub,
            register.get(CONF_NAME),
            register.get(CONF_SLAVE),
            register.get(CONF_REGISTER),
            register.get(CONF_UNIT_OF_MEASUREMENT),
            register.get(CONF_COUNT),
            register.get(CONF_SCALE),
            register.get(CONF_OFFSET),
            register.get(CONF_PRECISION),
		    register.get(CONF_SIGNED),
            buffer
						))
    add_devices(sensors)


    

class ModbusRegisterBuffer():
    def __init__(self, hub, name, slave, scan_interval):
        self._hub = hub
        self._name = name
        self._slave = slave
        self._scan_interval = scan_interval
        self._minreg = 99999
        self._maxreg = 0
        self._doread = True
        self._result = None
        self._lastread = datetime.datetime.now()
        
        
    def set_register(self, register, count):
        if(register < self._minreg):
            self._minreg = register
            self._doread = True
        if(register+count-1 > self._maxreg):
            self._maxreg = register+count-1
            self._doread = True
        _LOGGER.info("Sensor buffer min/max %s / %s",self._minreg, self._maxreg)

    def refresh(self):
        self._doread = True
        """_LOGGER.info("Loght do refresh")"""

    def read_register(self, register, count):
        if(datetime.datetime.now()-self._scan_interval >= self._lastread):
            self._doread = True
        if(self._doread == True and self._maxreg >= self._minreg):
            cnt  = self._maxreg - self._minreg + 1           
            self._result = self._hub.read_holding_registers(
              self._slave,
              self._minreg,
              cnt)
            if not self._result:
                _LOGGER.error("ModbusRegisterBuffer read error form reg %s for %s coils", self._minreg, cnt)
                return
            self._doread = False
            self._lastread = datetime.datetime.now()
            """_LOGGER.info("Sensor readed %s registers from %s ",cnt, self._minreg)"""
        regis = []
        for i in range(register - self._minreg, register - self._minreg + count):
            regis.append(self._result.registers[i])
        return regis


class ModbusHASRegisterSensor(RestoreEntity):
    """Modbus resgister sensor."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(self, hub, name, slave, register, unit_of_measurement, count,
                 scale, offset, precision, signed, buffer):
        """Initialize the modbus register sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._register = int(register)
        self._unit_of_measurement = unit_of_measurement
        self._count = int(count)
        self._scale = scale
        self._offset = offset
        self._precision = precision
        self._signed = signed
        self._buffer = buffer
        self._value = None
        buffer.set_register(register, count)
        
#    async def async_added_to_hass(self):
#        """Handle entity which will be added."""
#        state = await self.async_get_last_state()
#        if not state:
#            return
#        self._value = state.state
        
    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Update the state of the sensor."""
        """resultA = modbus.HUB.read_holding_registers(
            self._slave,
            self._register,
            self._count)
        if resultA:
            result = resultA.registers"""
        try:
            result = self._buffer.read_register(self._register, self._count)    
            if not result:
                _LOGGER.error(
                    'No response from modbus slave %s register %s',
                    self._slave,
                    self._register)
                return 
        except AttributeError as error:
            _LOGGER.error(
                'Exception during response from modbus slave %s register %s: %s',
                self._slave,
                self._register,
                error)
            return                
        val = 0
        for i, res in enumerate(result):
            r = -1
            r = res
            if i == 0 and self._signed == 1 and r > 32768:
# and res.bits[0] == 1:
              r = 0 - (r - 65536)
              r = 0 - r
            val += r * (2**(i*16))
        self._value = format(
            self._scale * val + self._offset,
            ".{}f".format(self._precision))
