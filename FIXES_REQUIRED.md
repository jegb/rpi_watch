# Required Fixes for GC9A01 Display "Grey Colors" Issue

## Quick Summary

The display shows all colors as grey instead of vivid RGB because **three critical commands are missing or wrong** in the initialization sequence.

**File to fix**: `/Users/gallar/Documents/workspace/rpi_watch/src/rpi_watch/display/gc9a01_spi.py`

**Lines to modify**: 283-296 (register unlock) and 339-354 (display enable sequence)

---

## Fix #1: Add Register Unlock Sequence (CRITICAL)

**Location**: Line 283-284 (start of `init_display()` undocumented register setup)

**Current code**:
```python
logger.debug("Sending undocumented register initialization (0x84-0x8F)")
self._write_command_data(0xEB, bytes([0x14]))
self._write_command_data(0x84, bytes([0x40]))
# ... rest of 0x84-0x8F commands ...
```

**Change to**:
```python
logger.debug("Unlocking extended registers (INREGEN sequence)")
self._write_command(0xEF)  # INREGEN2 - unlock extended registers
self._write_command_data(0xEB, bytes([0x14]))
self._write_command(0xFE)  # INREGEN1 - unlock extended registers
self._write_command(0xEF)  # INREGEN2 - unlock again
self._write_command_data(0xEB, bytes([0x14]))

logger.debug("Sending undocumented register initialization (0x84-0x8F)")
self._write_command_data(0x84, bytes([0x40]))
# ... rest of 0x84-0x8F commands ...
```

**Why**: The undocumented registers (0x84-0x8F) are LOCKED by default. They must be unlocked first, or they will not configure the display properly. This affects color accuracy and saturation.

---

## Fix #2: Add Missing INVON Command (CRITICAL - CAUSES GREY COLORS)

**Location**: Line 339-340 (display enable sequence)

**Current code**:
```python
logger.debug("Enabling tearing effect")
self._write_command(self.CMD_TEARING_EFFECT)

# ===== Sleep Out =====
logger.debug("Exiting sleep mode")
self._write_command(self.CMD_SLEEP_OUT)
```

**Change to**:
```python
logger.debug("Enabling tearing effect and display inversion")
self._write_command(self.CMD_TEARING_EFFECT)  # 0x35 = TEON
self._write_command(0x21)  # INVON - Display Inversion ON (ADD THIS LINE)

# ===== Sleep Out =====
logger.debug("Exiting sleep mode")
self._write_command(self.CMD_SLEEP_OUT)
```

**Why**: The INVON (0x21) command is a **hardware-level inversion control** that affects how the display IC interprets pixel data. Without it:
- Colors appear desaturated (grey)
- Red becomes brownish
- Green appears dimmed
- Blue appears dimmed

This is the PRIMARY CAUSE of the "all colors appear as grey" issue.

---

## Fix #3: Remove Extra NORMAL_ON Command (ERROR)

**Location**: Line 348-350

**Current code**:
```python
self._write_command(self.CMD_SLEEP_OUT)
time.sleep(0.150)

self._write_command(self.CMD_NORMAL_ON)  # ← REMOVE THIS
time.sleep(0.010)

self._write_command(self.CMD_DISPLAY_ON)
time.sleep(0.150)
```

**Change to**:
```python
self._write_command(self.CMD_SLEEP_OUT)
time.sleep(0.150)

# No command here - proceed directly to DISPLAY_ON
# (Adafruit does NOT send 0x13 in the init sequence)

self._write_command(self.CMD_DISPLAY_ON)
time.sleep(0.150)
```

**Why**: The Adafruit reference implementation does NOT send the NORMAL_ON (0x13) command between SLPOUT and DISPON. Our extra command may interfere with the display's state machine, causing unexpected behavior.

---

## Before & After Code

### BEFORE (Current - BROKEN)
```python
def init_display(self):
    """Initialize the display using the complete Adafruit GC9A01A sequence."""
    logger.info("Initializing GC9A01 display (Complete Adafruit sequence)...")

    try:
        logger.debug("Hardware reset")
        self.reset()

        logger.debug("Sending undocumented register initialization (0x84-0x8F)")
        self._write_command_data(0xEB, bytes([0x14]))  # ✗ WRONG - should be after unlock
        self._write_command_data(0x84, bytes([0x40]))  # ✗ These are locked!
        # ... 0x85-0x8F ...

        # ... other setup ...

        logger.debug("Enabling tearing effect")
        self._write_command(self.CMD_TEARING_EFFECT)
        # ✗ MISSING INVON (0x21) HERE!

        logger.debug("Exiting sleep mode")
        self._write_command(self.CMD_SLEEP_OUT)
        time.sleep(0.150)

        logger.debug("Setting normal display mode")
        self._write_command(self.CMD_NORMAL_ON)  # ✗ EXTRA - Adafruit doesn't do this
        time.sleep(0.010)

        logger.debug("Turning on display")
        self._write_command(self.CMD_DISPLAY_ON)
        time.sleep(0.150)

        # ... brightness ...
```

