"""Modbus HAS integration."""
import logging
import asyncio

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.framer import FramerType

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import discovery
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

DOMAIN = "modbushas"

# Klucze w hass.data
DATA_WRITE_CLIENT = "modbushas_write_client"
DATA_COMMAND_SENDER = "modbushas_command_sender"


class ModbusWriteClient:
    """Dedykowany klient Modbus TCP do operacji zapisu.

    Oddzielne połączenie TCP, aby zapisy nie czekały w kolejce
    za odczytami na głównym hubie (który ma globalny asyncio.Lock).
    """

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()

    async def async_setup(self) -> bool:
        """Nawiąż połączenie z PLC."""
        try:
            self._client = AsyncModbusTcpClient(
                host=self._host,
                port=self._port,
                framer=FramerType.SOCKET,
                timeout=3,
                retries=3,
            )
            if await self._client.connect():
                _LOGGER.info("ModbusWriteClient: połączono z %s:%s", self._host, self._port)
                return True
            _LOGGER.error("ModbusWriteClient: nie udało się połączyć z %s:%s", self._host, self._port)
            return False
        except Exception as e:
            _LOGGER.error("ModbusWriteClient: błąd połączenia: %s", e)
            return False

    async def async_close(self) -> None:
        """Zamknij połączenie."""
        if self._client:
            self._client.close()
            self._client = None
            _LOGGER.info("ModbusWriteClient: połączenie zamknięte")

    async def async_write_coil(self, address: int, value: bool, slave: int = 1):
        """Zapis pojedynczego coila."""
        if not self._client:
            _LOGGER.error("ModbusWriteClient: brak połączenia")
            return None
        async with self._lock:
            result = await self._client.write_coil(address, value, device_id=slave)
            if result.isError():
                _LOGGER.error("ModbusWriteClient: błąd zapisu coil %s: %s", address, result)
                return None
            return result

    async def async_write_register(self, address: int, value: int, slave: int = 1):
        """Zapis pojedynczego rejestru."""
        if not self._client:
            _LOGGER.error("ModbusWriteClient: brak połączenia")
            return None
        async with self._lock:
            result = await self._client.write_register(address, value, device_id=slave)
            if result.isError():
                _LOGGER.error("ModbusWriteClient: błąd zapisu rejestru %s: %s", address, result)
                return None
            return result

    async def async_write_registers(self, address: int, values: list[int], slave: int = 1):
        """Zapis wielu kolejnych rejestrów."""
        if not self._client:
            _LOGGER.error("ModbusWriteClient: brak połączenia")
            return None
        async with self._lock:
            result = await self._client.write_registers(address, values, device_id=slave)
            if result.isError():
                _LOGGER.error("ModbusWriteClient: błąd zapisu rejestrów %s: %s", address, result)
                return None
            return result


