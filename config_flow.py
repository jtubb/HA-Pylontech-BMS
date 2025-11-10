"""Config flow to configure Pylontech BMS integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BATTERY_VARIANT,
    CONF_DEVICE_NAME,
    CONF_PROTOCOL_TYPE,
    DEFAULT_NAME,
    DEFAULT_PORT_BINARY,
    DEFAULT_PORT_CONSOLE,
    DOMAIN,
    PROTOCOL_BINARY,
    PROTOCOL_CONSOLE,
    VARIANT_SOK,
    VARIANT_STANDARD,
)
from .protocol import TCPBinaryProtocol, TCPConsoleProtocol

_LOGGER = logging.getLogger(__name__)


class PylontechFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Pylontech BMS config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.protocol_type: str | None = None
        self.config_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle protocol type selection."""
        errors = {}

        if user_input is not None:
            self.protocol_type = user_input[CONF_PROTOCOL_TYPE]
            return await self.async_step_connection()

        # Protocol selection schema
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_PROTOCOL_TYPE, default=PROTOCOL_CONSOLE
                ): vol.In(
                    {
                        PROTOCOL_CONSOLE: "Console Protocol (Text-based)",
                        PROTOCOL_BINARY: "Binary Protocol (Frame-based)",
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "console_desc": "Standard TCP console (port 1234)",
                "binary_desc": "Binary frame protocol (port 8234)",
            },
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle connection configuration."""
        errors = {}

        if user_input is not None:
            # Store connection data
            self.config_data.update(user_input)
            self.config_data[CONF_PROTOCOL_TYPE] = self.protocol_type

            # Validate connection
            try:
                device_info = await self._test_connection()

                # Set unique ID based on barcode
                await self.async_set_unique_id(device_info.barcode)
                self._abort_if_unique_id_configured()

                # Create entry
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({device_info.barcode})",
                    data=self.config_data,
                )

            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except ConnectionRefusedError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error during connection test: %s", err)
                errors["base"] = "unknown"

        # Build schema based on protocol type
        default_port = (
            DEFAULT_PORT_CONSOLE
            if self.protocol_type == PROTOCOL_CONSOLE
            else DEFAULT_PORT_BINARY
        )

        schema_dict = {
            vol.Required(CONF_HOST, default="pylontech.local"): str,
            vol.Required(CONF_PORT, default=default_port): int,
            vol.Optional(CONF_DEVICE_NAME, default="Battery"): str,
        }

        # Add variant selection for binary protocol
        if self.protocol_type == PROTOCOL_BINARY:
            schema_dict[
                vol.Required(CONF_BATTERY_VARIANT, default=VARIANT_STANDARD)
            ] = vol.In(
                {
                    VARIANT_STANDARD: "Pylontech Standard",
                    VARIANT_SOK: "SOK 48V Battery",
                }
            )

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="connection",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "protocol": (
                    "console" if self.protocol_type == PROTOCOL_CONSOLE else "binary"
                ),
            },
        )

    async def _test_connection(self) -> Any:
        """Test connection to BMS and retrieve device info.

        Returns:
            DeviceInfo from protocol

        Raises:
            TimeoutError: If connection times out
            ConnectionRefusedError: If connection is refused
            Exception: For other errors
        """
        # Create appropriate protocol instance
        if self.protocol_type == PROTOCOL_CONSOLE:
            protocol = TCPConsoleProtocol(
                host=self.config_data[CONF_HOST],
                port=self.config_data[CONF_PORT],
            )
        else:  # PROTOCOL_BINARY
            protocol = TCPBinaryProtocol(
                host=self.config_data[CONF_HOST],
                port=self.config_data[CONF_PORT],
                variant=self.config_data.get(CONF_BATTERY_VARIANT, VARIANT_STANDARD),
            )

        # Test connection
        await protocol.connect()
        try:
            device_info = await protocol.get_device_info()
            _LOGGER.info(
                "Successfully connected to %s %s (barcode: %s)",
                device_info.manufacturer,
                device_info.model,
                device_info.barcode,
            )
            return device_info
        finally:
            await protocol.disconnect()
