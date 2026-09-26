# M10-R B2Y record 0x18 — COLOR DIFFERENCE SUPPRESSION / SATURATION geometry

Date: 2026-09-26

Branch: `m10r-b2y-colordifsuppress1b`

## Status

Firmware/selector/register mapping is now strong enough to identify the M10-R saturation-control geometry.

**No Android renderer change is authorized by this note.**

## 1. Selector and hardware identity

Canonical IMG-System selector inventory proves:

- selector: `0x153B80`
- calibration record: `0x18`
- name: `color_dif_suppression`
- hardware setter: `0xD0770`
- hardware page: `0x20021100`

Saved-still M10-R selects this record by:

- `_B2YMODE:STILL_SATURATION:LOW`
- `_B2YMODE:STILL_SATURATION:MEDIUM`
- `_B2YMODE:STILL_SATURATION:HIGH`
- `_B2YMODE:STILL_SATURATION:MONOCHROME`

The two tested M10 Monochrom firmwares do not expose those saved-still saturation keys. They reuse record 0x18 for `_TONEHUE:...` controls instead.

## 2. M10-R color preset payloads

Record size: 144 bytes.

Preset-dependent six-value bank at payload offsets:

`+0x10,+0x14,+0x18,+0x1C,+0x20,+0x24`

Values:

| preset | six values | ratio to 8192 |
|---|---:|---:|
| LOW | 6964 x6 | 0.850098 |
| MEDIUM | 8192 x6 | 1.000000 |
| HIGH | 9830 x6 | 1.199951 |

The hardware setter copies these values directly as six 14-bit fields into:

- page +0x10 low/high field
- page +0x14 low/high field
- page +0x18 low/high field

No selector-side or setter-side scaling is applied.

The exact numeric role of 8192 is not named by firmware, but the LOW/MEDIUM/HIGH ratios make Q13-unity semantics a strong structural interpretation.

## 3. Six companion fields and five knots

Immediately following the six 14-bit fields:

### Six 23-bit fields

Payload:

`+0x28,+0x2C,+0x30,+0x34,+0x38,+0x3C`

M10-R LOW/MEDIUM/HIGH value: all zero.

Setter destination:

- page +0x20
- page +0x24
- page +0x28
- page +0x2C
- page +0x30
- page +0x34

Each destination consumes one 23-bit payload field.

### Five ordered 16-bit values

Payload:

- +0x40 = 0
- +0x44 = 20000
- +0x48 = 30000
- +0x4C = 40000
- +0x50 = 50000

Setter packs them into the 16-bit fields at page +0x40, +0x44 and +0x48.

This 6 + 6 + 5 geometry is strongly consistent with a six-segment piecewise transform:
six gain/slope-like values, six companion offset-like values, and five segment boundaries.

**The exact hidden hardware equation, comparison coordinate, interpolation, rounding and clipping remain unproven.**

## 4. Why the M10-R presets simplify the unknown hardware

Whatever scalar coordinate selects the six segments, all six M10-R LOW/MEDIUM/HIGH gain-like values are equal within each preset, while all six companion values are zero.

Therefore the segment-selection details cannot change the preset gain if the six lanes are the multiplicative/slope term indicated by the geometry.

This gives the strongest current structural interpretation:

- LOW: uniform color-difference scale about 0.85
- MEDIUM: uniform color-difference scale about 1.00
- HIGH: uniform color-difference scale about 1.20

This is **not yet a claim of the exact pixel equation**. It is a register/payload structural result.

## 5. Remaining fields

The later payload/register region includes full-range-looking pairs and a second mode area:

- +0x54/+0x58 and +0x5C/+0x60 -> page +0x50/+0x54
- +0x64/+0x68/+0x6C -> control bits in page +0x58
- +0x70/+0x74 -> paired 16-bit fields at page +0x5C
- +0x78/+0x7C -> fields at page +0x60
- +0x80/+0x84 and +0x88/+0x8C -> page +0x64/+0x68

M10 Monochrom tone-hue presets leave the M10-R six-lane saturation bank zero and instead vary the later +0x70/+0x74 pair, for example:

- sepia weak: +180 / -240
- sepia strong: +384 / -640
- blue weak: -128 / +312
- blue strong: -256 / +450
- selenium weak: 0 / +128
- selenium strong: 0 / +384

This proves record 0x18 contains at least two independently used color-control substructures:
a saturation/color-difference scale area and a tone-hue area.

## 6. Consequence for current skin investigation

This is a real M10-R-specific saved-still color block and should eventually be implemented for user saturation modes.

However, current first-parity/default work is using the equivalent of M10-R **MEDIUM** saturation. The six selected values are exact 8192 unity candidates and the companion six fields are zero.

Therefore record 0x18 is **not presently strong evidence for a missing default-MEDIUM skin correction**.

Do not use this finding to justify:

- another global saturation reduction;
- a skin-specific HSL correction;
- changing WB;
- changing exposure;
- promoting Y_BLEND k=0.45.

The current default-skin investigation should return to the pre-CC1 warm-highlight/chroma behavior already identified by the private replay and POSTYC1A work.

## 7. Separate implementation value

Record 0x18 remains high-value for a future proper Leica saturation control:

- LOW ≈ 0.85
- MEDIUM ≈ 1.00
- HIGH ≈ 1.20
- MONOCHROME uses a distinct control state

Implement only after the input/output color-difference domain and exact application point are constrained.

## Evidence

- `research/generated/M10R_B2Y_CHROMA_KEY_CROSSMODEL1A.json`
- `research/generated/M10R_B2Y_CHROMA_KEY_CROSSMODEL1A.md`
- `research/generated/M10R_B2Y_COLORDIFSUPPRESS_DRIVER1B.txt`
- `research/M10R_v094_b2y_selector_inventory.txt`
