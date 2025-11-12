"""Constants for the Pylontech BMS component."""
from datetime import timedelta
from enum import Enum

from homeassistant.const import Platform

DOMAIN = "pylontech"

PLATFORMS = [Platform.SENSOR]

DEFAULT_NAME = "Pylontech BMS"
SCAN_INTERVAL = timedelta(seconds=30)

KEY_COORDINATOR = "coordinator"

# Configuration keys
CONF_PROTOCOL_TYPE = "protocol_type"
CONF_BATTERY_VARIANT = "battery_variant"
CONF_DEVICE_NAME = "device_name"

# Protocol types
PROTOCOL_CONSOLE = "console"
PROTOCOL_BINARY = "binary"

# Default ports
DEFAULT_PORT_CONSOLE = 1234
DEFAULT_PORT_BINARY = 8234

# Battery variants
VARIANT_STANDARD = "standard"
VARIANT_SOK = "sok"


class ConnectionType(Enum):
    """BMS connection types."""

    TCP_CONSOLE = "tcp_console"
    TCP_BINARY = "tcp_binary"


class BatteryVariant(Enum):
    """Battery manufacturer variants."""

    PYLONTECH_STANDARD = "standard"
    SOK_48V = "sok"
