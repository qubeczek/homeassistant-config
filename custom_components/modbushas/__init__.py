"""Modbus HAS integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

DOMAIN = "modbushas"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Modbus HAS integration."""
    _LOGGER.info("Setting up Modbus HAS integration")
    
    # Load light platform if configured
    if DOMAIN in config and "light" in config[DOMAIN]:
        _LOGGER.info("Loading light platform from config")
        
        # Get the light configuration
        light_config = config[DOMAIN]["light"]
        _LOGGER.info("Light config: %s", light_config)
        
        # Sprawdź strukturę light_config po rozszerzeniu !include
        if isinstance(light_config, dict) and "light" in light_config:
            # Struktura po rozszerzeniu !include: {'light': [platform1, platform2, platform3]}
            platforms = light_config["light"]
            if isinstance(platforms, list):
                for platform_config in platforms:
                    if platform_config.get("platform") == "modbushas":
                        _LOGGER.info("Loading platform: %s", platform_config)
                        discovery.load_platform(hass, "light", "modbushas", platform_config, config)
            else:
                _LOGGER.error("Expected list of platforms, got: %s", type(platforms))
        elif isinstance(light_config, list):
            # Struktura: [platform1, platform2, platform3] - bezpośrednia lista
            for platform_config in light_config:
                if platform_config.get("platform") == "modbushas":
                    _LOGGER.info("Loading platform: %s", platform_config)
                    discovery.load_platform(hass, "light", "modbushas", platform_config, config)
        else:
            _LOGGER.error("Unexpected light_config structure: %s", type(light_config))
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus HAS from a config entry."""
    _LOGGER.info("Setting up Modbus HAS from config entry")
    return True
