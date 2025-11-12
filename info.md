# Pylontech BMS Integration

Monitor your Pylontech high-voltage Battery Management System directly in Home Assistant.

## Features

✅ **Multi-Pack Support** - Separate device for each battery pack
✅ **Comprehensive Monitoring** - Voltage, current, temperature, SOC, capacity
✅ **Cell-Level Details** - Individual cell voltages and temperatures
✅ **Dual Protocol Support** - Console and Binary protocols
✅ **SOK Battery Compatible** - Works with SOK 48V batteries
✅ **Auto-Discovery** - Dynamically detects available sensors
✅ **Custom Device Names** - Personalize your battery device names

## Supported Hardware

- Pylontech US2000, US3000, US5000
- SOK 48V batteries with compatible BMS
- Other Pylontech-compatible BMS systems

## Quick Start

1. Add this repository in HACS
2. Install the integration
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Pylontech BMS"
5. Follow the setup wizard

## Protocol Selection

**Console Protocol (Port 1234)**
- Standard text-based protocol
- Firmware v3.0 and above
- Comprehensive status information

**Binary Protocol (Port 8234)**
- Frame-based protocol with enhanced data
- Firmware v2.0 and v2.5
- Additional cell-level sensors
- SOK battery support

## Need Help?

- 📖 [Full Documentation](https://github.com/jtubb/HA-Pylontech-BMS)
- 🐛 [Report Issues](https://github.com/jtubb/HA-Pylontech-BMS/issues)
