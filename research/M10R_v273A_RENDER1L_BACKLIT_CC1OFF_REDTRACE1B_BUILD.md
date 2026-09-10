# M10R v273A — RENDER1L BACKLIT CC1OFF1A RESULT / REDTRACE1B BUILD

Date: 2026-09-10
Project: Leica M10-R -> Xiaomi 15 Ultra / PhotonCamera

## Device input

Sidecar: `IMG_20260910_175820_M10R_CAPTURE1B.json`
Render identity: `RENDER1L_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A`
Scene: strongly backlit indoor portrait against a bright window.

Frozen capture facts:
- single RAW = true
- HDR = false
- stacking = false
- 4096x3072 render source / 3072x4096 published orientation
- JPEG + DNG + sidecar all saved

## Photographic observation

The previously obvious fluorescent orange/red skin failure is substantially reduced with CC1 bypassed.

Do NOT promote CC1OFF1A as final architecture from this observation. CC1 is a neutral-axis-preserving working/output matrix (row sums ~= 1), so bypassing it publishes Leica internal working RGB as though it were output RGB. That can reduce visible warm expansion while still being colorimetrically wrong.

The subject is also strongly backlit and darker than the bright-window background, so this is not a controlled lighting match to the earlier front-lit portrait.

## Why REDTRACE1A is confounded on this frame

REDTRACE1A:
- sampleCount = 196608
- postYcWorkingAbove1RGB = [26437,2532,677]
- postCc1Above1RGB = [27330,3030,699]
- cc1CreatedRedAbove1Count = 894
- CC1-created share of post-CC1 R>1 = 3.2711%
- post-CC1 red-only share = 96.5569%

But the red-excursion subset has:
- meanMappedY = 0.998256
- meanPostYc RGB = [0.999703,0.998907,0.991146]
- meanPostCc1 RGB = [1.001722,0.998748,0.990248]

Therefore the global R>1 population is dominated by near-white window/highlight pixels, not the portrait skin/midtones.

Additional highlight evidence:
- neutralDomainClipCounts = [1666868,1703149,1655594]
- post-DG p90/p99 are essentially at the 14-bit ceiling (~16379)

Conclusion: global R>1 is not a reliable CC1 skin/warm discriminator across scene types.

## Architectural status

Keep these separate:

1. `CC1OFF1A` is a positive control, not a final output path.
2. Stored CC1 placement after internal-working nonlinear processing remains firmware-supported.
3. Exact CC consumer MAC / shift / rounding / saturation behavior remains unresolved in the firmware research lineage.
4. No subjective red, skin, WB, or saturation correction should be added.

## REDTRACE1B

Branch:
`m10r-render1m-redtrace1b-build`

Patch commit:
`859378cfb343e14df8533aacb4c422785a321f32`

Workflow commit / APK-producing SHA:
`b7bab1c06547da766a753290475993e214a0ead4`

Actions run:
`34505982958`

Result:
SUCCESS

Artifact:
`M10RCam-RENDER1M-REDTRACE1B-CC1OFF1A-NATIVEOUT1A-debug-apk`

Artifact ID:
`10163953907`

Artifact ZIP digest:
`sha256:ed5eb714816583a2e175fb10d8b76e31dc51787c40e0e1ab09ac64f75cf0d4fa`

Extracted APK SHA256:
`c7066b7b8daafa1b6b4a213aadb853608188e81750e17c00fe3f85242068f7e0`

## REDTRACE1B design

Photographic pixels remain arithmetic-equivalent to RENDER1L CC1OFF1A.

Counterfactual CC1 remains diagnostic-only at sampling stride 64.

Samples are split into four mapped-Y bins:
- shadow: Y < 0.18
- lowMid: 0.18 <= Y < 0.40
- midHigh: 0.40 <= Y < 0.75
- highlight: Y >= 0.75

Each bin is reported for:
- all samples
- warm relative chroma: mappedY > 0.03 and mappedCr/mappedY >= 0.04
- near-neutral relative chroma: mappedY > 0.03, |mappedCb/mappedY| <= 0.02, |mappedCr/mappedY| <= 0.02

Per subset record:
- sample count
- post-Yc R>1
- counterfactual post-CC1 R>1
- CC1-created R>1
- post-CC1 red-only R>1
- post-CC1 B<0
- mean mapped Y / relative Cb / relative Cr
- mean post-Yc RGB
- mean counterfactual post-CC1 RGB
- mean CC1 delta RGB

## Next device gate

Use RENDER1M REDTRACE1B and provide JPEG + `_M10R_CAPTURE1B.json`.

Best first capture: a normally/front-lit portrait similar to the earlier orange/red example. A second repeat of the backlit-window scene is useful as the highlight control.

Primary question:
Does counterfactual CC1 show a strong positive-R / negative-G/B displacement specifically in warm shadow/midtone subsets while near-neutral controls remain close and highlights explain the global clipping population?

If yes: reopen the exact CC1 consumer/domain/output handling boundary; do not remove CC1 and do not tune skin.

If no: investigate the upstream Yc/working-space chroma reconstruction before changing colour.
