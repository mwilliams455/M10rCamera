# M10-R PHOTOAUDIT1A — actual same-RAW photographic audit

Original native colour/tone core on genuine M10-R RAW data. Matrix-only target-domain DNG adapter; NOT an end-to-end Android Camera2 frontend equivalence claim.

Six Photography Blog original same-shot DNG/JPEG pairs. Identity is checked independently by camera serial, unique image ID, time and exposure fields. Reference firmware differs from the extracted-table firmware.

## Original native core results

| Scene | Split | ISO | Condition | Patches | L* MAE | a*b* error | Delta E76 |
|---|---|---:|---|---:|---:|---:|---:|
| 01 | development | 320 | target_native | 2133 | 2.047 | 5.473 | 6.045 |
| 01 | development | 320 | white_normalized_control | 2133 | 3.224 | 5.138 | 6.295 |
| 02 | held_out | 640 | target_native | 5993 | 2.676 | 2.903 | 4.156 |
| 02 | held_out | 640 | white_normalized_control | 5993 | 4.205 | 2.821 | 5.302 |
| 03 | development | 100 | target_native | 5368 | 2.658 | 7.907 | 8.639 |
| 03 | development | 100 | white_normalized_control | 5346 | 4.360 | 7.293 | 8.947 |
| 04 | held_out | 100 | target_native | 2593 | 2.460 | 3.518 | 4.707 |
| 04 | held_out | 100 | white_normalized_control | 2593 | 4.046 | 3.356 | 5.754 |
| 05 | development | 100 | target_native | 2177 | 1.923 | 10.861 | 11.088 |
| 05 | development | 100 | white_normalized_control | 2177 | 3.286 | 9.915 | 10.505 |
| 06 | held_out | 100 | target_native | 4494 | 2.479 | 11.696 | 12.051 |
| 06 | held_out | 100 | white_normalized_control | 4494 | 3.993 | 10.771 | 11.606 |

## Held-out tone-only diagnostic

Training uses only neutral patches from 01/03/05, equal total scene weights, a monotonic 5-L* knot curve and the documented identity prior. No per-scene exposure or white-balance fit. 02/04/06 are never used for fitting. The correction changes L* only before an explicit RGB gamut conversion.

### target_native
Held-out scene-equal L* MAE: 2.539 -> 1.481; 3/3 wins. Delta E76: 6.971 -> 6.442.
NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.

### white_normalized_control
Held-out scene-equal L* MAE: 4.081 -> 2.431; 3/3 wins. Delta E76: 7.554 -> 6.564.
NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.

## Limitations

- References are from firmware 10.20.27.20; current tables are extracted from 30.22.23.34.
- No phone metering or shutter/ISO policy evaluated. RAW exposure and recorded camera WB held fixed.
- No DNG GainMap was supplied by these metadata exports; no lens-shading correction added. Centre-region sensitivity must be checked before target attribution.
- Reference JPEGs and native output have different demosaic, optical/lens corrections and sharpening. Flat patches reduce but do not eliminate those confounds.
- L* residual is an empirical diagnostic fitted to three scenes, not recovered firmware arithmetic or an approved app change.
- Target-native and white-normalized source-adapter conditions are both reported; normalization sensitivity prevents a full-pipeline attribution.

No APK produced, no photographic baseline promotion, no firmware-exactness claim. Results come from the CI run stated in results.json; no claim of independent local rerun. Native arithmetic is checked against an independently expressed array implementation; image formation uses the original C++ function.

Reference source: https://www.photographyblog.com/reviews/leica_m10_r_review
Frozen baseline: a66b73cc339ebcb863d345c7a9ee7ff631fc86f0
Audit source commit: 77eba535b6491823e48d09355e3b97e530d55d75
Actions run: 35519696178
