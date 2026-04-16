# GC9A01A Initialization Sequence: Adafruit vs Our Implementation

## Executive Summary

**CRITICAL FINDING**: There are **3 key differences** between the Adafruit reference implementation and our `gc9a01_spi.py` that may cause the "all colors appear as grey" issue:

1. **INVON (Display Inversion) Command Missing** - Adafruit uses it, we don't
2. **Timing Delays on Critical Commands** - SLPOUT and DISPON need 150ms delays (marked with 0x80 bit)
3. **Potential Power Control Sequencing** - Order and timing of power commands may matter

---

## 1. Complete Adafruit initcmd[] Array (Authoritative Source)

### Raw Command Sequence with Exact Hex Values

```
static const uint8_t PROGMEM initcmd[] = {
  0xEF, 0,           // INREGEN2
  0xEB, 1, 0x14,
  0xFE, 0,           // INREGEN1
  0xEF, 0,           // INREGEN2
  0xEB, 1, 0x14,
  0x84, 1, 0x40,
  0x85, 1, 0xFF,
  0x86, 1, 0xFF,
  0x87, 1, 0xFF,
  0x88, 1, 0x0A,
  0x89, 1, 0x21,
  0x8A, 1, 0x00,
  0x8B, 1, 0x80,
  0x8C, 1, 0x01,
  0x8D, 1, 0x01,
  0x8E, 1, 0xFF,
  0x8F, 1, 0xFF,
  0xB6, 2, 0x00, 0x00,
  0x36, 1, 0x48,     // MADCTL = 0x48 (0x40|0x08 = MX|BGR)
  0x3A, 1, 0x05,     // COLMOD = 0x05 (RGB565)
  0x90, 4, 0x08, 0x08, 0x08, 0x08,
  0xBD, 1, 0x06,
  0xBC, 1, 0x00,
  0xFF, 3, 0x60, 0x01, 0x04,
  0xC3, 1, 0x13,     // POWER2
  0xC4, 1, 0x13,     // POWER3
  0xC9, 1, 0x22,     // POWER4
  0xBE, 1, 0x11,
  0xE1, 2, 0x10, 0x0E,
  0xDF, 3, 0x21, 0x0c, 0x02,
  0xF0, 6, 0x45, 0x09, 0x08, 0x08, 0x26, 0x2A,  // GAMMA1
  0xF1, 6, 0x43, 0x70, 0x72, 0x36, 0x37, 0x6F,  // GAMMA2
  0xF2, 6, 0x45, 0x09, 0x08, 0x08, 0x26, 0x2A,  // GAMMA3
  0xF3, 6, 0x43, 0x70, 0x72, 0x36, 0x37, 0x6F,  // GAMMA4
  0xED, 2, 0x1B, 0x0B,
  0xAE, 1, 0x77,
  0xCD, 1, 0x63,
  0xE8, 1, 0x34,     // FRAMERATE
  0x62, 12, 0x18, 0x0D, 0x71, 0xED, 0x70, 0x70,
           0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70,
  0x63, 12, 0x18, 0x11, 0x71, 0xF1, 0x70, 0x70,
           0x18, 0x13, 0x71, 0xF3, 0x70, 0x70,
  0x64, 7, 0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07,
  0x66, 10, 0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00,
  0x67, 10, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98,
  0x74, 7, 0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00,
  0x98, 2, 0x3e, 0x07,
  0x35, 0,            // TEON (no params)
  0x21, 0,            // **INVON - Display Inversion ON (no params)**
  0x11, 0x80,         // **SLPOUT with 150ms delay (0x80 = delay flag)**
  0x29, 0x80,         // **DISPON with 150ms delay (0x80 = delay flag)**
  0x00
};
```

### Command Header Interpretation

Each command in the array has format:
```
[COMMAND_BYTE, PARAM_COUNT, ...PARAMS]
```

Where `PARAM_COUNT`:
- Regular byte count: 1, 2, 3, 4, 6, 7, 10, 12
- **0x80 bit flag**: Indicates "add 150ms delay after this command"
  - `0 = no params, no delay`
  - `0x80 = no params, but ADD 150ms delay`
  - `1 = 1 param byte`
  - `0x81 = 1 param byte, then add 150ms delay`

---

## 2. Key Command Values Extracted

