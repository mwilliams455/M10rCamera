# M10-R B2Y CC-CONTROL CROSSMODEL1A

Focused comparison of static B2Y CC0 (0x06) and CC1 (0x0A) records.

## Architectural boundary

Frozen firmware research proves the normal live helper path takes per-frame matrix coefficients from the CA9-rendered runtime CC object. The static B2Y record contributes the enable bit and tail control/limit fields. Whole-record inequality therefore does not by itself prove a different live color transform.

## 0x6 CC0

| Field | M10-R | M10M 2.12.8.0 | M10M 3.21.2.50 | Equal all | M10-R vs latest |
|---|---:|---:|---:|---|---|
| enable_bit0 | 1 | 1 | 1 | True | True |
| tail_2c_low8 | 77 | 77 | 77 | True | True |
| tail_30_low8 | 150 | 150 | 150 | True | True |
| tail_34_low8 | 29 | 29 | 29 | True | True |
| tail_38_u16 | 32768 | 32768 | 32768 | True | True |
| tail_3c_low15 | 32767 | 32767 | 32767 | True | True |

Default/baseline 3x3-looking region equal across all: **False**.
M10-R vs latest Monochrom default region equal: **False**.

## 0xa CC1

| Field | M10-R | M10M 2.12.8.0 | M10M 3.21.2.50 | Equal all | M10-R vs latest |
|---|---:|---:|---:|---|---|
| enable_bit0 | 1 | 1 | 1 | True | True |
| tail_2c_low15 | 32767 | 32767 | 32767 | True | True |
| tail_30_u16 | 32768 | 32768 | 32768 | True | True |
| tail_34_low15 | 32767 | 32767 | 32767 | True | True |
| tail_38_u16 | 32768 | 32768 | 32768 | True | True |
| tail_3c_low15 | 32767 | 32767 | 32767 | True | True |
| tail_40_u16 | 32768 | 32768 | 32768 | True | True |

Default/baseline 3x3-looking region equal across all: **False**.
M10-R vs latest Monochrom default region equal: **False**.

## Decision

**All normal-path static CC0/CC1 fields are invariant across the three inputs.**

The whole-record cross-model differences therefore sit outside the static control/limit fields consumed by the normal live helper path. Deprioritize the static 0x06/0x0A record differences as the explanation for the remaining M10-R skin/color mismatch.
Keep CA9-rendered per-frame CC0/CC1 authoritative and do not add the static matrices as a second transform.

## Next

1. If the normal-path static fields are invariant, move priority to changed chroma-shaping records 0x16/0x18 while keeping tone/DG separate.
2. If any live static field differs, trace only that field into its destination register bits.
3. Keep Y_BLEND 0x0D and YC CONVERSION 0x0C as invariant controls.
4. Make no Android renderer change in this pass.
