# M10-R v2.70B — Device WB gate numeric closure

Date: 2026-09-10
Status: RESEARCH-ONLY / NO PIXEL CHANGE
Parent process checkpoint: `research/M10R_v270A_BASELINE_REGISTRY_RETURN_TO_DEVICE_GATE.md`

## 0. Purpose

Apply the v2.70A return-to-device decision gate to the newly available device sidecar:

`IMG_20260910_071015_M10R_CAPTURE1B.json`

This checkpoint records only what the sidecar and frozen build lineage prove. No renderer arithmetic is changed and no APK is built.

---

## 1. Capture identity and baseline validity

The sidecar reports:

```text
captureMode = single_frame_raw
sourceFrameCount = 1
hdrEnabled = false
stackingEnabled = false
renderLook = RENDER1F_YC2A_MATRIX1A
status = success
```

The diagnostics writer is:

```text
DIAG1C_SAF_ABSPATH
```

This is acceptable for the v2.70A gate. The DIAG1C SAF1 build is derived from the same frozen RENDER1F / YC2A / MATRIX1A chain and its patch changes only diagnostics persistence. Its workflow explicitly applies the frozen RENDER1F chain through DIAG1A, then overlays the DIAG1C SAF writer, with a provenance assertion that rendering arithmetic is unchanged.

Therefore the frame is valid for the v2.70A numeric WB gate even though its diagnostics transport is DIAG1C rather than the earlier DIAG1A writer.

---

## 2. Relevant device diagnostics

```text
sourceSensorNeutral = [0.6025390625, 1.0, 0.3876953125]
sourceInterpolationFactor = 0.5780919564532268
sceneWhiteX = 0.40806447946570246
sceneWhiteY = 0.4329644967886003
sceneCctKelvinLeicaLocus = 3747.056631039559 K
m10rSyntheticAsShotNeutral = [0.3520715101905391, 1.0, 0.4085187552669846]
m10rCa9Gains = [727, 256, 627]
neutralDomainClipCounts = [0, 0, 0]
sourceWhiteLevelClipCount = 0
```

Source transform:

```text
[ 1.0538088083,  0.1097463369,  0.5661473274 ]
[ 0.3630470335,  0.7578125000,  0.0604534000 ]
[-0.0645773560, -0.4513603449,  3.3922789097 ]
```

---

## 3. v2.70A check A — neutral-domain clipping

Observed:

```text
neutralDomainClipCounts = [0, 0, 0]
sourceWhiteLevelClipCount = 0
```

Verdict:

```text
T2_NEUTRAL_CLIPPING_CAUSE = REJECTED_FOR_THIS_FRAME
```

There is no measured CA9 neutral-domain clip event in the diagnostic sample and no source-white clipping. Therefore a broad tungsten/yellow midtone cast, if visually present in the matching JPEG, cannot be explained by the renderer's current CA9 neutral clamp for this frame.

This does not claim that Leica hardware can never clip WB-domain values. It only rejects the current neutral-clipping explanation for this captured frame.

---

## 4. v2.70A check B — reciprocal-256 ownership

Recovered architectural relation:

```text
WB_q8 ~= round(256 / AsShotNeutral)
```

For the recorded synthetic M10-R neutral:

```text
R: 256 / 0.3520715101905391 = 727.1250089547 -> 727
G: 256 / 1.0                = 256.0000000000 -> 256
B: 256 / 0.4085187552669846 = 626.6542152580 -> 627
```

Recorded:

```text
m10rCa9Gains = [727, 256, 627]
```

Exact integer closure:

```text
round(256 / m10rSyntheticAsShotNeutral) == m10rCa9Gains
```

Residual products:

```text
727 * 0.3520715101905391 = 255.9559879085
256 * 1.0                = 256.0000000000
627 * 0.4085187552669846 = 256.1412595524
```

Verdict:

```text
RECIPROCAL256_OWNERSHIP = PROVEN_CONSISTENT_FOR_THIS_FRAME
T3_WB_REPRESENTATION_MISMATCH = REJECTED_FOR_THIS_FRAME
```

The current synthetic neutral and integer CA9 gains are mutually consistent with the recovered Leica reciprocal-Q8 relation. There is no evidence in this sidecar of an internal neutral/gain representation mismatch that would justify adding another WB stage.

---

## 5. Signal-headroom context

The diagnostic sample enters the nonlinear stage with substantial headroom:

```text
preTone max R = 0.5512651
preTone max G = 0.5523016
preTone max B = 0.4877810
```

No tone-input or DG-index high clipping was recorded.

After tone/DG/chroma reconstruction, pre-sRGB out-of-range counts are small and downstream:

```text
R above 1.0 = 554 / 196608 = 0.2818%
G above 1.0 =   0 / 196608 = 0.0000%
B above 1.0 =  29 / 196608 = 0.0148%
```

These downstream excursions may matter to localized highlight colour, but they do not rescue the rejected upstream neutral-clipping hypothesis for a broad midtone tungsten cast.

---

## 6. Decision-tree state after this frame

Two v2.70A branches are now eliminated numerically for this capture:

```text
T2 = REJECTED_FOR_THIS_FRAME
T3 = REJECTED_FOR_THIS_FRAME
```

The remaining fork is purely photographic because the matching JPEG is required to determine whether the original yellow/amber concern still reproduces:

### If the matching JPEG still shows the broad tungsten cast

Classify as:

```text
T1
```

Then the next renderer experiment is one bounded A/B at the:

```text
ColorSpec / D50 -> fixed rendered working-basis seam
```

Do not reopen generic B2Y consumer arithmetic first.

### If the matching JPEG does not show the concern

Classify as:

```text
T4
```

Then freeze the WB path and move to the next visible discrepancy, preferably daylight colour separation / saturation / highlight behaviour.

---

## 7. What is not authorized yet

```text
NEW_APK = NO
NEW_WB_GAIN_STAGE = NO
CA9_CLIP_FIX = NO
GENERIC_B2Y_TRACE = NO
Y_BLEND_CHANGE = NO
TONE_DG_CHANGE = NO
EDGE_CHANGE = NO
```

The only missing discriminator is the matching rendered JPEG (or an explicit visual confirmation that this exact frame still exhibits the yellow/amber concern).

---

## 8. Current verdict codes

```text
DEVICE_GATE_CAPTURE_FOUND = TRUE
DIAG1C_PIXEL_EQUIVALENT_TO_FROZEN_RENDER_CHAIN = PROVEN_BY_BUILD_PATCH
SINGLE_RAW_HDR_OFF = PROVEN
SOURCE_WHITE_CLIP = ZERO
NEUTRAL_DOMAIN_CLIP = ZERO
RECIPROCAL256_SYNTHETIC_ASN_TO_CA9 = EXACT_INTEGER_CLOSURE
T2_NEUTRAL_CLIPPING = REJECTED_FOR_THIS_FRAME
T3_WB_REPRESENTATION_MISMATCH = REJECTED_FOR_THIS_FRAME
T1_VS_T4 = WAITING_FOR_MATCHING_JPEG_VISUAL_DISCRIMINATOR
NEW_APK_BEFORE_VISUAL_DISCRIMINATOR = NO
```