| Command Name | Hex Value | Parameter(s) | Purpose |
|--------------|-----------|--------------|---------|
| **COLMOD** | 0x3A | 0x05 | Set pixel format to RGB565 (5-5-6) |
| **MADCTL** | 0x36 | 0x48 | Memory access: MX=0x40, BGR=0x08 |
| **INVON** | 0x21 | (none) | **Display Inversion ON** |
| **POWER1** | 0xC3 | 0x13 | Power Control 1 |
| **POWER2** | 0xC4 | 0x13 | Power Control 2 |
| **POWER3** | 0xC9 | 0x22 | Power Control 3 |
| **SLPOUT** | 0x11 | with 0x80 | Sleep Out + **150ms delay** |
| **DISPON** | 0x29 | with 0x80 | Display ON + **150ms delay** |
| **TEON** | 0x35 | (none) | Tearing Effect ON |
| **BRIGHTNESS** | 0x51 | 0xFF | (sent separately after init) |

### MADCTL Bit Breakdown

```
MADCTL = 0x48
  = 0x40 (MADCTL_MX)   | Right-to-left direction
  | 0x08 (MADCTL_BGR)  | Blue-Green-Red pixel order (not RGB)

Bit 7: 0 = Top to Bottom (MY)
Bit 6: 1 = Right to Left (MX)        ← SET IN ADAFRUIT
Bit 5: 0 = Normal mode (MV)
Bit 4: 0 = LCD refresh (ML)
Bit 3: 1 = BGR color order (BGR)     ← SET IN ADAFRUIT
```

---

## 3. Comparison: Adafruit vs Our Implementation

### 3.1 Our Current gc9a01_spi.py init_display() (Lines 266-368)

```python
def init_display(self):
    """Initialize the display using the complete Adafruit GC9A01A sequence."""
    logger.info("Initializing GC9A01 display (Complete Adafruit sequence)...")

    try:
        # ===== Hardware Reset =====
        self.reset()

        # ===== Register Configuration =====
        self._write_command_data(0xEB, bytes([0x14]))
        self._write_command_data(0x84, bytes([0x40]))
        # ... (0x85-0x8F all present) ...

        # ===== Display Configuration =====
        self._write_command_data(0xB6, bytes([0x00, 0x00]))
        self._write_command_data(self.CMD_MEMORY_ACCESS, bytes([0x40 | 0x08]))  # MX | BGR
        self._write_command_data(self.CMD_INTERFACE_PIXEL_FORMAT, bytes([0x05]))  # RGB565

        # ... (0x90, 0xBD, 0xBC, 0xFF all present) ...

        # ===== Power Control =====
        self._write_command_data(0xC3, bytes([0x13]))  # Power control 1
        self._write_command_data(0xC4, bytes([0x13]))  # Power control 2
        self._write_command_data(0xC9, bytes([0x22]))  # Power control 3
        self._write_command_data(0xBE, bytes([0x11]))

        # ... (Gamma curves, timing, clock dividers all present) ...

        # ===== CRITICAL: Display Control Commands =====
        self._write_command(self.CMD_TEARING_EFFECT)  # 0x35

        # ===== Sleep Out =====
        self._write_command(self.CMD_SLEEP_OUT)  # 0x11
        time.sleep(0.150)  # 150ms delay

        # ===== Normal Mode =====
        self._write_command(self.CMD_NORMAL_ON)  # 0x13
        time.sleep(0.010)

        # ===== Display ON =====
        self._write_command(self.CMD_DISPLAY_ON)  # 0x29
        time.sleep(0.150)  # 150ms delay

        # ===== Brightness Control =====
        self._write_command_data(self.CMD_BRIGHTNESS, bytes([0xFF]))
        time.sleep(0.010)

        self.initialized = True
```

### 3.2 Differences Found

#### ISSUE #1: Missing INVON (Display Inversion) Command ⚠️

**Adafruit sequence (lines before SLPOUT):**
```c
0x35, 0,            // TEON (Tearing Effect ON)
0x21, 0,            // INVON (Display Inversion ON) ← THIS IS MISSING IN OUR CODE
0x11, 0x80,         // SLPOUT with 150ms delay
0x29, 0x80,         // DISPON with 150ms delay
```

**Our sequence (lines 339-354):**
```python
self._write_command(self.CMD_TEARING_EFFECT)  # 0x35
# INVON (0x21) IS NOT SENT!
self._write_command(self.CMD_SLEEP_OUT)  # 0x11
time.sleep(0.150)
self._write_command(self.CMD_NORMAL_ON)  # 0x13 ← This is different
time.sleep(0.010)
self._write_command(self.CMD_DISPLAY_ON)  # 0x29
time.sleep(0.150)
```

**Impact on "Grey Colors" Issue**:
- INVON (0x21) enables display inversion at the hardware level
- **WITHOUT this command, color inversion may not work properly**
- This could cause colors to appear desaturated or shifted to grayscale
- The command changes how the display hardware interprets pixel values

