"""
Support for Modbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.modbus/
"""
import logging
import voluptuous as vol
import datetime

from homeassistant.components import modbus
from homeassistant.const import (
    CONF_NAME, CONF_SLAVE, CONF_COMMAND_ON, CONF_COMMAND_OFF)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COIL = "coil"
CONF_COILS = "coils"
CONF_REGISTER = "register"
CONF_REGISTERS = "registers"
CONF_VERIFY_STATE = "verify_state"
CONF_VERIFY_REGISTER = "verify_register"
CONF_REGISTER_TYPE = "register_type"
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"

REGISTER_TYPE_HOLDING = 'holding'
REGISTER_TYPE_INPUT = 'input'

REGISTERS_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_SLAVE): cv.positive_int,
    vol.Required(CONF_REGISTER): cv.positive_int,
    vol.Required(CONF_COMMAND_ON): cv.positive_int,
    vol.Required(CONF_COMMAND_OFF): cv.positive_int,
    vol.Optional(CONF_VERIFY_STATE, default=True): cv.boolean,
    vol.Optional(CONF_VERIFY_REGISTER):
        cv.positive_int,
    vol.Optional(CONF_REGISTER_TYPE, default=REGISTER_TYPE_HOLDING):
        vol.In([REGISTER_TYPE_HOLDING, REGISTER_TYPE_INPUT]),
    vol.Optional(CONF_STATE_ON): cv.positive_int,
    vol.Optional(CONF_STATE_OFF): cv.positive_int,
})

COILS_SCHEMA = vol.Schema({
    vol.Required(CONF_COIL): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SLAVE): cv.positive_int,
})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_COILS, CONF_REGISTERS),
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_COILS): [COILS_SCHEMA],
        vol.Optional(CONF_REGISTERS): [REGISTERS_SCHEMA]
    }))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Read configuration and create Modbus devices."""
    switches = []
    scan_interval =  config.get("scan_interval")
    """_LOGGER.info("Switch scan interval %s %s",scan_interval, type(scan_interval))"""
    coilBuffer = ModbusSwitchCoilBuffer("test", 1, scan_interval)
    if CONF_COILS in config:
        for coil in config.get(CONF_COILS):
            switches.append(ModbusHASCoilSwitch(
                coil.get(CONF_NAME),
                coil.get(CONF_SLAVE),
                coil.get(CONF_COIL),
                coilBuffer))
    if CONF_REGISTERS in config:
        for register in config.get(CONF_REGISTERS):
            switches.append(ModbusHASRegisterSwitch(
                register.get(CONF_NAME),
                register.get(CONF_SLAVE),
                register.get(CONF_REGISTER),
                register.get(CONF_COMMAND_ON),
                register.get(CONF_COMMAND_OFF),
                register.get(CONF_VERIFY_STATE),
                register.get(CONF_VERIFY_REGISTER),
                register.get(CONF_REGISTER_TYPE),
                register.get(CONF_STATE_ON),
                register.get(CONF_STATE_OFF)))
    add_entities(switches)


class ModbusSwitchCoilBuffer():
    def __init__(self, name, slave, scan_interval):
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
        # _LOGGER.info("Loght do refresh")

    def read_coil(self, coil):
        if(datetime.datetime.now()-self._scan_interval >= self._lastread):
            self._doread = True
        if(self._doread == True and self._maxcoil >= self._mincoil):
            coilnum  = self._maxcoil - self._mincoil + 1           
            self._result = modbus.HUB.read_coils(self._slave, self._mincoil, coilnum)
            if not self._result:
                _LOGGER.error("ModbusSwitchCoilBuffer read error form coil %s for %s coils", self._mincoil, coilnum)
                return
            self._doread = False
            self._lastread = datetime.datetime.now()
            # _LOGGER.info("Switch readed %s coils from %s ",coilnum, self._mincoil)     
        bitnum = coil - self._mincoil
        return bool(self._result.bits[bitnum])
        
             
        


class ModbusHASCoilSwitch(ToggleEntity):
    """Representation of a Modbus coil switch."""

    def __init__(self, name, slave, coil, buffer):
        """Initialize the coil switch."""
        self._name = name
        self._slave = int(slave) if slave else None
        self._coil = int(coil)
        self._is_on = None
        self._buffer = buffer
        buffer.set_coil(coil)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Set switch on."""
        modbus.HUB.write_coil(self._slave, self._coil, True)
        self._is_on = True
        self._buffer.refresh()

    def turn_off(self, **kwargs):
        """Set switch off."""
        modbus.HUB.write_coil(self._slave, self._coil, False)
        self._is_on = False
        self._buffer.refresh()

    def update(self):
        """Update the state of the switch."""
        #result = modbus.HUB.read_coils(self._slave, self._coil, 1)
        try:
            self._is_on = self._buffer.read_coil(self._coil)
        except AttributeError:
            _LOGGER.error(
                'No response from modbus slave %s coil %s',
                self._slave,
                self._coil)


class ModbusHASRegisterSwitch(ModbusHASCoilSwitch):
    """Representation of a Modbus register switch."""

    # pylint: disable=super-init-not-called
    def __init__(self, name, slave, register, command_on,
                 command_off, verify_state, verify_register,
                 register_type, state_on, state_off):
        """Initialize the register switch."""
        self._name = name
        self._slave = slave
        self._register = register
        self._command_on = command_on
        self._command_off = command_off
        self._verify_state = verify_state
        self._verify_register = (
            verify_register if verify_register else self._register)
        self._register_type = register_type

        if state_on is not None:
            self._state_on = state_on
        else:
            self._state_on = self._command_on

        if state_off is not None:
            self._state_off = state_off
        else:
            self._state_off = self._command_off

        self._is_on = None

    def turn_on(self, **kwargs):
        """Set switch on."""
        modbus.HUB.write_register(
            self._slave,
            self._register,
            self._command_on)
        if not self._verify_state:
            self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""
        modbus.HUB.write_register(
            self._slave,
            self._register,
            self._command_off)
        if not self._verify_state:
            self._is_on = False

    def update(self):
        """Update the state of the switch."""
        if not self._verify_state:
            return

        value = 0
        if self._register_type == REGISTER_TYPE_INPUT:
            result = modbus.HUB.read_input_registers(
                self._slave,
                self._register,
                1)
        else:
            result = modbus.HUB.read_holding_registers(
                self._slave,
                self._register,
                1)

        try:
            value = int(result.registers[0])
        except AttributeError:
            _LOGGER.error(
                'No response from modbus slave %s register %s',
                self._slave,
                self._verify_register)

        if value == self._state_on:
            self._is_on = True
        elif value == self._state_off:
            self._is_on = False
        else:
            _LOGGER.error(
                'Unexpected response from modbus slave %s '
                'register %s, got 0x%2x',
                self._slave,
                self._verify_register,
                value)
