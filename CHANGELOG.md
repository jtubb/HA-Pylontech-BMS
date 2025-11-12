# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-11-12

### Added
- Multi-pack support with separate devices per pack
- Per-pack sensor detection and entity creation
- Binary protocol support for enhanced data access
- SOK battery variant support
- Customizable device names via configuration
- Console protocol support for v3+ firmware
- Dynamic sensor discovery based on BMS capabilities
- Comprehensive status sensors (protect, system, fault, alarm)
- Temperature sensors with proper naming (cells 1-4, 5-8, etc.)

### Fixed
- Byte order correction for binary protocol (little-endian)
- Two-byte prefix handling in analog data responses
- Cell count and temperature sensor parsing
- Entity naming and suggested_object_id generation
- Device grouping and hierarchy

### Changed
- Removed verbose debugging logs for production use
- Improved error handling and connection validation
- Enhanced sensor precision for voltage readings (3 decimals)
- Optimized polling intervals and connection management

## [1.0.0] - Initial Release

### Added
- Initial implementation of Pylontech BMS integration
- TCP console protocol support
- Basic sensor entities
- Config flow for setup
