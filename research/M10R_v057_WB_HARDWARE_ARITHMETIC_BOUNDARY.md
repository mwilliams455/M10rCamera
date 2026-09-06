# M10-R v0.57 — WB hardware arithmetic boundary

## Status

FROZEN for **WB configuration ABI and static-firmware boundary only**.

This note does **not** freeze:
- the exact per-pixel WB multiply formula,
- rounding mode,
- saturation/clipping behavior,
- sensor-slot scan order,
- or the physical WB→CC0 routing order inside B2Y hardware.

The renderer/application remains unchanged.

## Correction to v0.55 interpretation

v0.55 correctly proved that `0x2002008c` and `0x20020090` do not feed a downstream **CPU arithmetic consumer**. Their observed CPU-side uses are same-register read/modify/write programming sequences.

That result was initially interpreted too broadly as evidence that these words were merely configuration/control and not a direct gain path.

v0.56 resolves that distinction: the CPU is programming the **hardware data plane itself**. The absence of a software multiply is expected because the live arithmetic is performed inside B2Y hardware.

Therefore preserve the narrow v0.55 statement:

> no downstream CPU pixel-multiply consumer was proven for these MMIO words.

Reject the broader obsolete statement:

> these MMIO words are not WB gain inputs.

## Canonical WB provenance

Previously frozen firmware evidence establishes the canonical per-frame WB triplet as signed 16-bit values at input `+0xF4/+0xF6/+0xF8`, interpreted as R/G/B and independently clamped to `[1,2000]`.

The CA9 AsShotNeutral bridge uses:

`ASN_c = 256.0 / gain_c`

and the reverse diagnostic reconstruction uses the corresponding `round(256 / ASN_c)` relationship.

For the current real M10-R DNG fixture this reconstructs approximately:

`[R,G,B] = [697,256,442]`

so code `256` is the firmware unity-gain point. Numerically this is Q8-like:

- R: `697/256 = 2.72265625`
- G: `256/256 = 1.0`
- B: `442/256 = 1.7265625`

`Q8-like` describes the proven numeric encoding/unity point; it does **not** by itself prove the hidden hardware multiply/round operation.

## Direct B2Y WB consumer

The central B2Y selector at `0x42154F84` reads the local B2Y runtime halfwords:

- local `+0x04` → `r0` = R
- local `+0x06` → `r1` = G
- local `+0x08` → `r2` = B

and immediately calls `0x420D4380`.

v0.56 maps and verifies that helper against the hash-verified firmware. Its embedded diagnostics name the routine:

- `drv_img_b2y_set_wbgain1`
- `drv_img_b2y_set_wbgain2`

The helper validates the supplied values against an exclusive `0x800` ceiling and packs their low 11 bits into the B2Y register page based at `0x20020080`.

## Proven register ABI

### `0x2002008c`

- bits `10:0`   = R `[10:0]`
- bits `26:16`  = B `[10:0]`

### `0x20020090`

- bits `10:0`   = G `[10:0]`
- bits `26:16`  = G `[10:0]`

Therefore the hardware channel vector programmed by the helper is:

`R, G, G, B`

with four 11-bit gain slots.

The upstream canonical range `[1,2000]` fits the helper's `<2048` requirement exactly.

This register-slot vector must **not** be silently equated with raw sensor scan order. The genuine M10-R RAW fixture is GBRG; the B2Y register layout is a color-channel ABI, not proof of pixel raster order.

## Independent programmer corroboration

The older B2Y programmer trace independently programs the same layout from a dedicated three-halfword WB object:

- first halfword → `+0x0c[10:0]`
- second halfword → both `+0x10[10:0]` and `+0x10[26:16]`
- third halfword → `+0x0c[26:16]`

This matches the R/G/G/B packing of `0x420D4380`.

## Static-firmware stage boundary

v0.57 inventories the named B2Y driver surface using candidate-seeded Thumb xrefs rather than a fragile long linear disassembly.

Recovered named WB routine:

- function `0x420D4380`
- owns B2Y MMIO page `0x20020080`
- strings `drv_img_b2y_set_wbgain1/2`

The bounded named-driver inventory also exposes operation-mode, tone-control, link/SDRAM and related B2Y APIs, but no named `demosaic`, `debayer`, or `bayer` routing routine providing an explicit software-visible WB→pixel-stage edge.

Final static verdict:

`WB_DRIVER_PROVEN_NO_NAMED_BAYER_ROUTING_EDGE`

This means static firmware has reached a **hardware arithmetic boundary** analogous to the separately established tone boundary. Firmware proves what gain values are programmed and exactly where, but does not expose the live B2Y pixel multiplier's internal rounding/saturation implementation.

## Stage-order constraint

Existing stage-order work already treats direct WB as a distinct B2Y front-end hardware path and freezes CC0 as the entrance into Leica's internal RGB working space for first-parity architecture.

However, programmer order, register address order, or function-call order are not physical routing proof. No new mux/source field has been recovered here.

Therefore:

- direct WB is proven as an independent hardware gain path,
- rendered CC matrices are separately proven to reach B2Y,
- physical WB→CC0 routing remains unproven at mux-level,
- first-parity software may model WB as the front-end candidate path, but must label hidden arithmetic/order assumptions explicitly.

## What is still unknown

Static firmware does **not** establish which of these pixel formulas B2Y uses, for example:

- truncation: `(sample * gain) >> 8`
- nearest: `(sample * gain + 0x80) >> 8`
- another internal precision/rounding rule

Nor does static firmware establish whether saturation occurs:

- immediately after WB,
- at a wider hidden accumulator width,
- at a later B2Y stage,
- or only at an output boundary.

Do not freeze a `0x3fff` post-WB clamp merely because the RAW WhiteLevel is 15000; gains above unity can create values beyond the sensor-domain white level and B2Y may retain internal headroom.

## Consequence for the next experiment

The previous six-pair JPEG/DNG stage-order experiment used a linear camera-space **green-channel** proxy. That proxy is poorly suited to testing this newly proven direct WB path because green's recovered gain is normally near the unity code 256.

The next empirical diagnostic must therefore be color-sensitive:

1. reuse the already verified same-capture JPEG/DNG pairs,
2. use R and B information as well as G,
3. apply the exact recovered integer WB triplet as an explicit candidate stage,
4. compare at least truncation vs nearest arithmetic,
5. keep clipping/headroom candidates explicit rather than silently freezing one,
6. emphasize colored and near-highlight samples where R/B gain differences cannot be absorbed trivially,
7. keep all renderer behavior frozen while evaluating the diagnostic offline.

## Frozen conclusions

- `0x2002008c` / `0x20020090` are B2Y WB gain registers.
- helper `0x420D4380` is the direct named B2Y WB programmer.
- input ABI is `r0=R`, `r1=G`, `r2=B`.
- register vector is `R,G,G,B` in four 11-bit fields.
- canonical WB range is `[1,2000]`, with exclusive hardware ceiling 2048.
- code 256 is unity; numeric encoding is Q8-like.
- no downstream CPU pixel multiply is expected or required for this hardware path.
- exact live per-pixel arithmetic, clipping, and physical mux order remain hardware-boundary unknowns.

## Next phase

`v0.58 — color-sensitive empirical WB arithmetic/headroom test`

Start from the six already validated same-capture JPEG/DNG pairs. Replace the green-only proxy with a color-sensitive model that makes the proven R/G/B WB triplet observable, while holding the frozen Leica rendering stages unchanged.
