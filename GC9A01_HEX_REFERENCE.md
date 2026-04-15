# GC9A01 Hex Command Reference - Complete Mapping

## Command Code Definitions (from Adafruit headers)

```
0x01 = SOFTWARE RESET
0x11 = SLEEP OUT (SLPOUT)
0x12 = PARTIAL MODE ON
0x13 = NORMAL DISPLAY MODE ON
0x20 = DISPLAY INVERSION OFF
0x21 = DISPLAY INVERSION ON (INVON) ← WE'RE MISSING THIS
0x26 = GAMMA CURVE SELECTION
0x28 = DISPLAY OFF
0x29 = DISPLAY ON (DISPON)
0x2A = COLUMN ADDRESS SET
0x2B = ROW ADDRESS SET
0x2C = WRITE TO RAM (MEMORY WRITE)
0x35 = TEARING EFFECT LINE ON (TEON)
0x36 = MEMORY ACCESS CONTROL (MADCTL)
0x3A = INTERFACE PIXEL FORMAT (COLMOD)
0x51 = WRITE BRIGHTNESS/BRIGHTNESS CONTROL
0x55 = BRIGHTNESS DISPLAY VALUE CONTROL

0x62 = GAMMA CURVE ADJUSTMENT (Part 1)
0x63 = GAMMA CURVE ADJUSTMENT (Part 2)
0x64 = GAMMA CURVE ADJUSTMENT (Part 3)
0x66 = DISPLAY FUNCTION CONTROL (Part 1)
0x67 = DISPLAY FUNCTION CONTROL (Part 2)
0x74 = SET PANEL RELATED (Part 1)
0x84-0x8F = UNDOCUMENTED REGISTERS (Critical for color)

0x98 = SET PANEL RELATED (Part 2)
0xAE = DISPLAY ENHANCEMENT A
0xBC = FRAME RATE/DISPLAY TIMING (Part 2)
0xBD = FRAME RATE/DISPLAY TIMING (Part 1)
0xBE = PANEL VOLTAGE SETTING
0xC3 = POWER CONTROL 1 (or 2 depending on labeling)
0xC4 = POWER CONTROL 2 (or 3 depending on labeling)
0xC9 = POWER CONTROL 3 (or 4 depending on labeling)
0xCD = FRAME RATE CONTROL
0xDF = DISPLAY MODE SETTING
0xE1 = DISPLAY ENHANCEMENT B
0xE8 = FRAME RATE CONTROL (FRAMERATE)
0xEB = READOUT FROM DISPLAY IDENTIFICATION
0xED = TIMING ADJUSTMENT
0xEF = INTER REGISTER ENABLE 2 (INREGEN2) ← WE'RE MISSING THIS
0xF0 = GAMMA CURVE 1 (GAMMA1)
0xF1 = GAMMA CURVE 2 (GAMMA2)
0xF2 = GAMMA CURVE 3 (GAMMA3)
0xF3 = GAMMA CURVE 4 (GAMMA4)
0xFE = INTER REGISTER ENABLE 1 (INREGEN1) ← WE'RE MISSING THIS
0xFF = FRAME RATE/CONTRAST/BRIGHTNESS ADJUSTMENT
```

---

## Complete Initialization Command Sequence (Adafruit Reference)

### Part 1: Register Unlock & Undocumented Setup
```
Command    Params  Values              Description
-------    ------  ------              -----------
0xEF       0       -                   INREGEN2 (unlock registers)
0xEB       1       0x14                Config A
0xFE       0       -                   INREGEN1 (unlock registers)
0xEF       0       -                   INREGEN2 (unlock registers)
0xEB       1       0x14                Config A (repeat)
0x84       1       0x40                Undocumented
0x85       1       0xFF                Undocumented
0x86       1       0xFF                Undocumented
0x87       1       0xFF                Undocumented
0x88       1       0x0A                Undocumented
0x89       1       0x21                Undocumented
0x8A       1       0x00                Undocumented
0x8B       1       0x80                Undocumented
0x8C       1       0x01                Undocumented
0x8D       1       0x01                Undocumented
0x8E       1       0xFF                Undocumented
0x8F       1       0xFF                Undocumented
```