#### ISSUE #2: Missing CMD_NORMAL_ON Before Display ON ⚠️

**Adafruit doesn't send 0x13 (Normal Display Mode) explicitly**
- Adafruit sends: `0x35` → `0x21` → `0x11` → `0x29`
- **Our code sends**: `0x35` → `0x11` → `0x13` → `0x29`

The presence of `0x13` (CMD_NORMAL_ON) between SLPOUT and DISPON may be:
1. **Harmless** if the display already defaults to normal mode, OR
2. **Interfering** with the display's internal state machine

#### ISSUE #3: Initial Register Write Difference

**Adafruit sequence starts with:**
```c
0xEF, 0,           // INREGEN2 (no params)
0xEB, 1, 0x14,
0xFE, 0,           // INREGEN1 (no params)
0xEF, 0,           // INREGEN2 again (no params)
0xEB, 1, 0x14,     // Send 0xEB, 0x14 again
0x84, 1, 0x40,     // Then proceed to 0x84-0x8F sequence
...
```

**Our sequence:**
```python
self._write_command_data(0xEB, bytes([0x14]))  # Starts at 0xEB, misses the 0xEF/0xFE setup!
self._write_command_data(0x84, bytes([0x40]))
```

**Analysis**: We're skipping the initial register unlock sequence (0xEF → 0xFE → 0xEF → 0xEB)
- `0xEF` = INREGEN2 (Inter-register enable 2)
- `0xFE` = INREGEN1 (Inter-register enable 1)
- These unlock undocumented registers for the 0x84-0x8F configuration
- **Skipping this may leave undocumented registers in wrong state**

---

## 4. Exact MADCTL Value Analysis

Both implementations use **0x48**:

```
Adafruit: MADCTL = 0x36, 1, 0x48
Our code: self._write_command_data(self.CMD_MEMORY_ACCESS, bytes([0x40 | 0x08]))  # MX | BGR
          = 0x36, 0x48  ✓ MATCHES
```

✓ **MADCTL is correct in both**

---

## 5. Power Control Commands

### Adafruit (lines in initcmd):
```c
0xC3, 1, 0x13,     // POWER2 (sometimes labeled POWER1)
0xC4, 1, 0x13,     // POWER3 (sometimes labeled POWER2)
0xC9, 1, 0x22,     // POWER4 (sometimes labeled POWER3)
0xBE, 1, 0x11,     // Additional power register
```

### Our code (lines 310-313):
```python
self._write_command_data(0xC3, bytes([0x13]))  # Power control 1
self._write_command_data(0xC4, bytes([0x13]))  # Power control 2
self._write_command_data(0xC9, bytes([0x22]))  # Power control 3
self._write_command_data(0xBE, bytes([0x11]))
```

✓ **Power control values match exactly**

---

## 6. Brightness/PWM Configuration

### Adafruit approach:
- Does NOT send brightness in the initcmd array
- Brightness is controlled after full initialization via 0x51 command (sent separately)

### Our code (line 359):
```python
self._write_command_data(self.CMD_BRIGHTNESS, bytes([0xFF]))  # Max brightness
time.sleep(0.010)
```

✓ **Matches Adafruit's separate brightness configuration**

---

## 7. Gamma Curves Comparison

### Adafruit (exact values from initcmd):
```c
0xF0, 6, 0x45, 0x09, 0x08, 0x08, 0x26, 0x2A,  // GAMMA1
0xF1, 6, 0x43, 0x70, 0x72, 0x36, 0x37, 0x6F,  // GAMMA2
0xF2, 6, 0x45, 0x09, 0x08, 0x08, 0x26, 0x2A,  // GAMMA3
0xF3, 6, 0x43, 0x70, 0x72, 0x36, 0x37, 0x6F,  // GAMMA4
```

### Our code (lines 318-321):
```python
self._write_command_data(0xF0, bytes([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]))  # Gamma 1
self._write_command_data(0xF1, bytes([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]))  # Gamma 2
self._write_command_data(0xF2, bytes([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]))  # Gamma 3
self._write_command_data(0xF3, bytes([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]))  # Gamma 4
```

✓ **Gamma curves match exactly**

---

## 8. Root Cause Analysis: Why Colors Appear Grey

### Most Likely Cause: Missing INVON (0x21) Command

The **Display Inversion ON** command (0x21) is critical:

1. **Hardware-Level Color Inversion**:
   - Inverts the polarity of the display signals
   - Changes how pixel values are interpreted
   - Without it: Color channels may be shifted or incorrect

