"""
Support for Modbus Light sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.modbus/
"""
import logging
import voluptuous as vol

import homeassistant.components.modbus as modbus
from homeassistant.const import CONF_NAME
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_WHITE_VALUE,
    ATTR_XY_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
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

SUPPORT_MODBUS = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR |
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
    for coil in config.get("coils"):
        lights.append(ModbusLight(
            coil.get(CONF_NAME),
            coil.get(CONF_SLAVE),
            coil.get(CONF_COIL)))
    add_devices(lights)



class ModbusLight(Light):
    """Modbus Light."""

    def __init__(self, name, slave, coil):
        """Initialize the modbus coil sensor."""
        self._name = name
        self._slave = int(slave) if slave else 1
        self._coil = int(coil)
        self._state = None

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
        modbus.HUB.write_coil(self._slave, self._coil, True )
        self._state = True

    def turn_off(self, **kwargs):
        """Turn the light off."""
        modbus.HUB.write_coil(self._slave, self._coil, False )
        self._state = False

    def update(self):
        """Update the state of the switch."""
        result = modbus.HUB.read_coils(self._slave, self._coil, 1)
        if not result:
            _LOGGER.error(
                'No response from modbus slave %s coil %s',
                self._slave,
                self._coil)
            return
        self._state = bool(result.bits[0])

