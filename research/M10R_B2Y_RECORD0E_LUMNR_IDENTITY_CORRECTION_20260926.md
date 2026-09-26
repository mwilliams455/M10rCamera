# M10-R B2Y RECORD 0x0E IDENTITY CORRECTION — FROZEN

Date: 2026-09-26

## Correction

The older v0.94 selector inventory incorrectly labels both record 0x0E and record 0x02 as `offset`.

Canonical M10-R 30.22.23.34 selector-body evidence resolves the identities:

### Record 0x0E
- Selector: IMG-System `+0x1546E8`
- Lookup: `+0x154744`
- Record ID passed to lookup: `0x0E`
- Embedded selector diagnostic immediately associated with the body:
  `@LUM NOISE REDUCTION     String:%s`
- Actual post-lookup hardware driver: IMG-System `+0xD3088`
- Hardware page written directly: `0x20020900`, offsets approximately `+0x40..+0x78`
- STILL selection is ISO-keyed.
- Therefore record 0x0E is **Luminance Noise Reduction**, not Offset.

### Record 0x02
- Selector: IMG-System `+0x1547C0`
- Lookup: `+0x1547F6`
- Record ID: `0x02`
- Embedded selector diagnostic:
  `@OFFSET    String:%s`
- v0.94 post-lookup driver candidate: IMG-System `+0xD3284`
- Therefore record 0x02 is the actual **Offset** control.

## Record 0x0E hardware structure

Driver `+0xD3088` directly programs B2Y page `0x20020900`.

The 84-byte payload contains:
- enable / small mode fields at payload +0x00..+0x0C;
- six 16-bit parameters at +0x10..+0x24;
- six 15-bit parameters at +0x28..+0x3C (including signed-looking two's-complement values in calibration);
- five 16-bit values at +0x40..+0x50.

For M10-R STILL the last five values are fixed across ISO:
`1000, 2000, 4000, 6500, 16383`.

The two six-value banks vary strongly with ISO.

This structure is consistent with a luminance-dependent NR calibration bank, but the exact consumer equation and meaning of each lane are not yet proven.

## Research boundary

- Keep record 0x0E on the detail/noise track.
- Do not use it as a direct explanation for skin hue without further evidence.
- Continue the color/skin investigation with the actual record 0x02 Offset block.
- Android renderer remains frozen.
