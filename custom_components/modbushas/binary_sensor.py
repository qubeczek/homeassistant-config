"""
Support for Modbus Coil sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.modbus/
"""
import logging
import voluptuous as vol

import homeassistant.components.modbus as modbus
from homeassistant.const import CONF_NAME
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

from homeassistant.components.modbus import DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COIL = "coil"
CONF_COILS = "coils"
CONF_SLAVE = "slave"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COILS): [{
        vol.Required(CONF_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int
    }]
})



def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus binary sensors."""
    sensors = []
    for coil in config.get(CONF_COILS):
        sensors.append(ModbusHASBinarySensor(
            hass,        
            coil.get(CONF_NAME),
            coil.get(CONF_SLAVE),
            coil.get(CONF_COIL)))
    add_devices(sensors)


class ModbusHASBinarySensor(BinarySensorDevice):
    """Modbus coil sensor."""

    def __init__(self, hass, name, slave, coil):
        """Initialize the modbus coil sensor."""
        self._hass = hass
        self._hub = None
        self._name = name
        self._slave = int(slave) if slave else None
        self._coil = int(coil)
        self._value = None
        
    def checkhub(self):
        if(self._hub is None):
            try:
                if(MODBUS_DOMAIN in self._hass.data):
                    self._hub = self._hass.data[MODBUS_DOMAIN][DEFAULT_HUB] 
            except AttributeError as error:
                self._hub = None
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
				
    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    def update(self):
        """Update the state of the sensor."""
        try:
            self.checkhub()
            if(self._hub is None):
                return
            result = self._hub.read_coils(self._slave, self._coil, 1)
            if not result:
                _LOGGER.error(
                    'No response from modbus slave %s register %s',
                    self._slave,
                    self._coil)
                return 
            self._value = result.bits[0]
        except AttributeError as error:
            _LOGGER.error(
                'Exception during response from modbus slave %s coil %s: %s',
                self._slave,
                self._coil,
                error)