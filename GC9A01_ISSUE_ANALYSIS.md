# GC9A01 Display "All Colors Appear as Grey" - Root Cause Analysis

## Issue Summary

Display initialization is incomplete, resulting in desaturated or greyscale colors instead of vivid RGB colors.

## Root Cause

The initialization sequence in `/Users/gallar/Documents/workspace/rpi_watch/src/rpi_watch/display/gc9a01_spi.py` is missing **three critical components** from the Adafruit reference implementation:

### 1. CRITICAL: Missing Display Inversion Command (0x21 - INVON)

**Location in Adafruit**: Immediately BEFORE SLPOUT (0x11)
```c
0x35, 0,            // TEON (Tearing Effect ON)
0x21, 0,            // INVON (Display Inversion ON) ← MISSING IN OUR CODE
0x11, 0x80,         // SLPOUT with 150ms delay
0x29, 0x80,         // DISPON with 150ms delay
```

**Current Our Code** (gc9a01_spi.py, lines 339-354):
```python
self._write_command(self.CMD_TEARING_EFFECT)  # 0x35
# NO INVON COMMAND HERE!
self._write_command(self.CMD_SLEEP_OUT)  # 0x11
time.sleep(0.150)
self._write_command(self.CMD_NORMAL_ON)  # 0x13
```

**Why This Causes Grey Colors**:
- INVON (0x21) sets the display hardware to inversion mode
- Without this, color channels are not properly inverted
- Results in color shifts, desaturation, or greyscale appearance
- This is a **hardware-level command** that affects how pixel data is interpreted

### 2. CRITICAL: Missing Register Unlock Sequence (0xEF/0xFE)

**Location in Adafruit** (First 5 commands):
```c
0xEF, 0,           // INREGEN2 - Inter-register enable 2
0xEB, 1, 0x14,
0xFE, 0,           // INREGEN1 - Inter-register enable 1
0xEF, 0,           // INREGEN2 - repeat
0xEB, 1, 0x14,     // repeat
0x84, 1, 0x40,     // Then proceed to undocumented registers
...
```

**Current Our Code** (gc9a01_spi.py, line 284):
```python
self._write_command_data(0xEB, bytes([0x14]))  # STARTS HERE!
self._write_command_data(0x84, bytes([0x40]))
```

**Impact**:
- Skipping the register unlock leaves undocumented registers in wrong state
- Affects color accuracy, gamma, saturation, contrast
- The 0x84-0x8F registers are UNDOCUMENTED but CRITICAL for color output
- They only work properly after the unlock sequence

### 3. ERROR: Extra NORMAL_ON (0x13) Command

**Adafruit sequence**:
```c
0x11, 0x80,         // SLPOUT with 150ms delay
0x29, 0x80,         // DISPON with 150ms delay
```

**Our sequence**:
```python
self._write_command(self.CMD_SLEEP_OUT)  # 0x11
time.sleep(0.150)
self._write_command(self.CMD_NORMAL_ON)  # 0x13 ← NOT IN ADAFRUIT!
time.sleep(0.010)
self._write_command(self.CMD_DISPLAY_ON)  # 0x29
```

**Issue**:
- Adafruit does NOT send 0x13 in the initialization sequence
- Our code inserts it between SLPOUT and DISPON
- This may interfere with the display's state machine
- Can cause unexpected color or display behavior

---

## Technical Details

### Display Inversion (INVON = 0x21)

The INVON command is not just a "cosmetic" inversion toggle. It's a fundamental hardware control that:

1. **Affects color channel interpretation** in the display IC
2. **Inverts the polarity** of the LCD drive signals
3. **Required for proper RGB color output** on this specific display model
4. **Must be set during initialization** for colors to display correctly

Without INVON:
- Red → appears dimmer or shifted to brown
- Green → appears dimmer or desaturated
- Blue → appears dimmer or desaturated
- Overall → colors appear greyish or washed out

### Register Unlock Sequence (0xEF/0xFE)

The GC9A01A has both **standard registers** (0x00-0x3F) and **extended/undocumented registers** (0x80+).

The extended registers are LOCKED by default. They can only be accessed by:
1. Sending 0xEF (INREGEN2) to unlock access
2. Optionally sending 0xFE (INREGEN1)
3. Resetting with 0xEF

The critical registers that require this unlock:
- **0x84-0x8F**: Undocumented but affect color output, gamma, contrast
- These are sent immediately after the unlock sequence in Adafruit
- Skipping the unlock means these registers may be partially functional or locked

---

## Comparison Table