### Part 2: Display Configuration
```
Command    Params  Values              Description
-------    ------  ------              -----------
0xB6       2       0x00, 0x00          Display configuration
0x36       1       0x48                MADCTL (MX=0x40 | BGR=0x08)
0x3A       1       0x05                COLMOD (RGB565)
0x90       4       0x08,0x08,0x08,0x08 Undocumented
0xBD       1       0x06                Frame rate timing
0xBC       1       0x00                Frame rate timing
0xFF       3       0x60,0x01,0x04      Contrast/brightness adjust
```

### Part 3: Power Control
```
Command    Params  Values              Description
-------    ------  ------              -----------
0xC3       1       0x13                Power control 1
0xC4       1       0x13                Power control 2
0xC9       1       0x22                Power control 3
0xBE       1       0x11                Panel voltage setting
```

### Part 4: Gamma Curves & Timing
```
Command    Params  Values (6 bytes each)
-------    ------  ---------------------
0xE1       2       0x10, 0x0E
0xDF       3       0x21, 0x0c, 0x02
0xF0       6       0x45,0x09,0x08,0x08,0x26,0x2A  (Gamma 1)
0xF1       6       0x43,0x70,0x72,0x36,0x37,0x6F  (Gamma 2)
0xF2       6       0x45,0x09,0x08,0x08,0x26,0x2A  (Gamma 3)
0xF3       6       0x43,0x70,0x72,0x36,0x37,0x6F  (Gamma 4)
0xED       2       0x1B, 0x0B
0xAE       1       0x77
0xCD       1       0x63
0xE8       1       0x34
```

### Part 5: Clock Dividers & Display Control
```
Command    Params  Description
-------    ------  -----------
0x62       12      Clock divider (Part 1)
0x63       12      Clock divider (Part 2)
0x64       7       Clock divider (Part 3)
0x66       10      Display function control (Part 1)
0x67       10      Display function control (Part 2)
0x74       7       Panel control
0x98       2       Panel control (Part 2)
```

### Part 6: Display Enable Sequence (CRITICAL)
```
Command    Params  Delay   Description
-------    ------  -----   -----------
0x35       0       None    TEON (Tearing effect ON)
0x21       0       None    INVON (Display Inversion ON) ← MISSING IN OUR CODE
0x11       0x80    150ms   SLPOUT (Sleep out) + mandatory delay
0x29       0x80    150ms   DISPON (Display ON) + mandatory delay
```

### Part 7: Brightness (sent after init complete)
```
Command    Params  Values              Description
-------    ------  ------              -----------
0x51       1       0xFF                BRIGHTNESS = Max (255)
```

---

## Our Current Implementation (gc9a01_spi.py)