class PlcCommandSender:
    """Wspólny mechanizm wysyłania komend do PLC.

    Format komendy w rejestrach R (od command_register):
      R[X]     — kod programu PLC (np. 301)
      R[X+1..] — parametry programu (ilość = kod // 100)

    Np. program 301 ma 3 parametry, 405 — 4 parametry, 3 — zero parametrów.
    """

    def __init__(self, hass: HomeAssistant, command_register: int):
        self._hass = hass
        self._command_register = command_register

    async def async_send_command(self, program_code: int, params: list[int], slave: int = 1) -> bool:
        """Wyślij komendę do PLC.

        Args:
            program_code: Kod programu PLC (np. 301).
            params: Lista parametrów — musi mieć długość = program_code // 100.
            slave: Adres slave Modbus.

        Returns:
            True jeśli zapis się powiódł.
        """
        expected_params = program_code // 100
        if len(params) != expected_params:
            _LOGGER.error(
                "Program %s wymaga %s parametrów, podano %s",
                program_code, expected_params, len(params),
            )
            return False

        values = [program_code] + params
        write_client = self._hass.data.get(DATA_WRITE_CLIENT)

        try:
            if write_client:
                result = await write_client.async_write_registers(
                    self._command_register, values, slave=slave,
                )
            else:
                from homeassistant.components.modbus.const import (
                    MODBUS_DOMAIN,
                    CALL_TYPE_WRITE_REGISTERS,
                )
                hub = self._hass.data[MODBUS_DOMAIN].get("fatek")
                if hub is None:
                    _LOGGER.error("PlcCommandSender: hub 'fatek' niedostępny")
                    return False
                result = await hub.async_pb_call(
                    unit=slave,
                    address=self._command_register,
                    value=values,
                    use_call=CALL_TYPE_WRITE_REGISTERS,
                )

            if not result:
                _LOGGER.error("PlcCommandSender: błąd zapisu programu %s", program_code)
                return False

            _LOGGER.info(
                "PlcCommandSender: program %s wysłany (rejestr=%s, wartości=%s)",
                program_code, self._command_register, values,
            )
            return True
        except Exception as e:
            _LOGGER.error("PlcCommandSender: wyjątek przy programie %s: %s", program_code, e)
            return False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Modbus HAS integration."""
    _LOGGER.info("Setting up Modbus HAS integration")

    # Dedykowany klient TCP do zapisów — nie blokuje odczytów na głównym hubie
    modbushas_config = config.get(DOMAIN, {})
    plc_host = modbushas_config.get("host")
    plc_port = modbushas_config.get("port")

    # Fallback: czytaj host/port z konfiguracji integracji modbus
    if not plc_host or not plc_port:
        modbus_configs = config.get("modbus", [])
        if modbus_configs:
            first_hub = modbus_configs[0]
            plc_host = plc_host or first_hub.get("host")
            plc_port = plc_port or first_hub.get("port")

    if not plc_host or not plc_port:
        _LOGGER.error("Brak konfiguracji host/port w modbushas ani modbus — write_client wyłączony")
        hass.data[DATA_WRITE_CLIENT] = None
        return True
    write_client = ModbusWriteClient(plc_host, plc_port)
    if await write_client.async_setup():
        hass.data[DATA_WRITE_CLIENT] = write_client
    else:
        _LOGGER.warning("ModbusWriteClient: nie udało się uruchomić, zapisy będą przez główny hub")
        hass.data[DATA_WRITE_CLIENT] = None

    async def _async_close_write_client(event):
        if hass.data.get(DATA_WRITE_CLIENT):
            await hass.data[DATA_WRITE_CLIENT].async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_write_client)

    # Wspólny mechanizm komend PLC
    command_register = modbushas_config.get("command_register")
    if command_register is not None:
        hass.data[DATA_COMMAND_SENDER] = PlcCommandSender(hass, command_register)
        _LOGGER.info("PlcCommandSender zainicjalizowany z rejestrem komend: %s", command_register)
    else:
        hass.data[DATA_COMMAND_SENDER] = None
        _LOGGER.warning("Brak command_register w konfiguracji modbushas — PlcCommandSender wyłączony")

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
    
    # Load binary_sensor platform if configured
    if DOMAIN in config and "binary_sensor" in config[DOMAIN]:
        _LOGGER.info("Loading binary_sensor platform from config")
        
        # Get the binary_sensor configuration
        binary_sensor_config = config[DOMAIN]["binary_sensor"]
        _LOGGER.info("Binary sensor config: %s", binary_sensor_config)
        
        # Sprawdź strukturę binary_sensor_config po rozszerzeniu !include
        if isinstance(binary_sensor_config, dict) and "binary_sensor" in binary_sensor_config:
            # Struktura po rozszerzeniu !include: {'binary_sensor': [platform1, platform2, platform3]}
            platforms = binary_sensor_config["binary_sensor"]
            if isinstance(platforms, list):
                for platform_config in platforms:
                    if platform_config.get("platform") == "modbushas":
                        _LOGGER.info("Loading binary_sensor platform: %s", platform_config)
                        discovery.load_platform(hass, "binary_sensor", "modbushas", platform_config, config)
            else:
                _LOGGER.error("Expected list of platforms, got: %s", type(platforms))
        elif isinstance(binary_sensor_config, list):
            # Struktura: [platform1, platform2, platform3] - bezpośrednia lista
            for platform_config in binary_sensor_config:
                if platform_config.get("platform") == "modbushas":
                    _LOGGER.info("Loading binary_sensor platform: %s", platform_config)
                    discovery.load_platform(hass, "binary_sensor", "modbushas", platform_config, config)
        else:
            _LOGGER.error("Unexpected binary_sensor_config structure: %s", type(binary_sensor_config))
    
    # Load sensor platform if configured
    if DOMAIN in config and "sensor" in config[DOMAIN]:
        _LOGGER.info("Loading sensor platform from config")
        
        # Get the sensor configuration
        sensor_config = config[DOMAIN]["sensor"]
        _LOGGER.info("Sensor config: %s", sensor_config)
        
        # Sprawdź strukturę sensor_config po rozszerzeniu !include
        if isinstance(sensor_config, dict) and "sensor" in sensor_config:
            # Struktura po rozszerzeniu !include: {'sensor': [platform1, platform2, platform3]}
            platforms = sensor_config["sensor"]
            if isinstance(platforms, list):
                for platform_config in platforms:
                    if platform_config.get("platform") == "modbushas":
                        _LOGGER.info("Loading sensor platform: %s", platform_config)
                        discovery.load_platform(hass, "sensor", "modbushas", platform_config, config)
            else:
                _LOGGER.error("Expected list of platforms, got: %s", type(platforms))
        elif isinstance(sensor_config, list):
            # Struktura: [platform1, platform2, platform3] - bezpośrednia lista
            for platform_config in sensor_config:
                if platform_config.get("platform") == "modbushas":
                    _LOGGER.info("Loading sensor platform: %s", platform_config)
                    discovery.load_platform(hass, "sensor", "modbushas", platform_config, config)
        else:
            _LOGGER.error("Unexpected sensor_config structure: %s", type(sensor_config))
    
    # Load switch platform if configured
    if DOMAIN in config and "switch" in config[DOMAIN]:
        _LOGGER.info("Loading switch platform from config")
        
        # Get the switch configuration
        switch_config = config[DOMAIN]["switch"]
        _LOGGER.info("Switch config: %s", switch_config)
        
        # Sprawdź strukturę switch_config po rozszerzeniu !include
        if isinstance(switch_config, dict) and "switch" in switch_config:
            # Struktura po rozszerzeniu !include: {'switch': [platform1, platform2, platform3]}
            platforms = switch_config["switch"]
            if isinstance(platforms, list):
                for platform_config in platforms:
                    if platform_config.get("platform") == "modbushas":
                        _LOGGER.info("Loading switch platform: %s", platform_config)
                        discovery.load_platform(hass, "switch", "modbushas", platform_config, config)
            else:
                _LOGGER.error("Expected list of platforms, got: %s", type(platforms))
        elif isinstance(switch_config, list):
            # Struktura: [platform1, platform2, platform3] - bezpośrednia lista
            for platform_config in switch_config:
                if platform_config.get("platform") == "modbushas":
                    _LOGGER.info("Loading switch platform: %s", platform_config)
                    discovery.load_platform(hass, "switch", "modbushas", platform_config, config)
        else:
            _LOGGER.error("Unexpected switch_config structure: %s", type(switch_config))
    
    # Load cover platform if configured
    if DOMAIN in config and "cover" in config[DOMAIN]:
        _LOGGER.info("Loading cover platform from config")

        cover_config = config[DOMAIN]["cover"]
        _LOGGER.info("Cover config: %s", cover_config)

        if isinstance(cover_config, dict) and "cover" in cover_config:
            platforms = cover_config["cover"]
            if isinstance(platforms, list):
                for platform_config in platforms:
                    if platform_config.get("platform") == "modbushas":
                        _LOGGER.info("Loading cover platform: %s", platform_config)
                        discovery.load_platform(hass, "cover", "modbushas", platform_config, config)
            else:
                _LOGGER.error("Expected list of platforms, got: %s", type(platforms))
        elif isinstance(cover_config, list):
            for platform_config in cover_config:
                if platform_config.get("platform") == "modbushas":
                    _LOGGER.info("Loading cover platform: %s", platform_config)
                    discovery.load_platform(hass, "cover", "modbushas", platform_config, config)
        else:
            _LOGGER.error("Unexpected cover_config structure: %s", type(cover_config))

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus HAS from a config entry."""
    _LOGGER.info("Setting up Modbus HAS from config entry")
    return True
