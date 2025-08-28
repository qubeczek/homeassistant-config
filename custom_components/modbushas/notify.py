"""
ModbusHAS notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging
import voluptuous as vol

import homeassistant.components.modbus as modbus

from homeassistant.components.notify import (ATTR_TITLE, ATTR_TITLE_DEFAULT,
                                             ATTR_DATA, PLATFORM_SCHEMA,
                                             BaseNotificationService)
	
_LOGGER = logging.getLogger(__name__)
EVENT_NOTIFY = "notify"
ATTR_ADDRESS = "address"
ATTR_VALUE = "value"

def get_service(hass, config, arg1):
    """Get the ModbusHAS notification service."""
    return ModbusHASNotificationService(hass,1)


class ModbusHASNotificationService(BaseNotificationService):
    """Implement ModbusHAS notification service."""

    def __init__(self, hass, slave):
        """Initialize the service."""
        self._slave = slave
        self.hass = hass

#    @property
#    def targets(self):
#        """Return a dictionary of registered targets."""
#        return {"test target name": "test target id"}
				

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = kwargs.get(ATTR_DATA) or {}
        address = data.get(ATTR_ADDRESS,'0')
        value = data.get(ATTR_VALUE,'0')
#        _LOGGER.error('Zapis modbus do rejetru  %s wartosc %s',address,value)
        modbus.HUB.write_register(self._slave, address, value)

