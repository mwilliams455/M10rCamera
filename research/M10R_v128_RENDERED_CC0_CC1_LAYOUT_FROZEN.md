# M10-R v1.28 — RENDERED CC0 / CC1 LAYOUT FROZEN

Date: 2026-09-04

## Scope

This freezes the rendered `CC0` / `CC1` color-correction representation observed in `ca9_cm_ColorManagementFinished`.

These records are **not** DNG `ColorMatrix1` / `ColorMatrix2`. DNG CM1/CM2 remain frozen separately in `M10R_v126_DNG_CM_LAYOUT_FROZEN.md`.

## Callback source-state offsets

The callback preserves original `r0` as its source-state base.

Frozen rendered-color fields:

```text
source +0x28 : CC0 matrix/color-spec record (0x2C bytes)
source +0x50 : CC0 Kelvin (record +0x28)
source +0x54 : CC1 matrix/color-spec record (0x2C bytes)
source +0x7C : CC1 Kelvin (record +0x28)
source +0x80 : CC0 default-data flag (u8)
source +0x81 : CC1 default-data flag (u8)
source +0x84 : CC0 tint (s16)
source +0x9C : CC1 tint (s16)
```

The firmware diagnostics directly identify these as:

```text
[out] CC0 default data
[out] CC0 T[K], Tint
[out] CC0 R0/R1/R2
[out] CC0 denominator

[out] CC1 default data
[out] CC1 T[K], Tint
[out] CC1 R0/R1/R2
[out] CC1 denominator
```

## 0x2C rendered CC record

Both CC0 and CC1 use the same 44-byte record encoding:

```c
struct M10RRenderedCCRecord {
    int32_t coeff[9];      // +0x00 .. +0x20
    uint16_t scaleCode;    // +0x24
    uint16_t unknown26;    // +0x26 — unresolved, do not name yet
    int32_t kelvin;        // +0x28
};                         // sizeof = 0x2C
```

The final `+0x28` word is now resolved: it is Kelvin.

Proof:

```text
CC0 record base = source+0x28
CC0 record+0x28 = source+0x50
firmware prints source+0x50 as CC0 T[K]

CC1 record base = source+0x54
CC1 record+0x28 = source+0x7C
firmware prints source+0x7C as CC1 T[K]
```

## Matrix decoding

For each record firmware reads the 16-bit field at `record+0x24` and derives the matrix denominator as:

```text
denominator = 1 << (9 - scaleCode)
```

Each signed 32-bit coefficient is converted to double and divided by that denominator:

```text
M[r][c] = coeff[r*3+c] / denominator
```

The diagnostic `CC0 denominator` / `CC1 denominator` output is this derived power-of-two denominator, not the raw `scaleCode` field.

## Default flags and tint are outside the 0x2C records

Do not place default flag or tint inside `M10RRenderedCCRecord`.

They are separate source-state fields:

```text
CC0 default = *(u8 *)(source+0x80)
CC1 default = *(u8 *)(source+0x81)
CC0 tint    = *(s16*)(source+0x84)
CC1 tint    = *(s16*)(source+0x9C)
```

The asymmetry of the tint offsets is real in the observed callback. Do not force a symmetric guessed container structure around CC0/CC1.

## Additional color-state data observed nearby

The callback also prints output `x` / `y` values from 16-bit rational-like fields rooted around `source+0x82`, and later prints remapped R/G/B gains from fields around `source+0xB8` and following offsets.

Those fields are deliberately not folded into the CC0/CC1 record freeze. They belong to the next WB / white-point / gain trace.

## Separation from DNG matrices

DNG CM records:

```text
rooted at *(source+0x24)
logical size 0x28
9 x int32 coeff + int32 denominator
T1/T2 are separate doubles around those matrix records
```

Rendered CC records:

```text
rooted directly at source+0x28 and source+0x54
size 0x2C
9 x int32 coeff + u16 scaleCode + u16 unresolved + int32 Kelvin
default/tint are separate source-state fields
```

Do not reuse one structure or decoder for both families.

## Implementation helper

```c
double m10r_rendered_cc_coeff(const M10RRenderedCCRecord *cc, int i) {
    const int shift = 9 - (int)cc->scaleCode;
    const double denom = (double)(1u << shift);
    return (double)cc->coeff[i] / denom;
}
```

Add bounds/validity checks around `scaleCode` in implementation code; the firmware trace here freezes representation, not malformed-input behavior.

## Frozen conclusion

Rendered CC0/CC1 are Kelvin-tagged fixed-point 3x3 color-correction matrices with separate default-data and tint fields.

This closes the v1.24 CC0/CC1 structure task.

## Next

Trace WB/AWB and white-point handling:

1. identify preset / auto-WB source fields;
2. connect Kelvin+tint and x/y to `NeutralToXY`, `SetWhiteXY`, and `MapWhiteMatrix`;
3. map output/remapped RGB gains;
4. follow those gains into B2Y WB gain programming;
5. then trace B2Y CC/gamma/tone.
