# M10-R Y_BLEND REFERENCE1A — CONSTANT-k FAMILY FALSIFICATION

Date: 2026-09-26

Successful analysis run: `36222566705`

Artifact: `M10R-YBLEND-REFERENCE1A` (ID `10898904272`)

The run's analysis, rendering, scoring and aggregation all completed successfully. Only the final Git push was rejected because the branch had advanced with the separate Y_BLEND hardware-boundary note.

## Scope

Six verified same-capture default Leica M10-R JPEG+DNG pairs were evaluated.

Offline candidate family only:

```
chromaScale = 1 + k * (mappedY / inputY - 1)
```

with `k = 0.00 .. 1.00` in `0.05` steps.

Fixed diagnostic pipeline:

```
CA9 neutral guard
-> Leica internal RGB
-> exact YC conversion record 0x0C
-> MEDIUM
-> DG(Y)
-> constant-k Cb/Cr carrier family
-> exact YC inverse
-> corrected factory sRGB CC1
-> sRGB publication
```

No Android renderer change and no claim that this is Leica's hardware equation.

## Per-scene best k

| Sample | Colourful RGB | Saturation | dE76 | Hue | RGB | Luma |
|---|---:|---:|---:|---:|---:|---:|
| 01 | 1.00 | 1.00 | 0.75 | 0.80 | 1.00 | 1.00 |
| 02 | 1.00 | 1.00 | 0.65 | 0.90 | 1.00 | 1.00 |
| 03 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 0.00 |
| 04 | 1.00 | 0.70 | 0.15 | 1.00 | 1.00 | 0.00 |
| 05 | 1.00 | 0.90 | 0.45 | 1.00 | 1.00 | 0.00 |
| 06 | 1.00 | 1.00 | 0.60 | 1.00 | 1.00 | 0.00 |

## Aggregate

- Colourful-pixel RGB RMSE: best `k=1.00`; current `k=0.35` is **7.035%** above the best. Scene best = `1.00` for 6/6.
- Saturation error: best `k=0.95`; current `0.35` is **37.971%** above the best. Scene range `0.70..1.00`.
- dE76: best `k=0.40`; current `0.35` is only **0.082%** above the best. Scene range `0.15..0.75`.
- Hue error: best `k=1.00`; current `0.35` is **6.256%** above the best. Scene range `0.80..1.00`.
- Full encoded RGB RMSE: best `k=1.00`; current `0.35` is **4.269%** above the best. Scene best = `1.00` for 6/6.
- Luma RMSE: best `k=0.00`; current `0.35` is only **0.485%** above the best; scene optima split between 0 and 1.

Workflow verdict: `CONSTANT_K_FAMILY_NOT_SUPPORTED_BY_SIX_SCENES`.

## Interpretation

The important fact is that the color-specific metrics all push strongly toward the upper edge of the tested range. This rejects `k=0.35` as a good photographic explanation in this simplified reference pipeline.

It does **not** justify setting `k=1.0` in the Android renderer:

1. the optimum reaches the test boundary rather than an interior solution;
2. the reference harness intentionally omits later empirical production stages;
3. most importantly, Leica MEDIUM `0x18` Chroma Suppress has six unity-like saturation fields **plus additional fixed nonzero fields**, so a large k can compensate for an omitted B2Y chroma stage.

Therefore do not extend or tune k until the full default `0x18` block has been separated into generic user-saturation behavior versus model-specific base chroma shaping.

## Next

Compare the color-family `0x18` payloads and exact saturation keys across:

- M10-R `30.22.23.34`
- M10 `3.22.23.38`
- M10-P `4.22.23.34`

If all non-user-saturation fields are invariant, `0x18` is generic user saturation and cannot explain M10-R-specific skin color. If M10-R differs while the same LOW/MEDIUM/HIGH/MONOCHROME key semantics remain, those fixed fields become a high-value true model-specific candidate.

Renderer remains frozen.
