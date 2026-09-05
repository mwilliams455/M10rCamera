# M10R PROJECT HANDOFF v2.42 — CFA DECODE PIXEL-EXACT / v0.4 DEMOSAIC NEXT

Date: 2026-09-05  
Repo: `mwilliams455/M10rCamera`  
Primary branch: `m10r-color-science-trace`  
Baseline head before this handoff: `8197fea519a2edfe52e23eb99e8fb0cb1403288f`

## Current state

The project has crossed the RAW-ingest boundary. The Android diagnostic app can open a Leica DNG, parse TIFF/DNG metadata, find the CFA RAW IFD, decode Leica compression `7` / SOF3 lossless-JPEG, reconstruct the complete Bayer CFA, and report deterministic RAW statistics and a CFA SHA-256.

The current APK deliberately stops before black/white normalization, demosaic, and rendered color.

## Validated APK baseline

Current test APK: `M10RDiagnostic-v0.3-cfa-decode-debug.apk`

v2.42 workflow run: `33967551763`

All gates passed:
- full-DNG Java RAW decode
- Android unit tests
- APK assembly
- APK verification
- artifact upload

APK SHA-256:
`99048f55964bb06cbf0dafcce201cbbfc0fe219c25c82c4b9919a71dd79263a7`

Actions artifact:
`M10RDiagnostic-v0.3-cfa-decode-debug-apk`

## Lossless-JPEG decoder — validated/frozen boundary

A genuine public M10-R DNG was used to characterize and validate the RAW stream.

Fixture: `leica_m10_r_01.dng`

Fixture SHA-256:
`b1ca50cac49347ec8b977de62b636b3cea193c8f41125ef1588c6b0159d716b9`

Observed Leica SOF3 profile:
- RAW: `7872 x 5208`
- TIFF compression: `7`
- bits tag: `16`
- one CFA RAW strip
- photometric: `32803`
- JPEG marker: `FFC3`
- JPEG precision: `14`
- JPEG frame: `3936 x 5208`
- components: `2`
- predictor (`Ss`): `1`
- point transform (`Pt`): `0`
- one DC Huffman table
- two interleaved components reconstruct one 7872-sample Bayer row

Pixel-exact comparison against rawpy / LibRaw:
- shape: `(5208, 7872)`
- reference SHA-256 LE-u16: `27814cbc80f92d23d7b975d4833f70525f35bc52917d992b35d0a899829a097a`
- Java SHA-256 LE-u16: `27814cbc80f92d23d7b975d4833f70525f35bc52917d992b35d0a899829a097a`
- `mismatch_count = 0`
- `max_abs_diff = 0`
- min/max: `0 / 16383`

Decision: `PIXEL_EXACT`

Do not reopen compression=7 unless a future Leica file exposes a genuinely different JPEG profile.

## User's real M10-R v0.3 test — SUCCESS

The user selected a true 40.9 MP M10-R DNG on-device.

Metadata:
- TIFF little-endian, 4 IFDs
- RAW IFD `7872 x 5208`
- bits `16`
- compression `7`
- photometric `32803`
- one strip
- payload approx `52,529,946` bytes
- first offset `2,275,262`
- AsShotNeutral `[0.3672883788, 1.000000000, 0.5791855204]`
- illuminants `17 / 21`
- BlackLevel `[0.0]`
- WhiteLevel `[15000.0]`
- ActiveArea missing
- CFA repeat `[2,2]`
- CFA pattern `[1,2,0,1]`

DNG CFA IDs are `0=R, 1=G, 2=B`, therefore `[1,2,0,1]` is:

```text
G B
R G
```

Resolved CFA: **GBRG**.

This is critical: v0.4 demosaic and diagnostics MUST be CFA-pattern-aware and MUST NOT assume RGGB.

User M10-R ColorMatrix1:

```text
[[ 0.71240234, -0.25000000, -0.04345703],
 [-0.57373047,  1.55224609,  0.35961914],
 [-0.10961914,  0.29223633,  0.77441406]]
```

User M10-R ColorMatrix2:

```text
[[ 0.48779297, -0.12866211, -0.04858398],
 [-0.58398438,  1.37011719,  0.22070313],
 [-0.18041992,  0.33691406,  0.52514648]]
```

Decoded CFA:
- `7872 x 5208`
- 1 strip
- `40,997,376` samples
- SOF3 precision `14`
- predictor `1`
- Pt `0`
- min `0`
- max `16383`
- mean `729.788957`
- CFA SHA-256 LE-u16: `a752849fc83dd4df5f9b27656d2475b0c201966d7e6514e55cedf61441c7e2be`

Status: `DECODER STATUS: PIXELS DECODED`

Current v0.3 output labels plane means as `RGGB`; that label is not trustworthy for this file because the actual CFA is GBRG. Treat those values as quadrant-slot means only until v0.4 fixes the interpretation.

## Normalization boundary

The SOF3 stream is 14-bit, so encoded values can reach `16383`, but the DNG explicitly says:

`WhiteLevel = 15000`

Use the DNG white level as the primary photographic normalization boundary, not the encoded ceiling.

Primary v0.4 formula:

```text
normalized = clamp((sample - blackLevel) / (whiteLevel - blackLevel), 0, 1)
```

For the tested M10-R file:

```text
blackLevel = 0
whiteLevel = 15000
```

Do NOT simply divide by 16383 in the first renderer. Treat `15000..16383` as encoding/sensor headroom unless later Leica evidence proves otherwise.