2. **Impact on RGB565**:
   - If INVON is missing, the display may invert colors internally
   - This manifests as: Red → Cyan, Green → Magenta, Blue → Yellow
   - **Or**: Colors become desaturated (appear greyish)

3. **Why It Causes Grey Colors**:
   - Inversion without the hardware flag can cause color loss
   - The display driver may be applying wrong corrections
   - RGB channels not properly aligned → reduced saturation

### Secondary Causes:

1. **Missing Register Unlock (0xEF/0xFE sequence)**:
   - Undocumented registers 0x84-0x8F may be in wrong state
   - Could affect color accuracy, contrast, or saturation

2. **Missing Delay on TEON (0x35)**:
   - Tearing effect setup may need settling time
   - Not critical but could cause timing issues

3. **Extra 0x13 (NORMAL_ON) Command**:
   - Our code sends it between SLPOUT and DISPON
   - Adafruit doesn't send this command at all
   - May interfere with display state machine

---

## 9. Summary of Required Changes

### Critical Fixes (Must Do):

1. **Add INVON (0x21) command** before SLPOUT
   ```python
   self._write_command(0x21)  # Display Inversion ON
   ```

2. **Add initial register unlock sequence** at the start
   ```python
   self._write_command(0xEF)  # INREGEN2
   self._write_command_data(0xEB, bytes([0x14]))
   self._write_command(0xFE)  # INREGEN1
   self._write_command(0xEF)  # INREGEN2
   self._write_command_data(0xEB, bytes([0x14]))
   # Then proceed to 0x84-0x8F sequence
   ```

3. **Remove the extra 0x13 (NORMAL_ON)** command
   - Our code sends it between SLPOUT and DISPON
   - Adafruit never sends this in init

### Verify:

- [ ] MADCTL = 0x48 (already correct)
- [ ] COLMOD = 0x05 (already correct)
- [ ] Power commands = 0xC3:0x13, 0xC4:0x13, 0xC9:0x22 (already correct)
- [ ] Gamma curves all correct (already correct)
- [ ] TEON (0x35) sent (already correct)
- [ ] SLPOUT (0x11) with 150ms delay (already correct)
- [ ] DISPON (0x29) with 150ms delay (already correct)
- [ ] Brightness (0x51) set to 0xFF (already correct)

---

## 10. Side-by-Side Command Sequence

```
=== ADAFRUIT (CORRECT) ===              === OUR CODE (CURRENT) ===
0xEF (INREGEN2)                         ✗ MISSING
0xEB, 0x14                              (implicit in our sequence)
0xFE (INREGEN1)                         ✗ MISSING
0xEF (INREGEN2)                         ✗ MISSING
0xEB, 0x14                              (implicit in our sequence)
0x84-0x8F (undoc regs)                  ✓ Present
0xB6, 0x00, 0x00                        ✓ Present
0x36, 0x48 (MADCTL)                     ✓ Present
0x3A, 0x05 (COLMOD)                     ✓ Present
0x90, 4 bytes                           ✓ Present
0xBD-0xBC                               ✓ Present
0xFF, 3 bytes                           ✓ Present
0xC3-0xC9, 0xBE (power)                 ✓ Present
0xE1, 0xDF (gamma setup)                ✓ Present
0xF0-0xF3 (gamma curves)                ✓ Present
0xED-0xAE-0xCD-0xE8 (timing)            ✓ Present
0x62-0x67-0x74-0x98 (clock/display)     ✓ Present
0x35 (TEON)                             ✓ Present
0x21 (INVON) ← KEY!                     ✗ MISSING!!!
0x11, 0x80 (SLPOUT + 150ms)             ✓ Present
    [150ms delay]                       ✓ Present
✗ (NO 0x13)                             ✗ Our code sends 0x13 here (WRONG)
0x29, 0x80 (DISPON + 150ms)             ✓ Present
    [150ms delay]                       ✓ Present
(0x51, 0xFF later for brightness)       ✓ Present
```

---

## Conclusion

**The missing INVON (0x21) command is the most likely cause of the "all colors appear as grey" issue.**

Additionally, the missing initial register unlock sequence (0xEF/0xFE) could contribute to color inaccuracy or saturation problems.

Our implementation has ~95% of the Adafruit sequence correct, but these critical missing commands in the right order/timing are likely causing the display malfunction.

### Next Steps:
1. Add the INVON (0x21) command before SLPOUT
2. Add the initial register unlock sequence (0xEF/0xFE/0xEF/0xEB)
3. Remove the extra 0x13 (NORMAL_ON) command
4. Test with color patterns to verify saturation is restored
