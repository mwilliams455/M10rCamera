# M10-R B2Y RECORD 0x0E IDENTITY CORRECTION — LUMINANCE NR

Date: 2026-09-26

Branch: `m10r-b2y-offset-crossmodel1a`

## Corrected identity

Earlier selector inventory labeled record `0x0E` as `offset`.

Canonical M10-R 30.22.23.34 executable evidence corrects that interpretation.

Selector function `IMG-System +0x1546E8`:
- looks up B2Y record ID `0x0E`;
- is immediately associated with diagnostic string `@LUM NOISE REDUCTION     String:%s`;
- passes the selected payload to driver `IMG-System +0xD3088`.

Driver `+0xD3088` directly programs B2Y MMIO page `0x20020900`.

Therefore:

**record 0x0E = B2Y luminance-noise-reduction calibration/control family.**

It must no longer be treated as a color-offset candidate.

## Key selection

CROSSMODEL1A proved record 0x0E is selected directly by STILL ISO.

All 33 common STILL ISO keys differ between M10-R and M10 Monochrom.

M10-R groups ISO keys into progressively stronger calibration payloads. Examples:

- ISO 100/160/200 -> first M10-R payload group
- ISO 250/320/400 -> next group
- ISO 500/640/800 -> next group
- ISO 1000/1250/1600 -> next group
- ISO 2000/2500/3200 -> next group
- ISO 4000/5000/6400 -> next group
- ISO 8000/10000/12500 -> next group
- ISO 16000/20000/25000/32000 -> next group
- ISO 40000+ -> highest group

Representative first numeric fields rise strongly with ISO.

## Driver geometry

Driver `+0xD3088` programs page `0x20020900`.

The payload controls:
- enable/control fields in register `0x20020940`;
- multiple paired 16-bit fields across `0x20020950..0x20020958`;
- several 15-bit/16-bit paired fields across `0x20020960..0x20020968`;
- more paired 16-bit fields across `0x20020970..0x20020978`.

This is a substantial ISO-dependent luminance-processing block, not a simple scalar.

## Project implication

Record 0x0E is now a strong candidate for the current **detail / skin texture / noise-rendering** mismatch, particularly at elevated ISO.

It is not, by itself, a strong explanation for the remaining skin hue / tungsten color mismatch.

The two issues should be investigated separately:

1. **Detail/noise:** recover and reproduce M10-R record-0x0E luminance NR behavior.
2. **Color/skin hue:** continue searching the model-specific color/chroma stages; do not force record 0x0E into that role.

## Renderer boundary

No Android renderer changes are made by this correction.
