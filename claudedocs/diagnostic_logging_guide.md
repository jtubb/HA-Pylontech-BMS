# Diagnostic Logging Guide

## Enhanced Logging Added

I've added comprehensive diagnostic logging to help troubleshoot the temperature sensor count issue and verify correct protocol parsing.

## What to Look For

After restarting Home Assistant, check the logs for these messages:

### 1. Cell Count Validation
```
DEBUG: Parsing analog response: cells=16, data_length=XXX, first_20_bytes=...
```
**Expected**: `cells=16` (for your 16-cell packs)
**Problem**: If you see `cells=217` or other unexpected values

### 2. Temperature Count Detection
```
DEBUG: Temperature count at offset XX: 6 (0x06). Previous 10 bytes: ..., Next 10 bytes: ...
```
**Expected**: Temperature count should be ~6 (0x06)
**Problem**: If you see count=33 (0x21) or other unexpected values

If temperature count > 16, you'll also see:
```
WARNING: Unusual temperature count: 33 (0x21). Expected 2-8 for typical pack.
Full context - Previous 20 bytes: ..., Next 20 bytes: ...
```

### 3. Parsing Summary
```
DEBUG: Parsed analog data - Cells: 16 voltages (range: 3.250-3.350V),
Temps: 6 sensors (range: 15.0-25.0C),
Pack: 52.50V/-5.25A, Capacity: 45.00/50.00 Ah, SOC: 90%, Cycles: 123
```

**Expected values**:
- Cells: 16 voltages in range 2.5-3.65V (typical LiFePO4)
- Temps: 6 sensors in range 0-60°C (typical operating range)
- Pack voltage: ~51-54V (16 cells × 3.2V nominal)
- Current: Reasonable charge/discharge current
- SOC: 0-100%

**Problem indicators**:
- If Temps shows 33 sensors instead of 6
- If voltage ranges are wrong (>4V or <2V suggests parsing error)
- If temperature ranges are absurd (negative Celsius or >100°C)

## How to Enable Debug Logging

Add to your Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.pylontech: debug
```

Then restart Home Assistant.

## What the Logs Will Tell Us

### If Temperature Count is Wrong (e.g., 33 instead of 6):

1. **Byte value 0x21 (33 decimal)** at temperature count position means:
   - Either that's actually cell voltage data being misread as count
   - Or the offset calculation after cell voltages is wrong
   - Or there's an extra byte we're not accounting for

2. **Previous/Next bytes context** will show:
   - What comes before the temp count byte (should be last cell voltage bytes)
   - What comes after (should be first temperature value)
   - This helps identify if offset is wrong

### If Cell Voltages Look Wrong:

3. **Cell voltage ranges** outside 2.5-3.65V suggest:
   - Byte order still wrong (unlikely after little-endian fix)
   - Wrong offset for cell data start
   - Cell count byte itself is wrong

## Next Steps Based on Logs

**Scenario A: Cell count is correct (16) but temp count is wrong (33)**
- Offset calculation after cell voltages is wrong
- Need to check if there's a padding byte or different structure

**Scenario B: Cell count is wrong (217)**
- Need to go back to protocol structure analysis
- May need raw hex dump of full response to reverse-engineer

**Scenario C: Parsed values look reasonable but wrong sensor count**
- Issue might be in coordinator sensor creation logic
- Not a protocol parsing problem

## Reporting Back

Please share:
1. The "Parsing analog response" line (shows cell count)
2. The "Temperature count at offset" line (shows temp count and context)
3. The "Parsed analog data" summary line (shows final results)
4. Any WARNING messages about unusual counts

This will help pinpoint exactly where the protocol parsing goes wrong.