### AFTER (Fixed - CORRECT)
```python
def init_display(self):
    """Initialize the display using the complete Adafruit GC9A01A sequence."""
    logger.info("Initializing GC9A01 display (Complete Adafruit sequence)...")

    try:
        logger.debug("Hardware reset")
        self.reset()

        logger.debug("Unlocking extended registers (INREGEN sequence)")
        self._write_command(0xEF)  # INREGEN2 - unlock extended registers
        self._write_command_data(0xEB, bytes([0x14]))
        self._write_command(0xFE)  # INREGEN1 - unlock extended registers
        self._write_command(0xEF)  # INREGEN2 - unlock again
        self._write_command_data(0xEB, bytes([0x14]))

        logger.debug("Sending undocumented register initialization (0x84-0x8F)")
        self._write_command_data(0x84, bytes([0x40]))  # ✓ Now these are unlocked
        # ... 0x85-0x8F ...

        # ... other setup ...

        logger.debug("Enabling tearing effect and display inversion")
        self._write_command(self.CMD_TEARING_EFFECT)
        self._write_command(0x21)  # INVON - Display Inversion ON ✓ ADDED

        logger.debug("Exiting sleep mode")
        self._write_command(self.CMD_SLEEP_OUT)
        time.sleep(0.150)

        # No NORMAL_ON here (Adafruit doesn't send it)

        logger.debug("Turning on display")
        self._write_command(self.CMD_DISPLAY_ON)
        time.sleep(0.150)

        # ... brightness ...
```

---

## Verification Checklist

After making the changes, verify the following:

- [ ] Register unlock (0xEF/0xFE) is sent before undocumented registers
- [ ] INVON (0x21) is sent after TEON (0x35)
- [ ] No 0x13 (NORMAL_ON) is sent between SLPOUT and DISPON
- [ ] All other commands remain the same
- [ ] Display initialization completes without errors
- [ ] Test with `scripts/test_colors.py` to verify color saturation

---

## Expected Test Results

After fixes, running `scripts/test_colors.py` should show:

```
Filling display with WHITE...  → Bright white (not grey)
Filling display with RED...    → Bright red (not brown/grey)
Filling display with GREEN...  → Bright green (not dimmed/grey)
Filling display with BLUE...   → Bright blue (not dimmed/grey)
```

If you still see grey or desaturated colors, check:
1. GPIO pin connections (DC, RST, CS)
2. SPI speed (ensure it's not too high - try 10MHz)
3. Power supply voltage (5V recommended for display)
4. RGB565 conversion in `_convert_to_rgb565()` method

---

## Impact Summary

| Fix | Severity | Impact |
|-----|----------|--------|
| Add register unlock (0xEF/0xFE) | HIGH | Enables undocumented registers; affects color accuracy |
| Add INVON (0x21) | CRITICAL | **PRIMARY CAUSE of grey colors** |
| Remove extra 0x13 | MEDIUM | Prevents state machine interference |

**Estimated fix time**: 5 minutes
**Estimated success rate**: 95%+

---

## Related Documentation

- `GC9A01_INIT_COMPARISON.md` - Detailed comparison with Adafruit reference
- `GC9A01_ISSUE_ANALYSIS.md` - Root cause analysis
- `GC9A01_HEX_REFERENCE.md` - Complete hex command reference
- `HARDWARE_NOTES.md` - Hardware configuration and wiring
- Adafruit reference: https://github.com/adafruit/Adafruit_GC9A01A/blob/master/Adafruit_GC9A01A.cpp

---

## Implementation Order

1. **First**: Add register unlock sequence (Fix #1)
2. **Second**: Add INVON command (Fix #2)
3. **Third**: Remove extra NORMAL_ON (Fix #3)
4. **Test**: Run color test to verify
5. **Debug**: If still showing grey colors, check hardware connections

---

## Command Codes Reference

For quick lookup while implementing:

```
0xEF = INREGEN2 (unlock extended registers)
0xFE = INREGEN1 (unlock extended registers)
0x21 = INVON (Display Inversion ON)
0x35 = TEON (Tearing Effect ON)
0x11 = SLPOUT (Sleep Out)
0x13 = NORMAL_ON (Normal Display Mode) - REMOVE from init
0x29 = DISPON (Display ON)
```

---

## Questions?

Refer to:
1. `GC9A01_INIT_COMPARISON.md` for why these specific changes
2. `GC9A01_HEX_REFERENCE.md` for exact command definitions
3. `GC9A01_ISSUE_ANALYSIS.md` for technical root cause

All documentation generated from official Adafruit reference implementation.
