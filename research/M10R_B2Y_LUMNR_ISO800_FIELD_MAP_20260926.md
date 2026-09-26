# M10-R B2Y LUMINANCE NR ISO-800 FIELD MAP

Date: 2026-09-26

Branch: `m10r-b2y-offset-crossmodel1a`

## Identity

B2Y record `0x0E` is the firmware **LUM NOISE REDUCTION** control family.

For normal saved STILL at ISO 500 / 640 / 800, M10-R selects ordinal 20:

- payload size: 84 bytes
- SHA256: `0dd3612b9f903c02ec8213999a5ef63acc88cac8bc6c8a13f5d2d092e9bee81b`
- keys:
  - `_B2YMODE:STILL_ISO:500`
  - `_B2YMODE:STILL_ISO:640`
  - `_B2YMODE:STILL_ISO:800`

This is the ISO group used by the two retained September 21 tungsten captures (~ISO 800/820).

## Payload words

Signed 32-bit interpretation:

```
+0x00   1
+0x04   2
+0x08   2
+0x0C   3

+0x10   144
+0x14   324
+0x18   376
+0x1C   612
+0x20   553
+0x24   233

+0x28   2948
+0x2C   851
+0x30   1933
+0x34   -387
+0x38   -531
+0x3C   0

+0x40   1000
+0x44   2000
+0x48   4000
+0x4C   6500
+0x50   16383
```

## Driver packing

IMG-System driver `+0xD3088` programs B2Y page `0x20020900`.

- `+0x00..+0x0C` feed enable/mode fields in register `0x20020940`.
- `+0x10/+0x14` -> low/high 16-bit fields of `0x20020950`.
- `+0x18/+0x1C` -> low/high 16-bit fields of `0x20020954`.
- `+0x20/+0x24` -> low/high 16-bit fields of `0x20020958`.
- `+0x28/+0x2C` -> paired 15-bit fields of `0x20020960`.
- `+0x30/+0x34` -> paired 15-bit fields of `0x20020964`.
- `+0x38/+0x3C` -> paired 15-bit fields of `0x20020968`.
- `+0x40/+0x44` -> low/high 16-bit fields of `0x20020970`.
- `+0x48/+0x4C` -> low/high 16-bit fields of `0x20020974`.
- `+0x50` -> low 16-bit field of `0x20020978`.

The negative payload words at `+0x34` and `+0x38` survive naturally as signed 15-bit two's-complement values after the driver's masks:
- `-387 -> 0x7E7D`
- `-531 -> 0x7DED`

## Interpretation boundary

The record identity and register packing are proven. Exact pixel arithmetic and semantic names of individual fields are not yet proven.

Do not translate this into arbitrary sharpening/denoise sliders.

## Project implication

This is currently the strongest firmware-backed candidate for the separate **detail / skin-texture / noise rendering** mismatch at the ISO used by the bad tungsten captures.

It should be investigated independently from the color/hue problem.
