"""Support for Pylontech BMS."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BATTERY_VARIANT,
    CONF_DEVICE_NAME,
    CONF_PROTOCOL_TYPE,
    DOMAIN,
    KEY_COORDINATOR,
    PLATFORMS,
    PROTOCOL_BINARY,
    PROTOCOL_CONSOLE,
    VARIANT_STANDARD,
)
from .coordinator import PylontechUpdateCoordinator
from .protocol import ProtocolBase, TCPBinaryProtocol, TCPConsoleProtocol

_LOGGER = logging.getLogger(__name__)


def _create_protocol(entry: ConfigEntry) -> ProtocolBase:
    """Create appropriate protocol instance from config entry.

    Args:
        entry: Config entry containing protocol configuration

    Returns:
        Protocol instance (TCPConsoleProtocol or TCPBinaryProtocol)
    """
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Backward compatibility: Default to console protocol if not specified
    protocol_type = entry.data.get(CONF_PROTOCOL_TYPE, PROTOCOL_CONSOLE)

    if protocol_type == PROTOCOL_BINARY:
        variant = entry.data.get(CONF_BATTERY_VARIANT, VARIANT_STANDARD)
        _LOGGER.debug(
            "Creating TCP binary protocol for %s:%s (variant=%s)",
            host,
            port,
            variant,
        )
        return TCPBinaryProtocol(host=host, port=port, variant=variant)
    else:
        _LOGGER.debug("Creating TCP console protocol for %s:%s", host, port)
        return TCPConsoleProtocol(host=host, port=port)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Pylontech BMS components from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create protocol instance
    protocol = _create_protocol(entry)

    # Validate connection and get device info
    try:
        _LOGGER.debug(
            "Connecting to Pylontech BMS at %s port %s",
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
        )
        await protocol.connect()
        device_info = await protocol.get_device_info()
        _LOGGER.info(
            "Successfully connected to %s %s (barcode: %s, firmware: %s)",
            device_info.manufacturer,
            device_info.model,
            device_info.barcode,
            device_info.firmware_version,
        )
    except Exception as err:
        _LOGGER.error("Failed to connect to Pylontech BMS: %s", err)
        raise ConfigEntryNotReady from err
    finally:
        await protocol.disconnect()

    # Create update coordinator
    device_name = entry.data.get(CONF_DEVICE_NAME, "Battery")
    coordinator = PylontechUpdateCoordinator(hass, entry, protocol, device_info, device_name)

    # Detect available sensors
    await coordinator.detect_sensors()

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_COORDINATOR: coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
