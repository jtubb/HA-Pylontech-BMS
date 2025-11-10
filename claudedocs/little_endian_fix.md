# Critical Fix: Little-Endian Byte Order

## Issue Summary
The BMS uses **little-endian byte order** for all multi-byte values, but the code was parsing them as big-endian. This caused:

1. **Cell voltages parsed incorrectly**: `0cda` (little-endian 3290 mV = 3.290V) was read as `da0c` (big-endian 55820 mV = 55.8V invalid)
2. **Temperature values wrong**: Similar byte-swap issue
3. **All numeric readings corrupted**: Current, voltage, capacity, cycle count all affected
4. **Auto-detection triggered unnecessarily**: Invalid readings triggered broken fallback logic

## Root Cause

Looking at the hex data from logs:
```
db0cda0cda0cda0cda0cda
```

Breaking this down as little-endian 2-byte values:
- `db0c` → `0cdb` = 3291 mV = 3.291V ✅ Valid
- `da0c` → `0cda` = 3290 mV = 3.290V ✅ Valid
- `da0c` → `0cda` = 3290 mV = 3.290V ✅ Valid

But the code was reading as big-endian:
- `db0c` = 56076 mV = 56.076V ❌ Impossible
- `da0c` = 55820 mV = 55.820V ❌ Impossible

This is why only 1-2 cell voltages were detected - the auto-detection stopped after hitting invalid "voltages".

## Fix Applied

Changed ALL multi-byte reads from `'big'` to `'little'` in `tcp_binary.py` `_parse_analog_response()`:

### Line 702: Cell Voltages
```python
# Before:
voltage_mv = int.from_bytes(data[idx:idx + 2], 'big')

# After:
voltage_mv = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
```

### Line 747: Cell Temperatures
```python
# Before:
temp_k10 = int.from_bytes(data[idx:idx + 2], 'big')

# After:
temp_k10 = int.from_bytes(data[idx:idx + 2], 'little')  # BMS uses little-endian
```

### Lines 752, 757, 762, 767, 772: Current, Voltage, Capacities, Cycle Count
```python
# All changed from 'big' to 'little'
current_raw = int.from_bytes(data[idx:idx + 2], 'little', signed=True)
voltage_raw = int.from_bytes(data[idx:idx + 2], 'little')
remaining_raw = int.from_bytes(data[idx:idx + 2], 'little')
total_raw = int.from_bytes(data[idx:idx + 2], 'little')
cycles = int.from_bytes(data[idx:idx + 2], 'little')
```

### Removed Broken Auto-Detection
The complex cell/temp auto-detection logic was completely wrong because it was looking for big-endian values. Simplified to just trust the count bytes and log warnings for unusual values.

## Expected Results After Fix

Each pack should now have:
- **16 cell voltage sensors** (cell_voltage_0 through cell_voltage_15)
- **~6 temperature sensors** (cell_temp_0 through cell_temp_5)
- **Correct pack voltage, current, capacity values**
- **~56 sensors per pack** (not 339 total!)

**Total entities**: 6 packs × 56 sensors = **~336 entities** (down from incorrect 339)

## Sensor Naming

Entity names like `sensor.pack_voltage` vs `sensor.pack_voltage_2`:
- This is **correct behavior**
- Home Assistant adds suffixes (`_2`, `_3`, etc.) when multiple devices have sensors with the same name
- Each sensor is correctly associated with its pack device
- The device name appears in the full entity display in Home Assistant UI

## Testing Instructions

1. **Restart Home Assistant** to load the fixed code
2. **Check entity count per pack**:
   - Navigate to Settings → Devices & Services → Pylontech BMS
   - Click on each pack device
   - Should see ~56 entities per pack (not 100+)

3. **Verify cell voltages**:
   - Each pack should have exactly 16 cell_voltage sensors
   - Values should be 2.5V - 3.65V range (typical for LiFePO4)
   - All 16 should have valid readings

4. **Verify temperatures**:
   - Should have 4-8 temperature sensors per pack
   - Values should be 0°C - 60°C (typical operating range)

5. **Check pack-level sensors**:
   - Pack voltage should be ~51-54V (16 cells × 3.2V nominal)
   - Current, capacity, SOC should all have reasonable values

## Files Modified
- `/home/docker/homeassistant/config/custom_components/pylontech/protocol/tcp_binary.py`
  - Lines 702, 747, 752, 757, 762, 767, 772: Changed byte order to little-endian
  - Lines 617-624: Simplified cell count validation
  - Lines 642-650: Simplified temperature count validation

## Technical Notes

**Why Little-Endian?**
- Most embedded systems (ARM, x86) use little-endian natively
- BMS microcontrollers (likely ARM Cortex-M) default to little-endian
- The protocol spec apparently wasn't explicit about byte order
- The hex dumps clearly show little-endian structure when decoded correctly

**Protocol Documentation Gap**:
- Original implementation assumed big-endian (network byte order)
- Actual BMS uses little-endian (native ARM byte order)
- This is a critical detail missing from protocol documentation