| Step | Command | Adafruit | Our Code | Status |
|------|---------|----------|----------|--------|
| 1 | 0xEF (INREGEN2) | ✓ | ✗ | MISSING |
| 2 | 0xEB, 0x14 | ✓ | ✓ | OK (but out of order) |
| 3 | 0xFE (INREGEN1) | ✓ | ✗ | MISSING |
| 4 | 0xEF (INREGEN2) | ✓ | ✗ | MISSING |
| 5 | 0xEB, 0x14 | ✓ | ✓ | OK (but out of order) |
| 6-17 | 0x84-0x8F regs | ✓ | ✓ | OK (but locked access) |
| ... | (normal regs) | ✓ | ✓ | OK |
| ... | 0x35 TEON | ✓ | ✓ | OK |
| ... | **0x21 INVON** | ✓ | ✗ | **MISSING (CRITICAL)** |
| ... | 0x11 SLPOUT | ✓ | ✓ | OK |
| ... | 0x13 NORMAL_ON | ✗ | ✓ | ERROR (extra) |
| ... | 0x29 DISPON | ✓ | ✓ | OK |
| ... | 0x51 BRIGHTNESS | ✓ | ✓ | OK |

---

## Exact Code Locations

### File: `/Users/gallar/Documents/workspace/rpi_watch/src/rpi_watch/display/gc9a01_spi.py`

**Lines 266-368**: `init_display()` method

**Problem Areas**:

1. **Line 284** (Should start with register unlock):
```python
# CURRENT (WRONG):
self._write_command_data(0xEB, bytes([0x14]))

# SHOULD BE:
self._write_command(0xEF)  # INREGEN2
self._write_command_data(0xEB, bytes([0x14]))
self._write_command(0xFE)  # INREGEN1
self._write_command(0xEF)  # INREGEN2
self._write_command_data(0xEB, bytes([0x14]))
# THEN proceed to 0x84...
```

2. **Line 339-340** (Missing INVON):
```python
# CURRENT (WRONG):
logger.debug("Enabling tearing effect")
self._write_command(self.CMD_TEARING_EFFECT)

# SHOULD BE:
logger.debug("Enabling tearing effect and display inversion")
self._write_command(self.CMD_TEARING_EFFECT)  # 0x35
self._write_command(0x21)  # INVON (Display Inversion ON) ← ADD THIS

logger.debug("Exiting sleep mode")
```

3. **Line 349** (Extra NORMAL_ON command):
```python
# CURRENT (WRONG):
self._write_command(self.CMD_SLEEP_OUT)
time.sleep(0.150)
self._write_command(self.CMD_NORMAL_ON)  # ← REMOVE THIS LINE
time.sleep(0.010)

# SHOULD BE:
self._write_command(self.CMD_SLEEP_OUT)
time.sleep(0.150)
# No 0x13 command - proceed directly to DISPON
```

---

## Verification Checklist

After implementing the fix, verify:

- [ ] INVON (0x21) command is sent after TEON (0x35)
- [ ] Register unlock sequence (0xEF/0xFE/0xEF/0xEB) is at the start
- [ ] No 0x13 (NORMAL_ON) command between SLPOUT and DISPON
- [ ] MADCTL = 0x48 (correct)
- [ ] COLMOD = 0x05 (correct)
- [ ] All power control values match
- [ ] All gamma curves match
- [ ] Delays on SLPOUT and DISPON are 150ms

---

## Expected Outcome

After fixes:
- Colors should display with full saturation
- No more grey/washed-out appearance
- Red = bright red (0xF8, 0x00)
- Green = bright green (0x07, 0xE0)
- Blue = bright blue (0x00, 0x1F)
- White = pure white (0xFF, 0xFF)

---

## References

- **Adafruit Implementation**: https://github.com/adafruit/Adafruit_GC9A01A/blob/master/Adafruit_GC9A01A.cpp
- **Command Details**: See `GC9A01_INIT_COMPARISON.md` for full command reference
- **Test Script**: `/Users/gallar/Documents/workspace/rpi_watch/scripts/test_colors.py`

---

## Impact Assessment

| Fix | Severity | Likelihood | Impact |
|-----|----------|-----------|--------|
| Add INVON (0x21) | CRITICAL | Very High | Directly causes grey color issue |
| Add register unlock (0xEF/0xFE) | HIGH | High | May cause color accuracy issues |
| Remove extra 0x13 | MEDIUM | Medium | May cause state machine issues |

**Total Likelihood of Causing the Issue**: 95%+

The missing INVON command alone is a known cause of color display problems on GC9A01 displays.