### Lines 284-337: Register Configuration & Setup
```python
# Line 284-296: Undocumented registers (0x84-0x8F)
self._write_command_data(0xEB, bytes([0x14]))  # ← Should be after unlock!
self._write_command_data(0x84, bytes([0x40]))  # ✓
self._write_command_data(0x85, bytes([0xFF]))  # ✓
# ... etc ...

# Line 299-301: Display configuration
self._write_command_data(0xB6, bytes([0x00, 0x00]))           # ✓
self._write_command_data(0x36, bytes([0x40 | 0x08]))          # ✓ MADCTL
self._write_command_data(0x3A, bytes([0x05]))                 # ✓ COLMOD

# Line 304-307: More undocumented
self._write_command_data(0x90, bytes([0x08, 0x08, 0x08, 0x08]))  # ✓
self._write_command_data(0xBD, bytes([0x06]))                    # ✓
self._write_command_data(0xBC, bytes([0x00]))                    # ✓
self._write_command_data(0xFF, bytes([0x60, 0x01, 0x04]))        # ✓

# Line 310-313: Power control
self._write_command_data(0xC3, bytes([0x13]))  # ✓
self._write_command_data(0xC4, bytes([0x13]))  # ✓
self._write_command_data(0xC9, bytes([0x22]))  # ✓
self._write_command_data(0xBE, bytes([0x11]))  # ✓

# Line 316-321: Gamma curves
self._write_command_data(0xE1, bytes([0x10, 0x0E]))                           # ✓
self._write_command_data(0xDF, bytes([0x21, 0x0c, 0x02]))                     # ✓
self._write_command_data(0xF0, bytes([0x45,0x09,0x08,0x08,0x26,0x2A]))        # ✓
self._write_command_data(0xF1, bytes([0x43,0x70,0x72,0x36,0x37,0x6F]))        # ✓
self._write_command_data(0xF2, bytes([0x45,0x09,0x08,0x08,0x26,0x2A]))        # ✓
self._write_command_data(0xF3, bytes([0x43,0x70,0x72,0x36,0x37,0x6F]))        # ✓

# Line 324-327: Timing & frame rate
self._write_command_data(0xED, bytes([0x1B, 0x0B]))        # ✓
self._write_command_data(0xAE, bytes([0x77]))              # ✓
self._write_command_data(0xCD, bytes([0x63]))              # ✓
self._write_command_data(0xE8, bytes([0x34]))              # ✓

# Line 330-336: Clock dividers & display control
self._write_command_data(0x62, bytes([0x18,0x0D,0x71,0xED,0x70,0x70,
                                      0x18,0x0F,0x71,0xEF,0x70,0x70]))  # ✓
self._write_command_data(0x63, bytes([0x18,0x11,0x71,0xF1,0x70,0x70,
                                      0x18,0x13,0x71,0xF3,0x70,0x70]))  # ✓
self._write_command_data(0x64, bytes([0x28,0x29,0xF1,0x01,0xF1,0x00,0x07]))  # ✓
self._write_command_data(0x66, bytes([0x3C,0x00,0xCD,0x67,0x45,0x45,
                                      0x10,0x00,0x00,0x00]))             # ✓
self._write_command_data(0x67, bytes([0x00,0x3C,0x00,0x00,0x00,0x01,
                                      0x54,0x10,0x32,0x98]))             # ✓
self._write_command_data(0x74, bytes([0x10,0x85,0x80,0x00,0x00,0x4E,0x00]))  # ✓
self._write_command_data(0x98, bytes([0x3e,0x07]))                      # ✓
```

### Lines 339-355: Display Enable Sequence (CRITICAL ISSUE HERE)
```python
# Line 340
self._write_command(self.CMD_TEARING_EFFECT)  # 0x35 ✓

# ✗ MISSING: self._write_command(0x21)  # INVON (Display Inversion ON)

# Line 344
self._write_command(self.CMD_SLEEP_OUT)  # 0x11 ✓
time.sleep(0.150)  # ✓ 150ms delay

# Line 349 ✗ WRONG: Extra command not in Adafruit
self._write_command(self.CMD_NORMAL_ON)  # 0x13 - NOT IN ADAFRUIT!
time.sleep(0.010)

# Line 354
self._write_command(self.CMD_DISPLAY_ON)  # 0x29 ✓
time.sleep(0.150)  # ✓ 150ms delay

# Line 359
self._write_command_data(self.CMD_BRIGHTNESS, bytes([0xFF]))  # 0x51 ✓
time.sleep(0.010)
```

---

## Missing vs Present: Summary Table

