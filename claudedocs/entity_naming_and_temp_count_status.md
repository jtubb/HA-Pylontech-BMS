# Entity Naming & Temperature Count Issues - Status

## Issue 1: Entity IDs Don't Include Device Name

### Problem
User reported entity IDs like `sensor.pack_voltage` without device name prefix.
Expected: `sensor.battery_pack_1_pack_voltage` (with device name "Battery")

### Solution (UPDATED)
**Initial approach was wrong** - setting `has_entity_name=False` broke device grouping!

**Correct approach** (sensor.py lines 253-264):
- Set `_attr_device_info` to associate entity with pack device ✓
- Do NOT override `_attr_name` - use the description.name directly ✓
- Do NOT set `has_entity_name=False` - use default (True) ✓

This allows Home Assistant's default behavior:
1. Entities are grouped under their pack devices (device hierarchy maintained)
2. Entity IDs auto-generated from device name + sensor name
3. Each pack is a separate device in the device registry

### Expected Result
For manufacturer="SOK", device_name="Battery", pack_id=1, sensor="Pack Voltage":
- Device name: "SOK Battery Pack 1" (from coordinator.py:263)
- Entity name: "Pack Voltage" (from description.name)
- Entity ID: `sensor.sok_battery_pack_1_pack_voltage` (auto-generated)

### Device Hierarchy
```
Device: SOK Battery Pack 1
├── sensor.sok_battery_pack_1_pack_voltage
├── sensor.sok_battery_pack_1_pack_current
├── sensor.sok_battery_pack_1_soc
├── sensor.sok_battery_pack_1_cell_voltage_0
└── ... (~56 sensors per pack)

Device: SOK Battery Pack 2
├── sensor.sok_battery_pack_2_pack_voltage
└── ... (~56 sensors per pack)
```

### Testing Required
User needs to:
1. Restart Home Assistant
2. Check if new entity IDs include device name
3. Report back entity IDs from entity registry

---

## Issue 2: 33 Temperature Sensors Instead of 6

### Problem
User's logs show sensors `temp_cell_temp_0` through `temp_cell_temp_32` (33 total).
Expected: 6 temperature sensors based on BMS data.

### Investigation Status

#### Possible Causes:

1. **Temperature count byte reads as 33 (0x21) instead of 6**
   - Offset calculation after cell voltages might be wrong
   - Could be reading voltage data as temperature count
   - Little-endian fix may not have fully resolved parsing

2. **Protocol structure mismatch**
   - May be extra bytes between cell voltages and temperature count
   - SOK BMS variant might have different structure than Pylontech

3. **Coordinator duplication**
   - Less likely but possible: temperatures being added twice somehow
   - Would explain `temp_cell_temp_X` double-prefixing

#### Diagnostic Logging Added

Enhanced logging in `tcp_binary.py` to capture:

**Cell Count** (line 610-615):
```python
_LOGGER.debug(
    "Parsing analog response: cells=%d, data_length=%d, first_20_bytes=%s",
    cells, len(data), data[:20].hex()
)
```

**Temperature Count** (line 640-659):
```python
_LOGGER.debug(
    "Temperature count at offset %d: %d (0x%02x). "
    "Previous 10 bytes: %s, Next 10 bytes: %s",
    idx - 1, temp_count, temp_count,
    data[max(0, idx-11):idx-1].hex(),
    data[idx:idx+10].hex()
)

# Plus WARNING if temp_count > 16 with 20 bytes context on each side
```

**Parsing Summary** (line 698-714):
```python
_LOGGER.debug(
    "Parsed analog data - Cells: %d voltages (range: %.3f-%.3fV), "
    "Temps: %d sensors (range: %.1f-%.1fC), "
    "Pack: %.2fV/%.2fA, Capacity: %.2f/%.2f Ah, SOC: %d%%, Cycles: %d",
    len(cell_voltages), min/max voltages,
    len(cell_temps), min/max temps,
    voltage, current, remaining, total, soc, cycles
)
```

### What We'll Learn From Logs

1. **If temp_count reads as 33**:
   - We'll see hex context showing what's at that byte position
   - Can compare with expected temperature count byte location
   - Will reveal if offset is wrong or structure is different

2. **If parsed temps are reasonable (6 temps, 0-60°C range)**:
   - Parsing is actually correct
   - Issue is in coordinator or sensor creation
   - Need to check why 33 sensors get created from 6 values

3. **If parsed temps are wrong (33 temps, absurd values)**:
   - Confirms protocol parsing issue
   - Hex context will show structure mismatch
   - May need to adjust offset or add padding bytes

### Next Steps

**User needs to**:
1. Restart Home Assistant with updated code
2. Check logs for the three debug messages above
3. Report back:
   - Cell count from "Parsing analog response"
   - Temperature count and hex context from "Temperature count at offset"
   - Parsing summary from "Parsed analog data"
   - Any WARNING messages

**Based on logs, we can**:
- Identify exact byte position of temperature count
- Verify if little-endian fix worked correctly
- Determine if structure differs from expected format
- Calculate correct offset if current one is wrong

---

## Files Modified

### sensor.py (lines 260-267)
Changed entity naming to include device name in entity_id

### tcp_binary.py (multiple locations)
Added comprehensive diagnostic logging:
- Line 610-615: Cell count logging
- Line 640-659: Temperature count with hex context
- Line 698-714: Complete parsing summary

### New Documentation
- `/claudedocs/diagnostic_logging_guide.md` - How to interpret logs
- `/claudedocs/entity_naming_and_temp_count_status.md` - This file

---

## Related Documentation

See also:
- `/claudedocs/little_endian_fix.md` - Previous byte order fix
- `/claudedocs/cell_count_bug_fix.md` - Initial 217-cell investigation
