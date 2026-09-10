# M10-R v2.72A — RENDER1I EDGE0A BUILD SUCCESS / DEVICE A-B NEXT

Date: 2026-09-10

## Status

RENDER1I EDGE0A built successfully as the bounded next photographic-renderer discriminator from the v2.72 handoff.

Branch:

`m10r-render1i-edge0a-build`

Patch commit:

`38ef2ca2f018752248bfda5d8b67f59691b56008`

APK-producing workflow commit:

`4acdbbcc806d5fbfd87ec541e628b0b6131697be`

Actions run:

`34488884328`

APK artifact:

`M10RCam-RENDER1I-EDGE0A-TRANSFER1A-DIAG1C-SAF1-debug-apk`

Artifact ID:

`10156984226`

GitHub artifact ZIP digest:

`sha256:57df3324379f6ab48e81036376484d303c3bb198da0928edd6a545f23dc5dabd`

Extracted APK SHA256:

`fd95c2a151ce15560370c33c784d1a4220868d73c137f2a6d93fc861a86755f6`

Buildlog artifact ID:

`10156981146`

Buildlog digest:

`sha256:efecf43b97ea3a93b033bc35b2fd7fa5931af6419187679c46d3fa8a5756bbcb`

Photon upstream remains pinned to:

`f0e6425d2509fb8ab834d5d3af593183038b778c`

All workflow stages succeeded, including patch syntax, exact firmware/B2Y extraction, isolation assertions, Android compile, build-log upload and APK upload.

---

## Exact RENDER1I change

RENDER1I is intentionally a one-variable A/B on top of RENDER1H TRANSFER1A.

Frozen path retained:

```text
RAW
→ SOURCECM1A / CA9
→ WORKING1A
→ Yc / MEDIUM / DG / LOOK1B
→ CC1
→ textbook sRGB OETF
→ [EDGE SITE]
→ TRANSFER1A inverse sRGB
→ JPEG
```

RENDER1H executes the current provisional native edge pass at the EDGE SITE.

RENDER1I changes only:

```text
nativeEdgePass(bitmap, edgeIso)
```

from executed to bypassed.

The native EDGE1A implementation and its recovered firmware coefficients/tables remain compiled and resident. They are not rewritten or deleted.

TRANSFER1A remains unchanged. Therefore the diagnostic 8-bit OETF → inverse-OETF round trip remains identical to RENDER1H.

No change was made to:

- capture / metering
- WB / source model / CA9
- matrices / CC0 / CC1 architecture
- WORKING1A placement
- Yc
- MEDIUM
- differential gamma
- LOOK1B
- output transfer experiment
- exposure
- JPEG quality
- 12 MP output
- single RAW
- HDR OFF

Expected RENDER1I diagnostics include:

```text
renderLook = RENDER1I_EDGE0A_TRANSFER1A_WORKING1A_YC2A_MATRIX1A
edgePassEnabled = false
edgeExperiment = EDGE0A_BYPASS_ONLY
edgeCallExecuted = false
edgeAffectedPixels = 0
edgeElapsedMs = 0
edgeScaleTableApplied = false
edgeHfRecordGainApplied = false
outputTransferExperiment = TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL
netOutputTransfer = linear_coded_after_inverse_sRGB
```

---

## Why this is a useful discriminator

Recent control diagnostics show the current edge stage modifies a localized minority of pixels rather than global tone/colour. Examples ranged from roughly 49k–61k affected pixels on earlier 12.6 MP frames and roughly 151k–167k on later TRANSFER1A frames, with edge-stage wall time around 44–61 ms.

Therefore the expected photographic difference is localized detail character: micro-edge contrast, hair/fabric/foliage definition, halos/ringing, and fine texture. A large global density, WB, saturation or hue shift would indicate an implementation problem rather than the intended EDGE0A variable.

---

## Device A/B — combine two gates in one scene

Before replacing RENDER1H, obtain one control frame with the exact TRANSFER1A APK if it is still installed.

Use a scene containing both:

- highlight stress: bright sky/window/white object/reflection
- fine detail: foliage, hair, fabric, text, brick/wood texture, branches

Then install RENDER1I EDGE0A and repeat the composition as closely as practical.

This single pair answers both outstanding questions:

1. Does RENDER1H TRANSFER1A keep highlights acceptable on corrected WORKING1A topology?
2. Does omitting the domain-provisional EDGE1A materially improve or damage photographic detail?

Upload both JPEGs and their M10R sidecar JSONs.

Primary comparison criteria:

```text
global density             should remain essentially unchanged
colour / WB                 should remain essentially unchanged
highlight behavior          should remain essentially unchanged
fine-detail crispness       compare
halos / ringing             compare
hair / foliage texture      compare
skin microtexture           compare if present
JPEG integrity              must remain good
```

Do not use global brightness or colour differences as a reason to tune EDGE0A; those are outside this variable.

---

## NATIVEOUT1A planning result

If EDGE0A is photographically neutral or preferable, the next architecture remains:

```text
RENDER1J_NATIVEOUT1A
WORKING1A core
→ no standalone textbook sRGB OETF
→ no inverse-sRGB diagnostic pass
→ no domain-invalid EDGE1A
→ direct 8-bit JPEG publication
```

The clean implementation can replace the current final native `srgb8(outR/G/B)` quantisation with direct clamp/round of post-CC1 channel values, while removing the full-frame inverse-sRGB diagnostic pass.

A dense numerical sweep of the current diagnostic round trip

```text
direct x
vs
q8(inverse_sRGB(q8(sRGB(x))))
```

shows a maximum discrepancy of 2 output code values and mean absolute discrepancy about 0.35/255 relative to direct 8-bit quantisation over x∈[0,1].

Therefore NATIVEOUT1A is expected to preserve the photographic density of EDGE0A/TRANSFER1A very closely while removing the unnecessary transfer round trip. It should still be built only after the EDGE0A device gate rather than bundled into this A/B.

If EDGE1A proves visibly important, do not silently retain the suspect transfer architecture as a permanent solution. Instead, keep RENDER1H as the photographic control while moving edge/detail toward a proven Leica B2Y/luma/YC domain in the parallel parity track.

---

## Current decision state

```text
CAPTURE1B                     FROZEN
HDR                           OFF
single RAW                    KEEP

WORKING1A                     KEEP
MEDIUM                        KEEP
DG                            KEEP
LOOK1B                        KEEP
CC1 architecture              KEEP

TRANSFER1A                    POSITIVE CONTROL
extra textbook sRGB OETF      STRONGLY DISFAVOURED
EDGE1A                        DOMAIN-PROVISIONAL CONTROL
EDGE0A                        BUILT — DEVICE A/B NEXT

NATIVEOUT1A                   PLANNED, NOT YET BUILT
warm/red issue                SEPARATE; DO NOT TUNE HERE
```
