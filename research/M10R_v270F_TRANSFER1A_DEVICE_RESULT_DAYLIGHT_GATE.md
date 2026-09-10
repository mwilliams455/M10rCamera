# M10-R v2.70F — TRANSFER1A DEVICE RESULT / DAYLIGHT GATE

Date: 2026-09-10
Branch: `m10r-render1h-transfer1a-build`
Status: **TRANSFER1A positive; daylight/highlight-rich validation remains before architectural promotion**

## Device captures reviewed

Two `RENDER1H_TRANSFER1A_WORKING1A_YC2A_MATRIX1A` JPEG + JSON pairs were reviewed:

1. `IMG_20260910_101441`
   - Leica-locus CCT: ~4712 K
   - edge ISO: 347
   - pre-sRGB luma median: ~0.4319
   - post-DG median: ~7067.6 / 16383
   - no tone-coordinate or DG-index clipping

2. `IMG_20260910_101315`
   - Leica-locus CCT: ~3931 K
   - edge ISO: 229
   - pre-sRGB luma median: ~0.5095
   - post-DG median: ~8363.5 / 16383
   - no tone-coordinate or DG-index clipping

Both sidecars prove that the intended diagnostic transfer cancellation executed:

```text
renderLook = RENDER1H_TRANSFER1A_WORKING1A_YC2A_MATRIX1A
outputTransferExperiment = TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL
outputTransferPlacement = post_EDGE1A_before_JPEG
working1aNativeSrgbOetfRetainedForEdgeInvariant = true
edgeInputDomainUnchangedFromWorking1A = true
netOutputTransfer = linear_coded_after_inverse_sRGB
outputTransferQuantization = 8bit_sRGB_roundtrip_diagnostic
```

## Device result

The delivered JPEG medians closely track the pre-sRGB linear medians, which is the expected consequence of a successful inverse-sRGB cancellation. The prior WORKING1A presentation had conspicuous final midtone lift from the added textbook sRGB OETF. The TRANSFER1A outputs restore substantially denser midtones and blacks without requiring an EV, WB, tone-table, DG-table, matrix, or exposure change.

Visual judgement from the two supplied frames:

- the ~4712 K portrait no longer has the washed/veiled appearance produced by the extra final OETF; hair, wood, skin, and clothing regain useful density and separation;
- the ~3931 K warm/mixed-light portrait also gains needed density, but a strong orange/yellow illuminated region remains and is more clearly exposed as a separate colour/gamut problem rather than a transfer problem.

Therefore:

```text
TRANSFER1A_DIRECTION = POSITIVE
EXTRA_TEXTBOOK_SRGB_OETF_AFTER_RECOVERED_B2Y_NONLINEAR = STRONGLY_SUSPECTED_WRONG
TRANSFER1A_8BIT_INVERSE_PASS = DIAGNOSTIC_ONLY / NOT_PRODUCTION_ARCHITECTURE
```

## Important remaining colour discriminator

The warm ~3931 K frame has substantial red output excursion before the final transfer stage:

```text
preSrgb R aboveExpected = 14927 / 196608 sampled pixels
preSrgb G aboveExpected = 7 / 196608
preSrgb B aboveExpected = 0 / 196608
```

The ~4712 K frame is milder but still has:

```text
preSrgb R aboveExpected = 4477 / 196608 sampled pixels
```

Neither frame has tone-coordinate or DG-index overflow. Thus the visible warm/orange clipping is not evidence against TRANSFER1A. It points downstream/upstream in colour-space/WB/chroma handling around CC1/working-space output, and must be investigated separately.

## Why no immediate TRANSFER1B build

TRANSFER1A deliberately leaves the existing EDGE1A decode/process/re-encode behavior untouched and cancels the software OETF only after the edge pass. That isolates transfer ownership, but costs an 8-bit round trip.

A production no-extra-OETF path cannot simply delete `srgb8()` while leaving EDGE1A untouched, because EDGE1A currently assumes sRGB-coded input and explicitly decodes it. The correct production architecture therefore needs the edge/output-stage domain clarified or moved before removing the round trip.

Do not build a second arbitrary gamma/exponent candidate.

## Immediate next gate

Take one daylight/highlight-rich scene with the same TRANSFER1A APK and upload JPEG + JSON.

Judge:

- sky/window/highlight roll-off;
- white fabric/specular separation;
- whether midtone density remains photographic rather than simply dark;
- whether highlight colour clips implausibly;
- whether the transfer result remains clearly preferable to a reconstructed WORKING1A+OETF presentation.

If daylight passes, freeze the architectural conclusion that the current extra textbook sRGB OETF is not part of first-parity output handling, then continue firmware/renderer work on the correct edge/output domain rather than tuning a replacement display gamma.

## Frozen during daylight gate

Do not change:

```text
SOURCECM1A
RGBORDER1A
CA9 gains / neutral clip
MEDIUM table
DG table
YC2A
LOOK1B relative chroma
WORKING1A placement
EDGE1A / SCALE1A / GAIN1A
Y_BLEND OFF
TEXTURE OFF
LF OFF
HDR OFF
single RAW
12 MP
capture exposure
JPEG quality
```
