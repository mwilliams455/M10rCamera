# M10-R v2.72B — EDGE0A device observation + NATIVEOUT1A build success

Date: 2026-09-10

## Device observation from RENDER1I EDGE0A

Two RENDER1I EDGE0A frames were supplied with diagnostics. The brighter first portrait (`IMG_20260910_153626`) is visibly too red/warm in skin compared with the rest of the scene. The darker second portrait (`IMG_20260910_153328`) is less affected.

This does **not** currently look like a simple global WB or stronger-CA9-red-gain problem:

### First / redder frame — 15:36:26
- Leica-locus CCT: 5966.75 K
- CA9 gains: 1198, 256, 478 (R/G gain ratio 4.6797)
- preTone medians: R 0.078857, G 0.073975, B 0.081787
  - median R/G = 1.0660
  - median B/G = 1.1056
- post-CC1 `preSrgb` medians: R 0.446533, G 0.398682, B 0.395264
  - median R/G = 1.1200
  - median B/G = 0.9914
- global-median diagnostic change through nonlinear/reconstruction/CC1:
  - R/G +5.07%
  - B/G -10.33%
- preSrgb >1 fractions:
  - R 2.363%
  - G 0.003%
  - B 7.282%
  - luma709 proxy only 0.001%

### Second / less-red frame — 15:33:28
- Leica-locus CCT: 6222.65 K
- CA9 gains: 1277, 256, 476 (R/G gain ratio 4.9883 — actually higher than the redder frame)
- preTone median R/G = 1.0479, B/G = 0.8802
- post-CC1 preSrgb median R/G = 1.0697, B/G = 0.8564
- global-median diagnostic change:
  - R/G +2.08%
  - B/G -2.71%

These are distribution medians rather than paired-pixel hue measurements, so they are evidence of a downstream colour-balance tendency, not a proof of the exact arithmetic stage. Combined with the image itself (skin/warm colours much more affected than neutral/background areas), the current best hypothesis is a scene/chroma-dependent downstream interaction in Yc reconstruction / relative-chroma scaling / CC1 / gamut handling, not a blanket WB error.

Do not compensate this with a general cooler WB or arbitrary red subtraction yet.

## EDGE0A gate

The supplied EDGE0A photographs show no obvious global density/colour discontinuity or unacceptable softness/halo failure caused by disabling the provisional EDGE1A pass. The user's only explicit issue was the red/warm rendering in the first portrait, which is orthogonal to edge execution.

Therefore EDGE0A is accepted as sufficient to unblock the clean transfer architecture candidate.

## RENDER1J NATIVEOUT1A

Branch:
`m10r-render1j-nativeout1a-build`

Functional patch commit:
`e788cec23dd3630a2a727815265a99b875d23fa8`

Workflow/APK-producing commit:
`769cfa4250a70e216b645fd673e62345868f06a7`

No-op CI trigger commit after workflow registration:
`4bfdf8ed481e16b521ab1f924188f6fb0a8af5d7`

Successful Actions run:
`34490871892`

APK artifact:
`M10RCam-RENDER1J-NATIVEOUT1A-EDGE0A-DIAG1C-SAF1-debug-apk`

Artifact ID:
`10157792307`

Artifact ZIP digest:
`sha256:6e4778035b86b9ada8c7a7cc084947d53d0f37110c3e23238acb8f00d1830cfc`

Extracted APK SHA256:
`41becec1e8e78f6acbf7285795ad71820bff2a9ee3f4b1e03351a018a7a05553`

Exact Photon baseline remains:
`f0e6425d2509fb8ab834d5d3af593183038b778c`

### RENDER1J live photographic path change

Previous EDGE0A/TRANSFER1A output path:

`post-CC1 -> textbook sRGB OETF -> 8-bit -> inverse sRGB full-frame pass -> JPEG`

RENDER1J:

`post-CC1 -> direct clamp/round linear8 -> JPEG`

The old sRGB helper and inverse-transfer native implementation remain resident only as unreachable research controls. EDGE remains bypassed.

Frozen across this candidate:
- source calibration / SOURCECM1A
- target M10-R camera transform
- WB / scene-white solve
- CA9
- WORKING1A placement
- Yc conversion/inverse
- MEDIUM
- differential gamma
- LOOK1B / YC2A structure
- exposure/capture
- 12 MP
- JPEG quality
- single RAW
- HDR OFF

This is not a claim that exact M10-R output colour encoding has been proven.

## Expected device relationship to RENDER1I

The previous numerical quantization sweep showed that direct 8-bit post-CC1 quantization versus the TRANSFER1A sRGB-encode -> 8-bit -> inverse-sRGB -> 8-bit round trip differs by at most 2 code values per channel over [0,1], with mean absolute error about 0.35/255. Therefore RENDER1J should be photographically very close in density to RENDER1I while removing the redundant transfer round trip.

It should **not** cure the red/warm issue. If it does materially change hue, that is a bug/confound and should be investigated before any colour tuning.

## Next device gate

Install RENDER1J and repeat one or both of the current portrait/indoor scenes if possible. Upload JPEG + `_M10R_CAPTURE1B.json`.

Expected diagnostics include:
- `renderLook = RENDER1J_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A`
- `outputTransferExperiment = NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8`
- `textbookSrgbOetfApplied = false`
- `transfer1aInverseExecuted = false`
- `outputTransferSeparatePassExecuted = false`
- `transferRoundTripRemoved = true`
- `nativePixelOutputQuantizer = linear8_post_CC1`
- `edgePassEnabled = false`
- `edgeCallExecuted = false`

## Colour work after NATIVEOUT1A gate

If NATIVEOUT1A preserves the desired density and the red/warm issue remains, start a diagnostic-only colour trace before applying a correction. Proposed next experiment: `REDTRACE1A`.

Instrument paired sampled pixels at:
1. post-CA9 / WORKING1A input,
2. post-Yc reconstruction before CC1,
3. post-CC1,
4. final clamp/gamut boundary.

Record per-pixel chromaticity movement (R/G and B/G or normalized rgb), luma, Cb/Cr and clamp/out-of-range state, with aggregate bins by luma/chroma quadrant. The aim is to determine whether warm/red inflation is introduced by relative-chroma preservation through the large MEDIUM/DG luma gain, by CC1, by matrix/gamut excursions, or by an upstream scene-white transform. Only then make a bounded colour correction.
