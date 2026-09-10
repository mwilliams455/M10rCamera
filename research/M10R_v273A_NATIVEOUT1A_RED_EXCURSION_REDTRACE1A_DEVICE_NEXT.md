# M10-R v2.73A — NATIVEOUT1A red excursion isolated; REDTRACE1A device gate

Date: 2026-09-10

## Device evidence that triggered REDTRACE1A

RENDER1J NATIVEOUT1A device sample `IMG_20260910_173333` preserves the clean transfer architecture (no textbook sRGB OETF, no inverse transfer, EDGE0A) but shows an obvious selective orange/red excursion on illuminated skin.

The sidecar is unusually diagnostic:

- scene CCT: 6615.21 K
- CA9 gains: 1370 / 256 / 464
- neutral-domain clip counts: 0 / 0 / 0
- pre-tone working RGB maxima: R 0.6371, G 0.5290, B 0.4701 (all below 1)
- post-CC1 sampled output (`preSrgb` historical field):
  - R max 1.40224, above-range count 12,391 / 196,608 = 6.30%
  - G max 0.95870, above-range count 0
  - B max 0.99051, above-range count 0
  - luma max 0.90254, above-range count 0

The JPEG itself also piles up only the red channel at the output ceiling while G/B do not. This makes global exposure, luma clipping, and CA9 neutral clipping poor explanations. It is a selective red/output-gamut excursion appearing downstream of the in-range working RGB.

Do not compensate this with global WB/CA9 changes before locating the stage that creates the excursion.

## REDTRACE1A

Branch: `m10r-render1k-redtrace1a-build`
Workflow run: `34503342325`
Workflow head: `0f53fdc47a4ce67edbc774095abd2435f4189e5f`
Result: SUCCESS
Artifact: `M10RCam-RENDER1K-REDTRACE1A-NATIVEOUT1A-debug-apk`
Artifact id: `10162903130`
Artifact ZIP digest: `sha256:fffa526f6405baa9a9da1711461894bcd6a3b9ebe121c3ae60e46eb78b86740e`
APK SHA256 after extraction: `3cb816df6c1d273d501f816a3843dd927cf221634f8e380dd7cba50a0417e4ad`

REDTRACE1A is diagnostics-only. Photographic pixels remain RENDER1J NATIVEOUT1A.

It adds sampled trace points around the unresolved boundary:

`working RGB -> Y/Cb/Cr -> mapped Y + relative chroma -> exact Yc inverse -> CC1 -> direct linear8 output`

It records:

- post-Yc-inverse RGB > 1 counts
- post-CC1 RGB > 1 counts
- red excursions first created by CC1
- red excursions already present after Yc inverse
- red-only post-CC1 excursion count
- negative-blue counts before/after CC1
- mapped Y/Cb/Cr, Y ratio, post-Yc RGB and post-CC1 RGB means for the R>1 subset

## One-shot device decision

Repeat a red-prone skin/fabric scene once with REDTRACE1A and upload JPEG + `_M10R_CAPTURE1B.json`.

- If most post-CC1 R>1 samples have post-Yc R <= 1, CC1/output-gamut handling is the immediate problem.
- If R>1 is already common immediately after Yc inverse, relative chroma preservation / Yc reconstruction is the immediate problem.
- If both are material, investigate the firmware's bounded chroma/gamut handling around the Yc->CC1 boundary rather than applying a scene-wide WB correction.

No colour correction is intentionally applied in REDTRACE1A.