# M10-R v2.70E — WORKING1A DEVICE RESULT / TRANSFER1A GATE

Date: 2026-09-10
Status: **WORKING1A retained; one final-transfer discriminator authorized**

## Device evidence

Two device captures from `RENDER1G_WORKING1A_YC2A_MATRIX1A` were reviewed with matching diagnostics:

- warm/mixed-light kitchen frame, recorded Leica-locus CCT about 4202 K;
- cooler bathroom frame, recorded Leica-locus CCT about 6236 K.

Both sidecars prove that the intended placement A/B actually ran:

```text
nonlinearPlacement = M10R_internal_working_RGB_between_CC0_CC1
workingBasisPlacementFix = WORKING1A
cc0WorkingBasisPlacement = pre_MEDIUM_DG
cc1Placement = post_MEDIUM_DG_before_sRGB_OETF
```

The bathroom frame is broadly neutral in walls/door/white clothing, while the kitchen remains warmer and also contains obvious spatially mixed illumination. Therefore WORKING1A does not introduce a global yellow cast and should not be rolled back merely because the warm-scene concern remains.

## New device discriminator: excessive final midtone lift

The two sidecars expose the linear values immediately after CC1 and before the software sRGB OETF.

Kitchen:

```text
preSrgb luma median ~= 0.2927
post-DG median       ~= 4763.7 / 16383
```

Bathroom:

```text
preSrgb luma median ~= 0.4695
post-DG median       ~= 7675.5 / 16383
```

Applying the renderer's textbook sRGB OETF to those pre-sRGB medians produces approximately 0.577 and 0.715 respectively, consistent with the conspicuously lifted delivered JPEGs. Neither frame has tone-coordinate or differential-gamma index overflow. The brightness therefore has a concrete downstream-transfer discriminator rather than an exposure/coordinate-overflow explanation.

## Firmware context

Frozen firmware research already establishes:

- default STILL enables differential gamma and tone;
- default STILL disables interpolation gamma and de-knee;
- differential gamma is itself an exact recovered scalar transfer function with 14-bit output;
- CC0 enters Leica internal working RGB and CC1 exits it to the selected output RGB;
- default STILL output colour space is sRGB.

What is **not** frozen is a separate textbook sRGB OETF after the recovered B2Y nonlinear path. The current Android renderer added such an OETF as an output-coding assumption.

This makes final transfer ownership a legitimate device A/B. It is not a visual EV/tone adjustment.

## Critical isolation constraint: EDGE1A

A naive edit that removes `srgb8()` from the WORKING1A native pixel loop is **not** a clean one-variable test.

The existing experimental EDGE1A pass consumes the already sRGB-coded bitmap, explicitly decodes sRGB to linear for luma/high-frequency processing, then re-encodes affected pixels to sRGB. If the native pixel loop were changed to emit linear-coded bytes while EDGE1A were left unchanged, EDGE1A would decode the wrong domain and the candidate would alter both transfer and edge arithmetic.

Therefore TRANSFER1A must preserve the complete WORKING1A + EDGE1A path and cancel the final sRGB coding only **after** EDGE1A.

## Authorized candidate

```text
RENDER1H_TRANSFER1A
experiment = TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL
```

Pipeline:

```text
source RAW
-> SOURCECM1A / CA9
-> Leica internal working RGB
-> Yc / MEDIUM / DG / LOOK1B
-> CC1
-> existing textbook sRGB OETF
-> existing EDGE1A decode/process/re-encode
-> TRANSFER1A inverse-sRGB full-frame pass
-> JPEG
```

The last pass maps each 8-bit sRGB code through the exact inverse textbook sRGB equation and re-quantizes to 8-bit. This makes the delivered JPEG linear-coded for the diagnostic A/B while keeping every upstream stage, including EDGE1A's input domain, unchanged.

## Deliberate limitation

Because the baseline OETF has already quantized to 8-bit before the inverse pass, this is not a bit-exact reconstruction of an hypothetical no-OETF firmware path. It is a bounded **transfer-cancellation discriminator** only.

Metadata must state:

```text
outputTransferExperiment = TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL
outputTransferPlacement = post_EDGE1A_before_JPEG
working1aNativeSrgbOetfRetainedForEdgeInvariant = true
edgeInputDomainUnchangedFromWorking1A = true
netOutputTransfer = linear_coded_after_inverse_sRGB
outputTransferQuantization = 8bit_sRGB_roundtrip_diagnostic
outputTransferExactHardwareParityClaimed = false
```

## Frozen behavior

Do not change:

```text
SOURCECM1A
RGBORDER1A
CA9 gains / clip
MEDIUM table
DG table
YC2A matrix
LOOK1B relative chroma
WORKING1A CC0/internal/CC1 placement
EDGE1A / SCALE1A / GAIN1A
Y_BLEND = OFF
LF = OFF
TEXTURE = OFF
HDR = OFF
single RAW
12 MP
capture exposure
JPEG quality
```

No WB offset, hue/saturation change, EV change, or tungsten special case is allowed in this candidate.

## Device judgement gate

Compare WORKING1A baseline against TRANSFER1A first in:

1. the same warm/mixed kitchen-type scene;
2. a neutral/cool interior with white surfaces and skin;
3. one daylight/highlight-rich scene if the first two show a useful density correction.

Primary questions:

- Does midtone density move toward the expected M10-R rendering rather than merely becoming underexposed?
- Are skin and white fabrics better separated?
- Are highlights compressed or lost in an implausible way?
- Does warm-scene colour improve, remain independent, or become worse?

Do not build a second transfer curve or tune a gamma exponent until TRANSFER1A is judged.
