# M10-R v2.72B — REDTRACE1A closes on CC1; RENDER1L CC1OFF1A device test next

Date: 2026-09-10

## Device evidence — IMG_20260910_174543

RENDER1K REDTRACE1A / NATIVEOUT1A / EDGE0A produced the decisive boundary trace.

- sampleCount: 196608
- post-Yc working RGB > 1: R=815, G=38, B=2250
- post-CC1 RGB > 1: R=4631, G=118, B=2451
- CC1-created R > 1: 3816
- CC1-created share of post-CC1 R > 1: 82.4012%
- post-CC1 red-only > 1: 4586 / 4631 = 99.0283%
- post-CC1 R > 1 fraction: 2.35545%

For the red-excursion subset:

- mean post-Yc working RGB: [0.948514, 0.678684, 0.486001]
- mean post-CC1 RGB: [1.096041, 0.617505, 0.459306]
- mean CC1 delta: approximately [+0.14753, -0.06118, -0.02670]
- mean mapped Y: 0.737254
- mean mapped Cb: -0.141862
- mean mapped Cr: +0.150580
- mean Y ratio: 3.15161

CC1 matrix under test:

```
 1.3895  -0.1693  -0.2202
-0.2288   1.2317  -0.0029
-0.0176  -0.0963   1.1139
```

Red equation:

```
outR = 1.3895*postYcR - 0.1693*postYcG - 0.2202*postYcB
```

## Interpretation

CC1 is the dominant creator of the current warm/red excursion. The near-unity row sums explain why neutrals can remain plausible while chromatic red/warm subjects expand strongly. This is not consistent with treating global WB/CA9 adjustment as the primary fix.

Yc is not fully cleared: 815 red samples and 2250 blue samples are already above 1 before CC1. That is a secondary boundary to revisit after CC1 semantics/domain are resolved.

NATIVEOUT1A remains supported: removing the standalone textbook sRGB transfer did not create the red issue.

## RENDER1L CC1OFF1A positive control

Branch: `m10r-render1l-cc1off1a-build`

APK-producing workflow head: `43f2e1f59e87fba860e6853f78409a1c6f2ce24e`

Actions run: `34504582774` — SUCCESS

Artifact: `M10RCam-RENDER1L-CC1OFF1A-NATIVEOUT1A-debug-apk`

Artifact ID: `10163392280`

Artifact ZIP digest: `sha256:4ef50463b1b221d5abe87ac5e300c2bd139a3180e4d203d19c76f4c7f4bcbc02`

APK SHA256: `481443ac9b40079658556e228093212c9a7248ad591a54ee52025340fa4b5af6`

Exact Photon baseline remains:

`f0e6425d2509fb8ab834d5d3af593183038b778c`

### One photographic variable

RENDER1L changes native photographic publication only:

```
post-Yc exact-inverse working RGB
-> BYPASS DEFAULT_SRGB_CC1
-> direct linear8
-> JPEG
```

The CC1 matrix remains resident. REDTRACE1A still computes the old CC1 output on the sampled diagnostic path as a counterfactual, so the JPEG can bypass CC1 while the JSON reports what CC1 would have done.

Frozen around this test:

- SOURCECM1A / target camera transform
- WB / CA9
- WORKING1A
- MEDIUM then differential gamma
- Yc conversion and exact inverse
- NATIVEOUT1A direct output architecture
- EDGE0A
- exposure/metering
- JPEG quality
- one RAW
- HDR off

This is a positive-control diagnostic, not a claim that final M10-R rendering omits CC1.

## Device gate

Repeat a skin/warm-subject scene similar to IMG_20260910_174543, ideally retaining a saturated cyan/blue object and neutral walls/fabric.

Expected JSON invariants:

- `renderLook = RENDER1L_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A`
- `cc1AppliedToPhotographicPixels = false`
- `cc1CounterfactualRedTraceRetained = true`
- `cc1OffOnlyPhotographicVariable = true`

Decision:

- If skin/warm colour normalizes while neutrals and cyan/blue remain sensible, reconstruct CC1 consumer/domain semantics rather than tuning WB.
- If the bypass removes necessary Leica colour separation or materially damages the image, CC1 is required but is currently applied in the wrong domain/semantics or lacks its paired output/gamut operation.
- After CC1 is resolved, return to the smaller pre-CC1 Yc red/blue excursions.