## AsShotNeutral → CA9 gains

Current first-parity reconstruction remains:

```text
gain[channel] = round(256 / AsShotNeutral[channel])
```

For the user's true M10-R DNG this gives approximately:

`[697, 256, 442]`

Evidence status remains extremely strong empirical parity, not direct DNG-writer ownership proof.

## Color-science state already frozen/constrained

Do not restart these without contradictory evidence:

- DNG CM1/CM2 and the rendered profile matrices are the same calibration values in fixed-rational vs double form.
- Default STILL output color space is sRGB.
- CC0 maps camera color into Leica's internal ProPhoto-like working RGB.
- CC1 maps the working RGB into the selected output RGB; default is sRGB.
- Leica NeutralToXY: D50 start, `1e-7` convergence threshold, 15-pass bound, pass-14 averaging fallback.
- Dual-illuminant interpolation is reciprocal-temperature based.
- Bradford adaptation path recovered.
- Rendered-CC quantization recovered.
- Rendered-CC rounding is half-away-from-zero before signed clamp.
- Default de-knee disabled.
- Default interpolation gamma disabled.
- Tone enabled.
- Differential gamma enabled.
- Default contrast/tone is MEDIUM.
- First-parity empirical renderer order is **TONE MEDIUM → Differential Gamma**.
- Tone TBL0/TBL1 are alternate banks of one tone stage and are byte-identical in this firmware.

## Important unresolved boundaries

Keep these explicit:

1. Complete B2Y hardware mux/routing is not directly proven. Do not infer physical pixel order from programmer/write order.
2. Exact nonlinear live-signal normalization into the tone/DG domains still needs final validation.
3. Tone arithmetic rounding remains separate from the now-proven CC quantizer rounding.
4. v0.3 channel/plane labels are hard-coded and wrong for the tested GBRG file.

## Immediate next build — v0.4

Goal: **first trustworthy visible preview from a genuine M10-R RAW using our own decoder.**

### v0.4A — pattern-aware CFA diagnostics

Resolve all four Bayer patterns:

```text
[0,1,1,2] = RGGB
[1,0,2,1] = GRBG
[1,2,0,1] = GBRG
[2,1,1,0] = BGGR
```

Report:
- resolved CFA name
- raw quadrant means
- correctly interpreted R/G1/G2/B means
- sample counts
- normalized means

### v0.4B — black/white normalization

Use DNG BlackLevel and WhiteLevel. Keep encoded max separately in diagnostics.

Support scalar values now, but structure code so repeated/per-channel black levels can be added later.

ActiveArea is missing in the tested file, so preserve the full CFA initially.

### v0.4C — reference demosaic

Implement a deterministic pattern-aware **bilinear demosaic** first.

Priorities:
- correct channel placement
- correct geometry/orientation
- deterministic output
- process off the UI thread
- report processing time
- reduced preview is acceptable for display, but preserve the full-resolution RAW path

Do not start with a complex production demosaic.

### v0.4D — sensor-sanity preview

First visual path:

```text
decoded CFA
→ DNG black/white normalization
→ pattern-aware bilinear demosaic
→ simple diagnostic neutral/WB preview transform
→ display gamma / sRGB preview
```

This is diagnostic only. It validates CFA orientation, normalization, demosaic, exposure and broad color direction.

### v0.4E — prepare separate Leica candidate render

After the sensor preview is sane, keep a second path for:

```text
DNG ASN + CM1/CM2 + illuminants
→ recovered CA9 ColorSpec
→ CC0
→ recovered default nonlinear path
→ CC1 / sRGB
→ display
```

Do not independently apply WB twice if CC0 already incorporates the recovered Leica gain/white state.

Keep the sensor-sanity preview and Leica candidate render distinct until parity is validated.

## Validation order

Use the same true M10-R DNG from the successful v0.3 test.

Required checkpoints:
1. decoder SHA remains `a752849fc83dd4df5f9b27656d2475b0c201966d7e6514e55cedf61441c7e2be`
2. CFA resolves as `GBRG`
3. normalized min/max are sensible
4. orientation is correct
5. no red/blue swap
6. no alternating-green-row defect
7. highlight normalization respects WhiteLevel `15000`
8. basic preview looks photographically plausible
9. only then enable the Leica ColorSpec/nonlinear candidate path

If the neutral preview is wrong, debug in this order:

```text
CFA pattern
→ strip geometry
→ black/white normalization
→ demosaic
→ orientation
→ WB
→ matrix/color science
```

The lossless-JPEG decoder should be treated as frozen unless the CFA SHA changes.

## Resume instruction

Start from:

**v0.3 RAW decode is validated on a true M10-R DNG. Do not revisit compression=7. Implement v0.4 pattern-aware normalization + reference Bayer demosaic + first sensor-sanity preview.**

Primary real M10-R validation fixture from the user's phone:

```text
RAW        7872 x 5208
CFA        GBRG
Black      0
White      15000
ASN        [0.3672883788, 1.0, 0.5791855204]
CA9 gains  approx [697, 256, 442]
CFA SHA    a752849fc83dd4df5f9b27656d2475b0c201966d7e6514e55cedf61441c7e2be
```

Do not hard-code RGGB.
Do not normalize by 16383 merely because SOF3 is 14-bit.
Do not merge the simple sensor preview and recovered Leica render until demosaic/orientation passes.

Immediate milestone:

**FIRST VISIBLE M10-R RAW PREVIEW FROM OUR OWN DECODER.**
