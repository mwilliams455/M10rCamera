# M10-R B2Y SATURATIONFIELDS1A

Basis-value execution of the original Leica 0x18 color-difference-suppression setter.

## Proven field map

| Payload | Register | Field | Width |
|---|---|---|---:|
| 0x10 | 0x20021110 | bits 0..13 | 14 |
| 0x14 | 0x20021110 | bits 16..29 | 14 |
| 0x18 | 0x20021114 | bits 0..13 | 14 |
| 0x1c | 0x20021114 | bits 16..29 | 14 |
| 0x20 | 0x20021118 | bits 0..13 | 14 |
| 0x24 | 0x20021118 | bits 16..29 | 14 |

The six LOW/MEDIUM/HIGH values are three paired 14-bit register coefficients. Values above 0x3FFF are truncated to the low 14 bits by the original setter; 0x4000 encodes as zero and 0xFFFF encodes as 0x3FFF.

MEDIUM uses 0x2000 = 8192 = 2^13; LOW uses 0x1B34 = 6964 (0.85009765625 relative to MEDIUM) and HIGH uses 0x2666 = 9830 (1.199951171875 relative to MEDIUM). This is Q13-compatible calibration structure, but the hardware consumer equation is not yet recovered, so Q13 multiplier semantics are not frozen yet.

## Next boundary

Recover the SAM7/hardware meaning of the three coefficient pairs and constrain their pixel-stage placement relative to CC1/Yc. Do not add an Android chroma multiplier solely from the numeric pattern.
