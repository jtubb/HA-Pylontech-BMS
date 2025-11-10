# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Home Assistant custom component for integrating Pylontech high voltage Battery Management Systems (BMS). The integration communicates with Pylontech BMS devices over TCP console connections to retrieve battery status, voltage, current, temperature, and charge information.

## Architecture

### Core Communication Flow

1. **Entry Point** (`__init__.py`): Handles Home Assistant integration setup
   - Creates `PylontechBMS` instance with host/port from config
   - Validates connection during setup by running `info()` command
   - Instantiates `PylontechUpdateCoordinator` with initial device info
   - Coordinator performs sensor detection before first refresh

2. **BMS Protocol Layer** (`pylontech.py`): Low-level TCP console interface
   - `PylontechBMS`: Manages async TCP connection (asyncio StreamReader/Writer)
   - Sends console commands (`pwr`, `unit`, `info`, `bat`) over telnet-like protocol
   - Parses ASCII responses into structured command objects
   - Each command class (`PwrCommand`, `UnitCommand`, `InfoCommand`, `BatCommand`) parses specific response formats
   - Sensor types (`Voltage`, `Current`, `Temp`, etc.) handle unit conversions (mV→V, mA→A, etc.)

3. **Data Coordination** (`coordinator.py`): Manages polling and device structure
   - `PylontechUpdateCoordinator`: Orchestrates updates every 30 seconds (SCAN_INTERVAL)
   - Runs `detect_sensors()` once during setup to discover available sensors from BMS
   - Update cycle: connect → fetch `pwr` → fetch `unit` → disconnect
   - Creates device hierarchy: main BMS device + individual BMU (Battery Management Unit) devices
   - Flattens sensor data: pack-level sensors + per-BMU sensors (suffixed with `_bmu_0`, `_bmu_1`, etc.)

4. **Sensor Entities** (`sensor.py`): Home Assistant sensor creation
   - Dynamically creates sensors based on `detect_sensors()` results
   - Maps Pylontech sensor units to Home Assistant device classes (V→VOLTAGE, A→CURRENT, C→TEMPERATURE, etc.)
   - Sensors attached to either main BMS device or individual BMU devices

### Device Hierarchy

- **Main BMS Device**: Identified by module barcode from `info` command
  - Pack-level sensors (average temp, total voltage/current, charge percentages, states)
- **BMU Devices**: Individual battery modules, one per detected BMU
  - Per-module sensors (voltage, current, temp, cell voltages/temps, charge state)
  - Linked to main BMS via `via_device` for proper device relationships

### Protocol Details

The BMS uses an ASCII console protocol over TCP (default port 1234):
- Commands are sent with `\r` line ending
- Responses end with `pylon>` prompt
- Mix of LF and CR+LF line endings in responses (handled by byte-by-byte parsing in `_exec_cmd`)
- Read in 120-byte chunks (larger reads fail on Linux)
- Commands validated by checking first two response lines match command echo and `@` separator

## Development Commands

This is a Home Assistant custom component. There are no build, test, or lint commands in this repository - development happens within Home Assistant's environment.

To reload the integration after code changes:
1. Restart Home Assistant or use Developer Tools → YAML → Reload custom integrations
2. Check Home Assistant logs for any errors: `homeassistant.config/home-assistant.log`

## Configuration

- **Config Flow** (`config_flow.py`): UI-based setup requiring host and port
- **Connection Validation**: Attempts `info` command during config to verify connectivity
- **Unique ID**: Uses module barcode from BMS to prevent duplicate integrations

## Key Constraints

- **Connection Management**: Each coordinator update opens/closes connection (no persistent connection)
- **Timeout Handling**: 2-second timeouts on read operations, 5-second timeout on initial connection
- **Sensor Discovery**: Dynamic - available sensors depend on BMS response format and detected BMUs
- **No External Dependencies**: Integration uses pure asyncio, no external libraries (see manifest.json requirements: [])
