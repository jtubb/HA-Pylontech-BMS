# Home Assistant - Pylontech BMS Integration

A Home Assistant custom component for monitoring Pylontech (and compatible) high-voltage Battery Management Systems (BMS) via TCP binary protocol.

## Features

- **Multi-Pack Support**: Creates separate devices for each battery pack with grouped entities
- **Per-Pack Sensor Detection**: Dynamically discovers available sensors for each pack
- **Comprehensive Monitoring**:
  - Cell voltages (individual cells)
  - Cell temperatures
  - Pack voltage, current, and power
  - State of Charge (SOC)
  - Remaining and total capacity
  - Cycle count
  - Alarm states
- **Customizable Device Names**: Configure custom base names for your battery devices
- **Little-Endian Protocol Support**: Correctly parses binary data from BMS hardware

## Supported Hardware

- Pylontech high-voltage BMS
- SOK batteries with compatible BMS
- Other manufacturers using similar binary protocol

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Pylontech BMS" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `pylontech` folder to `custom_components/` in your Home Assistant config directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **Pylontech BMS**
4. Enter your BMS connection details:
   - **Host**: IP address of your BMS
   - **Port**: TCP port (default: 1234)
   - **Device Name**: Custom base name for devices (default: "Battery")

## Device Structure

The integration creates one device per battery pack:

```
Device: SOK Battery Pack 1
├── Pack Voltage
├── Pack Current
├── State of Charge
├── Cell 0 Voltage
├── Cell 1 Voltage
├── ...
└── Cell Temperature sensors

Device: SOK Battery Pack 2
├── (Same sensor structure)
└── ...
```

## Sensor Examples

Each pack provides approximately 56 sensors (varies by BMS model):

- **Pack-level**: voltage, current, power, SOC, capacity
- **Cell voltages**: Individual cell readings (typically 16 cells)
- **Temperatures**: Cell and pack temperature sensors (typically 6 sensors)
- **States**: Base state, voltage state, current state, temperature state
- **Alarms**: Various alarm conditions
- **Cycle count**: Battery cycle counter

## Technical Details

### Protocol

This integration uses the Pylontech TCP binary protocol:
- Default port: 1234
- Binary protocol with ASCII hex encoding
- Little-endian byte order for multi-byte values
- Frame-based communication with CRC validation

### Architecture

- **Protocol Layer** (`protocol/tcp_binary.py`): Low-level BMS communication
- **Coordinator** (`coordinator.py`): Data polling and device management
- **Sensors** (`sensor.py`): Home Assistant entity creation
- **Models** (`models.py`): Data structures for battery information

## Troubleshooting

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.pylontech: debug
```

### Common Issues

**Entities not grouped under devices**:
- Delete the integration and re-add it to recreate device structure

**Wrong number of sensors**:
- Check debug logs for parsing information
- Verify BMS protocol compatibility

**Connection issues**:
- Verify IP address and port
- Check network connectivity to BMS
- Ensure only one client connects to BMS at a time

## Development

See `claudedocs/` directory for detailed technical documentation:
- `little_endian_fix.md`: Byte order correction details
- `cell_count_bug_fix.md`: Sensor detection improvements
- `diagnostic_logging_guide.md`: Troubleshooting guide

## Credits

Original protocol implementation based on Pylontech communication specifications.
Multi-pack architecture and little-endian fixes contributed by Claude Code.

## License

This project is provided as-is for Home Assistant integration purposes.
