# M10-R B2Y SATURATION ARITHMETIC1A — research boundary

Date: 2026-09-26

## Proven input facts

Record 0x18 is selected by M10-R STILL saturation keys and programs the B2Y color-difference-suppression block.

For LOW / MEDIUM / HIGH, the only payload differences are six fields:

- +0x10
- +0x14
- +0x18
- +0x1C
- +0x20
- +0x24

The original IMG setter and SAM7 register programmer agree that these are six independent 14-bit fields packed as three register pairs at:

- 0x20021110
- 0x20021114
- 0x20021118

Calibration values:

- LOW = 0x1B34 = 6964
- MEDIUM = 0x2000 = 8192
- HIGH = 0x2666 = 9830
- MONOCHROME = 0 for the same six saturation fields

Ratios relative to MEDIUM:

- LOW = 0.85009765625
- MEDIUM = 1.0
- HIGH = 1.199951171875

This strongly constrains the six fields as saturation-gain lanes with a neutral MEDIUM reference.

## What is NOT yet proven

Do not yet claim:

- exact Q13 multiply arithmetic;
- exact rounding or clipping;
- exact hue/sector name of lane 0..5;
- exact per-pixel lane-selection rule;
- placement relative to CC1, Yc reconstruction, DG, or tone.

Configuration order is not pixel-flow order.

## Exact next task

Recover the hardware arithmetic / lane selection from firmware evidence, in this order:

1. Find all software readers/writers of 0x20021110 / 0x20021114 / 0x20021118 beyond the calibration setter.
2. Search SAM7 control structures and copy/marshal routines for the six-lane vector.
3. Identify any neighboring hue/angle/boundary parameters in the same 0x18 record and map those fields to MMIO.
4. Determine whether those neighboring parameters define six color sectors and whether the six gains are indexed/interpolated by sector.
5. Only if firmware evidence supports it, model the neutral gain as 0x2000 and recover multiply/round/shift/clamp behavior.
6. Build an offline operator first against existing captures; keep Android renderer frozen.

## Renderer freeze

No change to MFM1B, POSTYC1A, WB/source matrices, tone, GAMUT1A, TONECAL1A, JPEG quality, Y_BLEND, or the Android renderer during this pass.
