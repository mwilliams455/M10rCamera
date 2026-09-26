# M10-R B2Y SATURATION FIELD MAP1A — FROZEN

Date: 2026-09-26

Branch: `m10r-b2y-saturation1a`

Canonical executable firmware for setter mapping:

`M10-R-30.22.23.34-Customer.FW`

SHA256:

`ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

B2Y calibration SHA256:

`ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b`

## Scope

This freeze records firmware-proven calibration selection and original register-programmer behavior for B2Y record `0x18`, named by the IMG selector as:

`color_dif_suppression`

It does not claim the hidden ISP pixel equation.

## 1. M10-R STILL saturation keys

Record `0x18` is selected by exact keys:

- `_B2YMODE:STILL_SATURATION:LOW`
- `_B2YMODE:STILL_SATURATION:MEDIUM`
- `_B2YMODE:STILL_SATURATION:HIGH`
- `_B2YMODE:STILL_SATURATION:MONOCHROME`

For LOW / MEDIUM / HIGH, the 144-byte payloads differ only at six 32-bit word offsets:

`+0x10, +0x14, +0x18, +0x1C, +0x20, +0x24`

Values:

- LOW: `0x1B34` = 6964, repeated six times
- MEDIUM: `0x2000` = 8192, repeated six times
- HIGH: `0x2666` = 9830, repeated six times

Relative to MEDIUM:

- LOW = 6964 / 8192 = 0.85009765625
- MEDIUM = 1.0
- HIGH = 9830 / 8192 = 1.199951171875

This is numerically consistent with a unity-referenced Q13-style scale, but the hardware arithmetic itself remains a separate question.

## 2. Exact original setter packing

IMG-System setter:

`0x420D0770` / section offset `0xD0770`

Normal path is selected with `r1 == 0`; `r0` points to the record payload.

The six saturation words are packed as six independent 14-bit fields:

| Payload | MMIO register | Bit field |
|---|---|---|
| +0x10 | 0x20021110 | bits 0..13 |
| +0x14 | 0x20021110 | bits 16..29 |
| +0x18 | 0x20021114 | bits 0..13 |
| +0x1C | 0x20021114 | bits 16..29 |
| +0x20 | 0x20021118 | bits 0..13 |
| +0x24 | 0x20021118 | bits 16..29 |

Bits 14..15 and 30..31 are preserved by read-modify-write.

Original-setter emulation independently perturbing each MEDIUM word proved that the union of these six fields exactly explains the complete LOW-vs-MEDIUM and HIGH-vs-MEDIUM register delta.

Therefore the LOW/MEDIUM/HIGH saturation distinction is fully isolated to these six 14-bit controls.

## 3. Default MEDIUM common fields

MEDIUM does not reduce to the six unity fields. It also programs common suppression state shared by LOW/MEDIUM/HIGH.

### Four-point sequence

Payload:

- `+0x44 = 20000`
- `+0x48 = 30000`
- `+0x4C = 40000`
- `+0x50 = 50000`

Packing:

- `+0x44` -> high 16 bits of `0x20021140`
- `+0x48` -> low 16 bits of `0x20021144`
- `+0x4C` -> high 16 bits of `0x20021144`
- `+0x50` -> low 16 bits of `0x20021148`

The adjacent `+0x40` field is zero in M10-R LOW/MEDIUM/HIGH and occupies the low 16 bits of `0x20021140`.

The semantic name of this 0/20000/30000/40000/50000 sequence is not yet proven. It must not be silently called a luma curve, chroma curve, or skin threshold without further evidence.

### Full-range paired fields

M10-R MEDIUM contains:

- `+0x54 = 0x7FFF`
- `+0x58 = 0x8000`
- `+0x5C = 0x7FFF`
- `+0x60 = 0x8000`
- `+0x80 = 0x7FFF`
- `+0x84 = 0x8000`
- `+0x88 = 0x7FFF`
- `+0x8C = 0x8000`

These pack into paired register fields at:

- `0x20021150`
- `0x20021154`
- `0x20021164`
- `0x20021168`

Their exact limit/range semantics remain unresolved.

### Control / offset area

Payload `+0x64/+0x68/+0x6C` maps to individual control bits in `0x20021158`.
They are zero for M10-R MEDIUM.

Payload `+0x70/+0x74` maps as two 16-bit values into `0x2002115C`.
For M10-R LOW/MEDIUM/HIGH these are both zero.

Payload `+0x78/+0x7C` maps into two 10-bit fields in `0x20021160`.
They are zero for M10-R MEDIUM.

## 4. Cross-model proof that this is a chroma/color-difference block

M10 Monochrom firmware uses the same B2Y record ID `0x18`, but selects it by toning keys rather than saturation keys:

- `_TONEHUE:OFF_TONESTRENGTH:OFF`
- `_TONEHUE:SEPIA_TONESTRENGTH:WEAK`
- `_TONEHUE:SEPIA_TONESTRENGTH:STRONG`
- `_TONEHUE:BLUE_TONESTRENGTH:WEAK`
- `_TONEHUE:BLUE_TONESTRENGTH:STRONG`
- `_TONEHUE:SELENIUM_TONESTRENGTH:WEAK`
- `_TONEHUE:SELENIUM_TONESTRENGTH:STRONG`

The same `+0x70/+0x74` pair that is zero for M10-R normal colour modes carries signed toning offsets in the Monochrom calibration:

- Sepia weak: `(+180, -240)`
- Sepia strong: `(+384, -640)`
- Blue weak: `(-128, +312)`
- Blue strong: `(-256, +450)`
- Selenium weak: `(0, +128)`
- Selenium strong: `(0, +384)`

This is strong firmware evidence that record `0x18` operates in a two-axis chroma / colour-difference domain.

The exact names/orientation of those two axes are not yet proven, so do not label them Cb/Cr or U/V as a frozen fact yet.

## 5. Implication for the current M10-R renderer

The six LOW/MEDIUM/HIGH controls alone cannot explain the current default MEDIUM skin-colour mismatch because MEDIUM uses the exact unity reference `0x2000` in all six fields.

The higher-value unresolved behavior is the common `color_dif_suppression` state that remains active at MEDIUM, especially:

- the 0/20000/30000/40000/50000 sequence;
- the paired full-range fields;
- the relationship of this block to the YCC/color-difference signal domain.

Do not add a generic Android saturation multiplier as a substitute.

## 6. Current priority

1. Recover any firmware-visible semantics for the six 14-bit lanes and the 0/20000/30000/40000/50000 sequence.
2. If hardware pixel arithmetic is not recoverable from firmware, use genuine matched M10-R DNG/JPEG references as an empirical oracle for the common MEDIUM suppression behavior.
3. Keep the Android renderer frozen until an offline reproduction demonstrates improvement.
4. Keep Y_BLEND / YC CONVERSION and normal-path static CC0/CC1 controls deprioritized based on the completed cross-model invariance tests.

## Provenance

Primary artifacts:

- `research/generated/M10R_B2Y_SATURATION1A.md`
- successful SATURATION1A Actions run `36215899568`
- successful setter ABI Actions run `36215786112`
- `research/generated/M10R_B2Y_CHROMA_KEY_CROSSMODEL1A.md`
- `research/generated/M10R_B2Y_CC_CONTROL_CROSSMODEL1A.md`