| Hex | Command | Name | Adafruit | Our Code | Status |
|-----|---------|------|----------|----------|--------|
| 0xEF | Unlock | INREGEN2 | ✓ | ✗ | MISSING |
| 0xFE | Unlock | INREGEN1 | ✓ | ✗ | MISSING |
| 0x84-0x8F | Setup | Undocumented | ✓ | ✓ | Present but locked |
| 0xB6 | Display | Config | ✓ | ✓ | Present |
| 0x36 | Color | MADCTL | ✓ | ✓ | Present (0x48) |
| 0x3A | Color | COLMOD | ✓ | ✓ | Present (0x05) |
| 0xC3 | Power | Power1 | ✓ | ✓ | Present (0x13) |
| 0xC4 | Power | Power2 | ✓ | ✓ | Present (0x13) |
| 0xC9 | Power | Power3 | ✓ | ✓ | Present (0x22) |
| 0xF0-0xF3 | Gamma | Gamma1-4 | ✓ | ✓ | Present (exact) |
| 0x35 | Enable | TEON | ✓ | ✓ | Present |
| **0x21** | **Enable** | **INVON** | **✓** | **✗** | **MISSING (CRITICAL)** |
| 0x11 | Enable | SLPOUT | ✓ | ✓ | Present |
| 0x13 | Enable | NORMAL_ON | ✗ | ✓ | EXTRA (ERROR) |
| 0x29 | Enable | DISPON | ✓ | ✓ | Present |
| 0x51 | Brightness | BRIGHTNESS | ✓ | ✓ | Present (0xFF) |

---

## Key Values Reference

### MADCTL = 0x36 (Memory Access Control)
```
Value: 0x48
Binary: 0100 1000
        ││││ ││││
        ││││ │││└─ 0: Normal RGB order (or 1: BGR order) ← SET
        ││││ ││└── 0: Normal (or 1: refresh right to left)
        ││││ │└─── 0: Normal (or 1: refresh top to bottom)
        ││││ └──── 0: Normal (or 1: reverse)
        │││└────── 0: Normal (or 1: horizontal/vertical flip)
        ││└─────── 0: Right to left (or 1: left to right) ← SET
        │└──────── 0: Top to bottom (or 1: bottom to top)
        └───────── 0: RGB mode (or 1: ? depends on bit 3)

Result: 0x40 (MX - Right to Left) | 0x08 (BGR - Blue-Green-Red) = 0x48
```

### COLMOD = 0x3A (Pixel Format)
```
Value: 0x05
DBI color depth:
  0x01 = 12-bit/pixel (4-4-4 RGB)
  0x02 = 16-bit/pixel (5-6-5 RGB)
  0x03 = 18-bit/pixel (6-6-6 RGB)
  0x04 = 16-bit/pixel (5-5-5-1 ARGB)
  0x05 = 16-bit/pixel (5-6-5 RGB) ← WE USE THIS

Result: 0x05 = RGB565 (5-bit R, 6-bit G, 5-bit B)
```

### INVON = 0x21 (Display Inversion ON)
```
No parameters
Function: Inverts the display hardware polarity
Effect: Without this, colors may appear desaturated, shifted, or greyscale
Critical: Must be set during initialization
```

---

## Power Control Values

| Register | Name | Adafruit | Our Code | Purpose |
|----------|------|----------|----------|---------|
| 0xC3 | POWER1 | 0x13 | 0x13 | VRH (Voltage reference) |
| 0xC4 | POWER2 | 0x13 | 0x13 | VCL (Negative voltage) |
| 0xC9 | POWER3 | 0x22 | 0x22 | VGH (Positive voltage) |
| 0xBE | Panel Volt | 0x11 | 0x11 | Panel voltage setting |

All power control values are **exactly correct** in our implementation.

---

## Timing Reference

| Command | Hex | Delay (Adafruit) | Our Code | Status |
|---------|-----|------------------|----------|--------|
| SLPOUT | 0x11 | 150ms (0x80 flag) | 150ms | ✓ Correct |
| DISPON | 0x29 | 150ms (0x80 flag) | 150ms | ✓ Correct |
| Other | - | Immediate | - | - |

The 0x80 flag in Adafruit's byte count means "add mandatory 150ms delay after command".

---

## Conclusion

**Our implementation is 95% correct** but missing these critical elements:

1. **0xEF/0xFE register unlock** before undocumented registers
2. **0x21 INVON command** before SLPOUT (CAUSES GREY COLOR ISSUE)
3. **Extra 0x13 NORMAL_ON** that shouldn't be there

Fix these three issues and the display should output proper colors.

See `GC9A01_ISSUE_ANALYSIS.md` for detailed fix instructions.
