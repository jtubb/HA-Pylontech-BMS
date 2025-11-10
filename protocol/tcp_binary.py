"""TCP Binary Protocol implementation for Pylontech BMS.

This module implements the binary frame protocol over TCP.
Based on PylonToMQTT implementation with frame structure:
~[VER][ADDR][CID1][CID2][LEN][INFO][CHECKSUM]\r

Commands (CID2):
- 0x90: Get pack count
- 0xC1: Get version info
- 0xC2: Get barcode
- 0x42: Get analog values (voltage, current, SOC, temps, cells)
- 0x44: Get alarm info (protection status, faults)
"""

from __future__ import annotations

import asyncio
from asyncio import StreamReader, StreamWriter
import logging
from typing import Any

from .base import ProtocolBase
from ..const import BatteryVariant, ConnectionType, VARIANT_SOK, VARIANT_STANDARD
from ..models import BatteryData, DeviceInfo

_LOGGER = logging.getLogger(__name__)


class TCPBinaryProtocol(ProtocolBase):
    """Pylontech BMS TCP binary frame protocol implementation.

    Uses binary frames over TCP connection (configurable port, typically 8234).
    Supports standard Pylontech (version 0x20) and SOK 48V (version 0x25) variants.
    """

    # Protocol constants
    CID1_FIXED = 0x46
    ADDR_DEFAULT = 0x00  # Broadcast address for initial queries (matches PylonToMQTT)

    # Command IDs (CID2)
    CMD_PACK_COUNT = 0x90
    CMD_VERSION_INFO = 0xC1
    CMD_BARCODE = 0xC2
    CMD_ANALOG_VALUES = 0x42
    CMD_ALARM_INFO = 0x44

    # Protocol version bytes
    VERSION_STANDARD = 0x20
    VERSION_SOK = 0x25

    def __init__(self, host: str, port: int, variant: str = VARIANT_STANDARD) -> None:
        """Initialize the TCP binary protocol.

        Args:
            host: BMS hostname or IP address
            port: TCP port (typically 8234)
            variant: Battery variant ("standard" or "sok")

        Note:
            SOK BMS responds with VER=0x25 but expects requests with VER=0x20.
            Both variants use VERSION_STANDARD (0x20) for requests.
        """
        self.host = host
        self.port = port
        self.variant = variant
        # CRITICAL: Always use VERSION_STANDARD (0x20) for requests
        # SOK BMS responds with 0x25 but expects requests with 0x20
        self.version_byte = self.VERSION_STANDARD
        self.reader: StreamReader | None = None
        self.writer: StreamWriter | None = None

    async def connect(self) -> None:
        """Establish TCP connection to BMS."""
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), 5
        )
        _LOGGER.debug("Connected to %s:%s (variant=%s)", self.host, self.port, self.variant)

    async def disconnect(self) -> None:
        """Close TCP connection."""
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
            self.reader = None
            self.writer = None
            _LOGGER.debug("Disconnected from %s:%s", self.host, self.port)

    def _build_frame(self, cid2: int, info: bytes = b"", address: int | None = None) -> bytes:
        """Construct frame with ASCII hex encoding.

        Frame format: ~[HEX_HEADER][HEX_INFO][HEX_CHECKSUM]\r

        CRITICAL: Entire frame is ASCII hex encoded!
        - Header (VER, ADDR, CID1, CID2, LEN): ASCII hex
        - Info payload: ASCII hex (e.g., device ID 0x01 becomes ASCII "01")
        - Checksum: ASCII hex

        Args:
            cid2: Command ID (CID2 byte)
            info: Optional info payload as ASCII hex bytes (e.g., b"01" for device 1)
            address: Optional address byte (defaults to ADDR_DEFAULT=0x00 for broadcast)

        Returns:
            Complete frame with ASCII hex encoding
        """
        # Use provided address or default to broadcast
        addr_byte = address if address is not None else self.ADDR_DEFAULT

        # Build header as ASCII hex string
        info_len_int = self._encode_info_length_int(len(info))
        header = f"{self.version_byte:02X}{addr_byte:02X}{self.CID1_FIXED:02X}{cid2:02X}{info_len_int:04X}"
        header_bytes = header.encode('ascii')

        # Calculate checksum on ASCII header + ASCII hex info
        checksum_data = header_bytes + info
        checksum = self._calculate_checksum_ascii(checksum_data)
        checksum_hex = f"{checksum:04X}".encode('ascii')

        # Assemble frame: ~ + ASCII_HEX_HEADER + ASCII_HEX_INFO + ASCII_HEX_CHECKSUM + \r
        frame = b'~' + header_bytes + info + checksum_hex + b'\r'

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Built frame: %s", frame)
            _LOGGER.debug("  Header (hex): %s", header)
            _LOGGER.debug("  Address: 0x%02X", addr_byte)
            _LOGGER.debug("  Info (ascii hex): %s", info.decode('ascii') if info else "(empty)")
            _LOGGER.debug("  Checksum: %04X", checksum)

        return frame

    def _calculate_checksum(self, data: bytes) -> bytes:
        """Calculate inverted sum checksum (returns as bytes).

        Algorithm: checksum = (~sum % 0x10000) + 1

        Args:
            data: Data bytes to checksum

        Returns:
            2-byte checksum
        """
        total = sum(data)
        checksum = ((~total % 0x10000) + 1) & 0xFFFF
        return checksum.to_bytes(2, 'big')

    def _calculate_checksum_ascii(self, data: bytes) -> int:
        """Calculate inverted sum checksum (returns as integer).

        Algorithm: checksum = (~sum % 0x10000) + 1

        Args:
            data: Data bytes to checksum

        Returns:
            Checksum as integer (0x0000-0xFFFF)
        """
        total = sum(data)
        checksum = ((~total % 0x10000) + 1) & 0xFFFF
        return checksum

    def _encode_info_length_int(self, length: int) -> int:
        """Encode info length with validation bits (returns integer).

        Uses PylonToMQTT algorithm:
        - Sum nibbles of length value
        - Calculate modulo 16
        - Validation = (~modulo + 1) & 0xF
        - Encoded = (validation << 12) | length

        Args:
            length: Info payload length (0-4095)

        Returns:
            Encoded length as integer with validation bits
        """
        if length == 0:
            return 0

        # Sum all nibbles of the length
        lenid_sum = (length & 0xF) + ((length >> 4) & 0xF) + ((length >> 8) & 0xF)
        lenid_modulo = lenid_sum % 16
        # Validation = inverted modulo + 1
        lenid_invert_plus_one = (0b1111 - lenid_modulo + 1) & 0xF
        # Combine: upper 4 bits = validation, lower 12 bits = length
        return (lenid_invert_plus_one << 12) + length

    def _encode_info_length(self, length: int) -> bytes:
        """Encode info length with validation bits (returns bytes).

        Lower 12 bits = length
        Upper 4 bits = validation (length >> 8)

        Args:
            length: Info payload length

        Returns:
            2-byte encoded length
        """
        encoded = self._encode_info_length_int(length)
        return encoded.to_bytes(2, 'big')

    def _decode_info_length(self, length_bytes: bytes) -> int:
        """Decode and validate info length.

        Args:
            length_bytes: 2 bytes containing encoded length

        Returns:
            Decoded length value

        Note:
            SOK BMS responses use plain 2-byte length without validation encoding.
            Standard Pylontech uses validation bits in upper 4 bits.
            This method tries validation first, falls back to plain length.
        """
        encoded = int.from_bytes(length_bytes, 'big')
        length = encoded & 0x0FFF
        validation = (encoded >> 12) & 0x0F
        expected = (length >> 8) & 0x0F

        # Check if validation bits match (standard Pylontech)
        if validation == expected:
            return length

        # SOK BMS doesn't use validation encoding - use plain 2-byte value
        # But only use lower 12 bits to avoid huge values from validation bits
        if encoded <= 0xFFF:  # Reasonable length (< 4096 bytes)
            return encoded
        else:
            # If upper bits are set, likely only lower 8-10 bits are length
            # Try just lower byte first
            return encoded & 0xFF

    async def _send_frame(self, frame: bytes) -> bytes:
        """Send frame over TCP and receive response.

        Args:
            frame: Complete frame to send

        Returns:
            Info payload from response (after validation)

        Raises:
            ValueError: If frame markers or checksum invalid
            TimeoutError: If no response received
        """
        # Send frame
        self.writer.write(frame)
        await asyncio.wait_for(self.writer.drain(), 5)

        # Read response frame
        response = bytearray()

        # Wait for frame start marker '~' (0x7E)
        # SOK BMS may take longer to respond, use 10 second timeout
        while True:
            byte = await asyncio.wait_for(self.reader.read(1), 10)
            if byte == b'~':
                response.extend(byte)
                break

        # Read until frame end marker '\r' (0x0D)
        while True:
            byte = await asyncio.wait_for(self.reader.read(1), 5)
            response.extend(byte)
            if byte == b'\r':
                break

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Received ASCII frame: %s", response)
            _LOGGER.debug("Received ASCII frame (hex): %s", response.hex())

        return self._parse_frame(bytes(response))

    def _parse_frame(self, frame: bytes) -> bytes:
        """Parse and validate frame with ASCII hex encoding.

        Frame format: ~[HEX_HEADER][HEX_INFO][HEX_CHECKSUM]\r

        CRITICAL: Entire frame is ASCII hex encoded!
        - Header (VER, ADDR, CID1, CID2, LEN): ASCII hex (12 chars)
        - Info payload: ASCII hex (decoded to bytes)
        - Checksum: ASCII hex (4 chars)

        Args:
            frame: Complete frame bytes

        Returns:
            Info payload decoded from ASCII hex to bytes

        Raises:
            ValueError: If frame format or checksum invalid
        """
        # Validate frame markers
        if frame[0] != ord('~'):
            raise ValueError(f"Invalid frame start marker: {frame[0]:#x}")
        if frame[-1] != ord('\r'):
            raise ValueError(f"Invalid frame end marker: {frame[-1]:#x}")

        # Extract content (exclude ~ and \r markers)
        content = frame[1:-1]

        if len(content) < 16:  # Minimum: 12 hex header + 4 hex checksum
            raise ValueError(f"Frame too short: {len(content)} bytes")

        # Extract ASCII hex header (first 12 chars = VER(2)+ADDR(2)+CID1(2)+CID2(2)+LEN(4))
        ascii_header = content[:12]
        # Extract ASCII hex checksum (last 4 chars)
        ascii_checksum = content[-4:]
        # Everything between header and checksum is ASCII hex info
        ascii_info = content[12:-4]

        # Validate checksum on (ASCII header + ASCII hex info)
        checksum_data = ascii_header + ascii_info
        expected_checksum = self._calculate_checksum_ascii(checksum_data)

        try:
            received_checksum = int(ascii_checksum.decode('ascii'), 16)
        except (ValueError, UnicodeDecodeError) as err:
            raise ValueError(f"Invalid checksum encoding: {err}") from err

        if received_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch: received={received_checksum:04x} "
                f"expected={expected_checksum:04x}"
            )

        # Decode header to extract info length
        try:
            header_binary = bytes.fromhex(ascii_header.decode('ascii'))
        except (ValueError, UnicodeDecodeError) as err:
            raise ValueError(f"Invalid header encoding: {err}") from err

        if len(header_binary) != 6:
            raise ValueError(f"Invalid header length: {len(header_binary)} bytes (expected 6)")

        # Check for error responses
        response_ver = header_binary[0]
        response_cid2 = header_binary[3]

        # CID2=0x02 or 0x03 indicates error/rejection from BMS
        # CID2=0x00 appears to be success code for SOK BMS
        if response_cid2 in (0x02, 0x03):
            # Check for variant mismatch
            # Note: SOK BMS responds with VER=0x25 even though requests use VER=0x20
            if response_ver == 0x25 and self.variant == VARIANT_STANDARD:
                raise ValueError(
                    "BMS variant mismatch: BMS reports SOK variant (0x25) but "
                    "integration configured for standard variant. "
                    "Please reconfigure integration and select 'SOK' variant."
                )
            elif response_ver == 0x20 and self.variant == VARIANT_SOK:
                raise ValueError(
                    "BMS variant mismatch: BMS reports standard variant (0x20) but "
                    "integration configured for SOK variant. "
                    "Please reconfigure integration and select 'Standard' variant."
                )
            else:
                raise ValueError(
                    f"BMS returned error response (CID2=0x{response_cid2:02x}, VER=0x{response_ver:02x}). "
                    f"Command may not be supported or parameters invalid."
                )

        # Decode ASCII hex info to bytes
        if len(ascii_info) > 0:
            try:
                decoded_info = bytes.fromhex(ascii_info.decode('ascii'))
            except (ValueError, UnicodeDecodeError) as err:
                raise ValueError(f"Failed to decode info as hex: {ascii_info}") from err
        else:
            decoded_info = b""

        # Validate info length matches decoded info
        info_len = self._decode_info_length(header_binary[4:6])  # LEN is bytes 4-5 of header

        if len(decoded_info) != info_len:
            _LOGGER.debug(
                "Info length mismatch: header says %d, got %d bytes after decoding. ASCII: %s",
                info_len,
                len(decoded_info),
                ascii_info.decode('ascii') if ascii_info else "(empty)"
            )

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Parsed info payload: %s", decoded_info.hex() if decoded_info else "(empty)")

        return decoded_info

    async def get_pack_count(self) -> int:
        """Query battery pack count (CID2 0x90).

        Returns:
            Number of battery packs

        Raises:
            ValueError: If response is empty or invalid
        """
        frame = self._build_frame(self.CMD_PACK_COUNT)
        response = await self._send_frame(frame)

        if len(response) < 1:
            raise ValueError("Empty response from BMS for pack count query")

        return response[0]

    async def get_version_info(self, dev_id: int = 1) -> str:
        """Retrieve firmware version (CID2 0xC1).

        Args:
            dev_id: Device/pack ID (1-based, default=1)

        Returns:
            Version string

        Raises:
            ValueError: If response is empty or invalid
        """
        # Device ID must be sent as ASCII hex string in info field (e.g., "01" for device 1)
        device_id_ascii = f"{dev_id:02X}".encode('ascii')
        frame = self._build_frame(self.CMD_VERSION_INFO, info=device_id_ascii)
        response = await self._send_frame(frame)

        if len(response) == 0:
            raise ValueError("Empty response from BMS for version info query")

        if self.variant == VARIANT_SOK:
            # SOK uses 20-character padded string
            return response[:20].decode('ascii').strip()
        else:
            # Standard uses null-terminated C string
            null_idx = response.find(b'\x00')
            if null_idx >= 0:
                return response[:null_idx].decode('ascii')
            return response.decode('ascii')

    async def get_barcode(self, dev_id: int = 1) -> str:
        """Get device barcode (CID2 0xC2).

        Args:
            dev_id: Device/pack ID (1-based, default=1)

        Returns:
            Barcode string

        Raises:
            ValueError: If response is empty or invalid
        """
        # Device ID must be sent as ASCII hex string in info field (e.g., "01" for device 1)
        device_id_ascii = f"{dev_id:02X}".encode('ascii')
        frame = self._build_frame(self.CMD_BARCODE, info=device_id_ascii)
        response = await self._send_frame(frame)

        if len(response) == 0:
            raise ValueError("Empty response from BMS for barcode query")

        return response[:15].decode('ascii').strip()

    async def get_alarm_info(self, dev_id: int = 1) -> dict[str, Any] | None:
        """Fetch alarm status (CID2 0x44).

        Args:
            dev_id: Device/pack ID (1-based, default=1)

        Returns:
            Dictionary with alarm data structure, or None if response too short

        Note:
            Response includes device ID as first byte which must be skipped.
            Minimum response length is 22 bytes for valid data.
            CRITICAL: Must use dev_id as address byte AND in info field!
        """
        device_id_ascii = f"{dev_id:02X}".encode('ascii')
        frame = self._build_frame(self.CMD_ALARM_INFO, info=device_id_ascii, address=dev_id)
        response = await self._send_frame(frame)

        # Check minimum response length (22 bytes minimum for valid alarm data)
        if len(response) < 22:
            _LOGGER.debug(
                "Alarm info response too short: got %d bytes, expected minimum 22. "
                "Command may not be supported.",
                len(response)
            )
            return None

        # Skip first byte (device ID echo) before parsing
        return self._parse_alarm_response(response[1:])

    def _parse_alarm_response(self, data: bytes) -> dict[str, Any]:
        """Parse binary alarm data structure.

        Structure:
        - modules (1 byte)
        - cells (1 byte)
        - cell_states (cells bytes)
        - temps (6 bytes)
        - current_state (1 byte)
        - voltage_state (1 byte)
        - protect_sts1 (1 byte)
        - protect_sts2 (1 byte)
        - system_sts (1 byte)
        - fault_sts (1 byte)
        - alarm_sts (2 bytes)
        - component_sts (1 byte)

        Args:
            data: Response bytes

        Returns:
            Parsed alarm data
        """
        idx = 0
        modules = data[idx]
        idx += 1
        cells = data[idx]
        idx += 1

        cell_states = list(data[idx:idx + cells])
        idx += cells

        temps = list(data[idx:idx + 6])
        idx += 6

        return {
            "modules": modules,
            "cells": cells,
            "cell_states": cell_states,
            "temperatures": temps,
            "current_state": data[idx],
            "voltage_state": data[idx + 1],
            "protect_sts1": data[idx + 2],
            "protect_sts2": data[idx + 3],
            "system_sts": data[idx + 4],
            "fault_sts": data[idx + 5],
            "alarm_sts": int.from_bytes(data[idx + 6:idx + 8], 'big'),
            "component_sts": data[idx + 8] if len(data) > idx + 8 else 0,
        }

    async def get_analog_values(self, dev_id: int = 1) -> dict[str, Any] | None:
        """Fetch analog values (CID2 0x42).

        Args:
            dev_id: Device/pack ID (1-based, default=1)

        Returns:
            Dictionary with analog measurements, or None if response too short

        Note:
            Response includes device ID as first byte which must be skipped.
            Minimum response length is 45 bytes for valid data.
            CRITICAL: Must use dev_id as address byte AND in info field!
        """
        device_id_ascii = f"{dev_id:02X}".encode('ascii')
        frame = self._build_frame(self.CMD_ANALOG_VALUES, info=device_id_ascii, address=dev_id)
        response = await self._send_frame(frame)

        # Check minimum response length (45 bytes minimum for valid analog data)
        if len(response) < 45:
            _LOGGER.warning(
                "Analog values response too short: got %d bytes, expected minimum 45. "
                "Data: %s. Command may not be supported by this BMS variant.",
                len(response),
                response.hex()
            )
            return None

        # Log full response for diagnostic purposes
        _LOGGER.debug(
            "Raw analog response (%d bytes): %s",
            len(response),
            response.hex()
        )
        _LOGGER.debug(
            "First 10 bytes decoded: %s",
            [f"{b:02x}({b})" for b in response[:10]]
        )

        # Skip first byte (device ID echo) before parsing
        return self._parse_analog_response(response[1:])

    def _parse_analog_response(self, data: bytes) -> dict[str, Any]:
        """Parse binary analog data structure.

        Structure:
        - cells (1 byte)
        - cell_voltages (cells * 2 bytes, mV)
        - temp_count (1 byte)
        - cell_temps (temp_count * 2 bytes, Kelvin * 10)
        - current (2 bytes, 10mA units, signed)
        - voltage (2 bytes, 10mV units)
        - remaining_capacity (2 bytes, 10mAh units)
        - total_capacity (2 bytes, 10mAh units)
        - cycle_count (2 bytes)

        Args:
            data: Response bytes (device ID already stripped)

        Returns:
            Parsed analog data

        Note:
            Caller must validate minimum length before calling this method.
        """
        idx = 0

        # Cell count
        cells = data[idx]
        idx += 1

        # DIAGNOSTIC: Log raw data to troubleshoot cell count issue
        _LOGGER.debug(
            "Parsing analog response: cells=%d, data_length=%d, first_20_bytes=%s",
            cells,
            len(data),
            data[:20].hex()
        )

        # Validate cell count is reasonable (Pylontech/SOK packs typically have 8-24 cells)
        if cells > 24 or cells < 8:
            _LOGGER.warning(
                "Unusual cell count: %d cells. Expected 8-24 for typical pack. "
                "Data will be parsed as-is. First 40 bytes: %s",
                cells,
                data[:40].hex()
            )

        # Cell voltages (2 bytes each, in mV)
        cell_voltages = []
        for _ in range(cells):
            if idx + 2 > len(data):
                _LOGGER.error("Not enough data for cell %d voltage", len(cell_voltages))
                break
            voltage_mv = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
            cell_voltages.append(round(voltage_mv / 1000, 3))  # Convert to V
            idx += 2

        # Temperature count
        temp_count = data[idx]
        idx += 1

        _LOGGER.debug(
            "Temperature count at offset %d: %d (0x%02x). "
            "Previous 10 bytes: %s, Next 10 bytes: %s",
            idx - 1,
            temp_count,
            temp_count,
            data[max(0, idx-11):idx-1].hex(),
            data[idx:idx+10].hex()
        )

        # Validate temperature count
        if temp_count > 16:
            _LOGGER.warning(
                "Unusual temperature count: %d (0x%02x). Expected 2-8 for typical pack. "
                "Full context - Previous 20 bytes: %s, Next 20 bytes: %s",
                temp_count,
                temp_count,
                data[max(0, idx-21):idx-1].hex(),
                data[idx:min(len(data), idx+20)].hex()
            )

        # Cell temperatures (2 bytes each, Kelvin * 10)
        cell_temps = []
        for _ in range(temp_count):
            if idx + 2 > len(data):
                _LOGGER.error("Not enough data for temperature %d", len(cell_temps))
                break
            temp_k10 = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
            cell_temps.append(round((temp_k10 / 10) - 273.15, 2))  # Convert to Celsius
            idx += 2

        # Current (2 bytes, in 10mA units, signed)
        current_raw = int.from_bytes(data[idx:idx + 2], 'little', signed=True)  # BMS uses little-endian
        current = round(current_raw / 100, 2)  # Convert to A
        idx += 2

        # Voltage (2 bytes, in 10mV units)
        voltage_raw = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
        voltage = round(voltage_raw / 100, 2)  # Convert to V
        idx += 2

        # Remaining capacity (2 bytes, in 10mAh units)
        remaining_raw = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
        remaining = round(remaining_raw / 100, 2)  # Convert to Ah
        idx += 2

        # Total capacity (2 bytes, in 10mAh units)
        total_raw = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
        total = round(total_raw / 100, 2)  # Convert to Ah
        idx += 2

        # Cycle count (2 bytes)
        cycles = int.from_bytes(data[idx:idx + 2], 'little') if len(data) >= idx + 2 else 0  # BMS uses little-endian

        # Calculate derived values
        soc = int((remaining / total) * 100) if total > 0 else 0
        power = round(voltage * current, 2)

        _LOGGER.debug(
            "Parsed analog data - Cells: %d voltages (range: %.3f-%.3fV), "
            "Temps: %d sensors (range: %.1f-%.1fC), "
            "Pack: %.2fV/%.2fA, Capacity: %.2f/%.2f Ah, SOC: %d%%, Cycles: %d",
            len(cell_voltages),
            min(cell_voltages) if cell_voltages else 0,
            max(cell_voltages) if cell_voltages else 0,
            len(cell_temps),
            min(cell_temps) if cell_temps else 0,
            max(cell_temps) if cell_temps else 0,
            voltage,
            current,
            remaining,
            total,
            soc,
            cycles
        )

        return {
            "cell_voltages": cell_voltages,
            "cell_temps": cell_temps,
            "pack_current": current,
            "pack_voltage": voltage,
            "remaining_capacity": remaining,
            "total_capacity": total,
            "cycle_count": cycles,
            "power": power,
            "soc": soc,
        }

    def _decode_alarm_bits(self, alarms: dict[str, Any]) -> dict[str, bool]:
        """Decode alarm status bits to named boolean flags.

        Args:
            alarms: Raw alarm data from _parse_alarm_response

        Returns:
            Dictionary mapping alarm names to boolean states
        """
        def check_bit(value: int, bit: int) -> bool:
            """Check if specific bit is set."""
            return bool(value & (1 << bit))

        protect1 = alarms["protect_sts1"]
        protect2 = alarms["protect_sts2"]

        return {
            # Protection status 1 alarms
            "charge_ot_alarm": check_bit(protect1, 0),
            "charge_ut_alarm": check_bit(protect1, 1),
            "discharge_ot_alarm": check_bit(protect1, 2),
            "discharge_ut_alarm": check_bit(protect1, 3),
            "charge_oc_alarm": check_bit(protect1, 4),
            "discharge_oc_alarm": check_bit(protect1, 5),
            "cell_ov_alarm": check_bit(protect1, 6),
            "cell_uv_alarm": check_bit(protect1, 7),

            # Protection status 2 protection states
            "chg_ot_protection": check_bit(protect2, 0),
            "chg_ut_protection": check_bit(protect2, 1),
            "dsg_ot_protection": check_bit(protect2, 2),
            "dsg_ut_protection": check_bit(protect2, 3),
            "chg_oc_protection": check_bit(protect2, 4),
            "dsg_oc_protection": check_bit(protect2, 5),
            "cell_ov_protection": check_bit(protect2, 6),
            "cell_uv_protection": check_bit(protect2, 7),
        }

    async def get_device_info(self) -> DeviceInfo:
        """Retrieve device information.

        Returns:
            DeviceInfo with manufacturer, model, version, barcode, etc.
        """
        # Query pack count first (doesn't require device ID)
        try:
            pack_count = await self.get_pack_count()
        except Exception:
            pack_count = 1  # Default to 1 if query fails

        # Try to get version info and barcode
        # SOK BMS may not support these commands in the same way
        try:
            version = await self.get_version_info()
        except Exception as err:
            _LOGGER.warning("Could not retrieve version info: %s", err)
            version = "Unknown"

        try:
            barcode = await self.get_barcode()
        except Exception as err:
            _LOGGER.warning("Could not retrieve barcode: %s", err)
            barcode = f"{self.variant.upper()}_BMS"

        manufacturer = "SOK" if self.variant == VARIANT_SOK else "Pylontech"
        model = f"BMS ({self.variant})"

        return DeviceInfo(
            manufacturer=manufacturer,
            model=model,
            barcode=barcode,
            firmware_version=version,
            connection_type=ConnectionType.TCP_BINARY,
            variant=BatteryVariant.SOK_48V if self.variant == VARIANT_SOK else BatteryVariant.PYLONTECH_STANDARD,
            pack_count=pack_count,
        )

    async def get_battery_data(self, pack_id: int = 1) -> BatteryData:
        """Fetch current battery telemetry for a specific pack.

        Args:
            pack_id: Battery pack ID (1-based, default=1)

        Returns:
            BatteryData with all available measurements for this pack

        Raises:
            ValueError: If analog values cannot be retrieved (required data)
        """
        # Fetch analog data - required for battery telemetry
        analog = await self.get_analog_values(dev_id=pack_id)

        if analog is None:
            raise ValueError(
                f"Pack {pack_id} does not support analog values query or returned invalid response. "
                "This BMS variant may not be compatible with binary protocol."
            )

        # Fetch alarm data - optional, may not be supported
        alarms = await self.get_alarm_info(dev_id=pack_id)
        if alarms is not None:
            alarm_states = self._decode_alarm_bits(alarms)
        else:
            alarm_states = {}

        # Build temperature dictionary from cell temps
        temperatures = {
            f"cell_temp_{i}": temp
            for i, temp in enumerate(analog["cell_temps"])
        }

        # Calculate average temperature
        avg_temp = (
            round(sum(analog["cell_temps"]) / len(analog["cell_temps"]), 2)
            if analog["cell_temps"]
            else None
        )

        return BatteryData(
            # Pack-level measurements
            pack_voltage=analog["pack_voltage"],
            pack_current=analog["pack_current"],
            soc=analog["soc"],

            # Capacity
            remaining_capacity=analog["remaining_capacity"],
            total_capacity=analog["total_capacity"],

            # Power
            power=analog["power"],

            # Temperatures
            temperatures=temperatures,
            avg_temperature=avg_temp,

            # Cell-level data
            cell_voltages=analog["cell_voltages"],
            cell_temps=analog["cell_temps"],

            # Alarms and protection
            alarms=alarm_states,

            # Cycle count
            cycle_count=analog["cycle_count"],

            # States - not available in binary protocol
            base_state=None,
            volt_state=None,
            curr_state=None,
            temp_state=None,
            cell_volt_state=None,
            cell_temp_state=None,
            unit_volt_state=None,
            unit_temp_state=None,

            # Charge metrics - not directly available
            charge_ah=None,
            charge_ah_perc=None,
            charge_wh=None,
            charge_wh_perc=None,

            # Extremes - calculate from cell data
            cell_volt_low=min(analog["cell_voltages"]) if analog["cell_voltages"] else None,
            cell_volt_high=max(analog["cell_voltages"]) if analog["cell_voltages"] else None,
            cell_temp_low=min(analog["cell_temps"]) if analog["cell_temps"] else None,
            cell_temp_high=max(analog["cell_temps"]) if analog["cell_temps"] else None,

            # DC voltage - not available in binary protocol
            dc_voltage=None,
            bat_voltage=None,

            # Error code - not available in binary protocol
            error_code=None,
        )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<TCPBinaryProtocol host={self.host} port={self.port} variant={self.variant}>"
