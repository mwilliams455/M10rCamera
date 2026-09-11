# M10-R RENDER1N YBLEND1A — BUILD SUCCESS, DEVICE VALIDATION NEXT

Date: 2026-09-11

## Status

RENDER1N YBLEND1A is implemented and built successfully as a controlled chroma-reconstruction falsification test on the exact frozen RENDER1M implementation.

This build does **not** claim that the Leica M10-R firmware uses the YBLEND1A midpoint formula. Device validation is still required before any photographic conclusion is drawn.

## Frozen base

- Repository: `mwilliams455/M10rCamera`
- Branch: `m10r-render1n-yblend1a-build`
- Exact RENDER1M implementation base: `b7bab1c06547da766a753290475993e214a0ead4`
- Photon upstream: `f0e6425d2509fb8ab834d5d3af593183038b778c`

The later RENDER1M branch research-note commit was intentionally not used as the renderer base because it did not alter implementation code.

## Provenance

- YBLEND1A functional patch commit: `9b9b7634eace7253093134d41521f5e8ecbb768f`
- APK workflow commit: `e129eca39c54c3267dbf409802833243ad0e9d1a`
- Successful GitHub Actions run: `34553958879`
- Successful job: `103122512197`
- APK/provenance artifact ID: `10181905763`
- Artifact name: `M10RCam-RENDER1N-YBLEND1A-REDTRACE1B-CC1OFF1A-NATIVEOUT1A-debug-apk`
- GitHub artifact metadata digest: `sha256:ff0f0fb21a9242b1a38545852076e794ff914a8f12db64f7f4c9b123558beef7`
- APK SHA256: `19fa5a766120a9eac405324cc36fa25b9a505fd8ffb163e5187a90eaee125910`
- APK filename: `M10RCam-Photon-0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1n-yblend1a-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf126681-debug.apk`

The APK hash above was calculated directly from the APK entry recovered from artifact `10181905763`; it is not the artifact-container digest.

## Exact RENDER1M reconstruction pinned

The live native photographic path was verified before changing it:

```cpp
const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;
const double mappedCb = cb * yRatio;
const double mappedCr = cr * yRatio;
```

The Java diagnostic mirror used the same relationship.

Therefore the previously suspected mechanism was real in the experimental renderer: the full post-DG `mappedY/inputY` luminance gain was also applied to Cb and Cr before the exact YC2A inverse.

## RENDER1N YBLEND1A controlled change

YBLEND1A leaves `mappedY` untouched and changes only the chroma carrier scale:

```text
oldScale = mappedY / inputY
newScale = 0.5 * (1 + oldScale)
```

Equivalent form:

```text
chromaCarrierY = 0.5 * (inputY + mappedY)
newScale = chromaCarrierY / inputY
```

The pre-existing near-zero-Y guard is preserved.

This midpoint is deliberately chosen as an interpretable experiment between:

- absolute Cb/Cr preservation: scale = 1
- RENDER1M relative Cb/Y, Cr/Y preservation: scale = mappedY/inputY

It is **not** promoted as Leica firmware truth.

## Frozen-stage gates passed

The workflow successfully applied the complete frozen chain and verified before Gradle compilation that:

- `mappedY = dy / DG_OUT_MAX` remains unchanged.
- MEDIUM and DG arithmetic remain unchanged.
- The exact YC2A inverse coefficients remain unchanged.
- CC1 remains isolated from photographic pixels (`CC1OFF1A`).
- EDGE remains disabled (`EDGE0A`).
- Direct `linear8` publication remains active (`NATIVEOUT1A`).
- Textbook sRGB OETF / inverse-transfer processing remains disabled.
- WORKING1A remains in place.
- Source/target transforms, CA9/WB and exposure are not modified by this patch.
- Source frame count remains 1.
- HDR remains off.
- The old native `mappedCb/Cr = Cb/Cr * yRatio` lines are absent after YBLEND1A is applied.

Gradle `assembleDebug` then completed successfully and the APK artifact was uploaded.

## Diagnostics added

The sidecar identifies:

```text
chromaReconstructionExperiment = YBLEND1A
yBlend1AExperimentalApplied = true
yBlend1AFirmwareClaim = false
yBlend1ALumaArithmeticChanged = false
yBlend1AMediumDgChanged = false
```

YBLEND1A also retains REDTRACE1B and records sampled old-vs-applied chroma scale, input/mapped Y, original/reconstructed Cb/Cr, and post-reconstruction RGB. Warm and neutral diagnostic classes are based on **pre-map input-relative chroma** so class membership does not move merely because YBLEND1A changed reconstruction.

## Device validation gate

No photographic success is claimed yet.

Test against RENDER1M using the repeat daylight/window-lit problem scene if possible, keeping lens, framing, exposure and capture settings comparable.

Collect:

- RENDER1M JPEG + JSON
- RENDER1N JPEG + JSON
- M10-R reference when available

Evaluate in this order:

1. frame luma / density — should be essentially unchanged;
2. skin warm/red/yellow inflation;
3. neutral/background stability;
4. REDTRACE1B + YBLEND1A old/applied scale diagnostics;
5. out-of-range / clamp behavior.

### Positive gate

If density/Y remains essentially unchanged while the problem-scene warm/red exaggeration decreases, current full relative-chroma reconstruction is implicated. Continue firmware research for the exact Y-blend / six-field chroma-conditioning behavior rather than promoting the midpoint formula as final.

### Negative gate

If red/warm behavior is unchanged, move focus to exact YC2A / CC1-domain / gamut behavior as supported by REDTRACE evidence. If brightness changes materially, reject the test as confounded and inspect the implementation despite the static luma gates.
