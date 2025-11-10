# Cell Count Bug Analysis and Fix (Updated)

## Issue Report
Integration was detecting 217 battery cells per pack when the BMS actually reports 16 cells. Additionally:
- Same issue with temperature sensors (217 instead of 6)
- Only 1-2 cell voltages being correctly parsed
- Indicates serious protocol structure mismatch

## Root Cause Analysis

### Problem Location
`protocol/tcp_binary.py:595` - `_parse_analog_response()` method

### The Bug
The protocol parser reads the first byte of the analog response data as the cell count:
```python
cells = data[idx]  # Line 595
```

If this byte happens to contain value 0xD9 (217 decimal), the code attempts to parse 217 cell voltages. The parser then quickly fails because it hits non-voltage data after 1-2 valid readings.

### Why This Happens
The BMS response has **additional header/status bytes** before the actual cell data starts:

```
[Device ID] [Unknown header bytes...] [0xD9=217?] [More bytes...] [Actual cell count=16] [Cell voltages...]
```

The current code assumes the structure is:
```
[Device ID] [Cell count] [Cell voltages...] [Temp count] [Temps...]
```

But the actual structure likely has status/flag bytes before the cell data section.

## Fix Applied

### 1. Enhanced Diagnostic Logging (Lines 566-575, 598-615)
Added comprehensive debug logging:
- Full raw response in hex (all bytes)
- First 10 bytes decoded with both hex and decimal values
- Detected cell count and position
- First 60 bytes of data being parsed

This captures the exact protocol structure for analysis.

### 2. Intelligent Cell Data Detection (Lines 617-694)

**Strategy 1: Structure-Based Search**
- Scans first 10 bytes looking for a reasonable cell count (8-24)
- When found, validates that it's followed by correct number of valid voltages
- Valid voltage range: 2000-4500 mV (2.0-4.5V for LiFePO4/Li-ion)
- If structure matches perfectly, adjusts data pointer to correct offset

**Strategy 2: Voltage Sequence Search (Fallback)**
- If no valid structure found, scans for longest sequence of valid voltages
- Tests multiple starting offsets (1-10 bytes)
- Uses the offset that produces the most consecutive valid voltage readings
- Requires minimum 8 cells to accept as valid

**Default Fallback**
- If both strategies fail, defaults to 16 cells at offset 1
- Logs error requesting diagnostic data

### 3. Temperature Count Validation (Lines 706-739)
Applied same validation approach to temperature sensors:
- Validates temp count is reasonable (1-32 sensors)
- Auto-detects by scanning for valid temperature values
- Valid range: 2530-3530 in Kelvin*10 (-20°C to 80°C)
- Counts consecutive valid temperature readings

### 4. Bounds Checking (Lines 698-704, 743-749)
Added protection against buffer overruns:
```python
if idx + 2 > len(data):
    _LOGGER.error("Not enough data for cell/temp %d", count)
    break
```

## Testing Required

After restarting Home Assistant, check the logs for diagnostic output:

### Success Indicators

1. **Structure Detection Success**:
   ```
   INFO: Found cell data at offset X: 16 cells with valid voltages
   ```
   Indicates Strategy 1 successfully found the correct structure.

2. **Voltage Sequence Detection**:
   ```
   INFO: Auto-detected 16 cells starting at offset X
   ```
   Indicates Strategy 2 found cells by scanning voltage sequences.

3. **Temperature Detection**:
   ```
   INFO: Auto-detected 6 temperature sensors
   ```
   Indicates temperature parsing also succeeded.

### Diagnostic Data to Capture

If issues persist, these logs are critical for protocol analysis:

```
DEBUG: Raw analog response (XX bytes): [full hex]
DEBUG: First 10 bytes decoded: [hex and decimal values]
WARNING: Unreasonable cell count detected: 217 cells. Raw data (first 60 bytes): [hex]
```

## Expected Outcome

Each pack should now have:
- **16 cell voltage sensors** (`cell_voltage_0` through `cell_voltage_15`)
- **6 temperature sensors** (`cell_temp_0` through `cell_temp_5`)
- No incorrect 217-sensor entities

## Next Steps

### 1. Restart Home Assistant
```bash
# Developer Tools → Restart
# OR via CLI:
ha core restart
```

### 2. Enable Debug Logging (if needed)
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.pylontech: debug
```

### 3. Check Integration Logs
```bash
# View logs:
cat /config/home-assistant.log | grep pylontech

# Look for:
# - "Raw analog response" - shows exact protocol bytes
# - "Found cell data at offset" - shows successful detection
# - "Auto-detected X cells" - shows fallback detection
```

### 4. Report Results
If the fix works, you should see 16 cells per pack.

If issues persist, please share:
- The "Raw analog response" hex dump
- The "First 10 bytes decoded" output
- Any warning/error messages

## Protocol Investigation Needed

If the auto-detection still fails, we need to:
1. Capture the exact raw response bytes from your BMS
2. Determine if additional bytes need to be skipped before the cell count
3. Check if SOK variant uses a different protocol structure than Pylontech
4. Potentially add variant-specific parsing logic

## File Modified
- `/home/docker/homeassistant/config/custom_components/pylontech/protocol/tcp_binary.py` (Lines 598-642)
