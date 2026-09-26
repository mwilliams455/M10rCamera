# M10-R Y_BLEND HARDWARE-BOUNDARY1A

Date: 2026-09-26

## Scope

This note closes the current static-firmware route for recovering Y_BLEND pixel arithmetic.

It does not claim the hardware equation is solved and makes no renderer change.

## Proven software path

Normal still Y_BLEND:

```
B2Y record 0x0D
[0, 32, 0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF]
    -> IMG selector direct pointer handoff
    -> D4480 / SAM7 YCC register programmer
    -> 0x2002092C / 0x20020930 / 0x20020934
    -> B2Y hardware
```

D4480 field mapping is proven:

- p0 -> 0x2002092C bits 0..5
- p1 -> 0x2002092C bits 8..13
- p2/p3 -> 0x20020930 low/high paired fields
- p4/p5 -> 0x20020934 low/high paired fields

Normal register image:

- 0x2002092C = 0x00002000
- 0x20020930 = 0x3FFF3FFF
- 0x20020934 = 0x3FFF3FFF

## Static-consumer census

The page 0x20020900 firmware census identifies the YCC/SAM7 programmer as the sole owner reaching the watched +0x2C/+0x30/+0x34 scope.

No software routine that consumes those register values as pixel data has been found.

No exact-address literal consumer exists; the registers are reached only as base-plus-offset MMIO.

The firmware therefore exposes register configuration but not the downstream B2Y datapath arithmetic.

## Cross-version / cross-model discriminator

Y_BLEND record 0x0D is byte-identical across:

- M10-R 20.20.47.37
- M10-R 30.22.11.52
- M10-R 30.22.23.34
- M10 Monochrom 2.12.8.0
- M10 Monochrom 3.21.2.50

YC CONVERSION 0x0C and the relevant SAM7 implementation are likewise invariant in the tested cross-model set.

Meanwhile the surrounding B2Y calibration demonstrably changes, so the invariant result is discriminating rather than a failed comparison.

## Related B2Y color-control elimination

Record-by-record and key-aware cross-model work further constrains the remaining color problem:

- static CC0 0x06 / CC1 0x0A whole records differ, but all normal-path static control/tail fields are invariant; live matrices remain CA9-rendered per-frame CC0/CC1;
- 0x16 color_dif_lpf is exact-equal for common saved-still ISO keys;
- 0x18 color_dif_suppression is Leica's user saturation/monochrome block, not a hidden M10-R skin matrix;
- 0x13/0x14/0x15/0x17 did not emerge as differing saved-still model-color controls in CROSSMODEL-DIFF1A.

Therefore there is no remaining evidence that another static M10-R-only B2Y color record should replace the unresolved generic Y_BLEND operator.

## Renderer consequence

POSTYC1A still carries:

```
chromaScale = 1 + 0.35 * (mappedY/inputY - 1)
```

This is explicitly empirical and is not Leica firmware arithmetic.

Do not:
- tune k again on-device;
- infer p1=32 means 0.5 or any Q-format;
- call 0x3FFF min/max/clip/scale without evidence;
- add a skin HSL correction to compensate.

## Next evidence source

Because static firmware has reached the hardware boundary, the next valid step is photographic model discrimination using verified same-capture M10-R JPEG+DNG pairs.

REFERENCE1A tests the entire current constant-k family offline. Its purpose is to answer:

**Can one global k explain the reference chroma behavior across independent scenes at all?**

- If no: retire the constant-k family and search for a nonlinear / bounded / signal-dependent operator.
- If yes: use the resulting cluster only as an empirical constraint; it still does not decode p1=32.

Android renderer, MFM1B, POSTYC1A placement, WB/source matrices, tone, GAMUT1A, TONECAL1A, JPEG quality and single-RAW behavior remain frozen.
