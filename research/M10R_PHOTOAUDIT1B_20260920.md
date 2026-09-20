# M10-R PHOTOAUDIT1B — actual same-RAW photographic audit

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
| 03 | development | 100 | white_normalized_control | 5368 | 4.338 | 7.304 | 8.940 |
| 04 | held_out | 100 | target_native | 2593 | 2.460 | 3.518 | 4.707 |
| 04 | held_out | 100 | white_normalized_control | 2593 | 4.046 | 3.356 | 5.754 |
| 05 | development | 100 | target_native | 2177 | 1.923 | 10.861 | 11.088 |
| 05 | development | 100 | white_normalized_control | 2177 | 3.286 | 9.915 | 10.505 |
| 06 | held_out | 100 | target_native | 4494 | 2.479 | 11.696 | 12.051 |
| 06 | held_out | 100 | white_normalized_control | 4494 | 3.993 | 10.771 | 11.606 |

## Held-out tone-only diagnostic

Training uses only neutral patches from 01/03/05, equal total scene weights, a monotonic 5-L* knot curve and the documented identity prior. No per-scene exposure or white-balance fit. 02/04/06 are never used for fitting. The correction is applied to every original output pixel, converted to bounded RGB and rounded to uint8; those actual corrected pixels are then measured with the unchanged reference patch mask.

### target_native
Held-out scene-equal L* MAE: 2.539 -> 1.460; 3/3 wins. Delta E76: 6.971 -> 6.436.
NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.

### white_normalized_control
Held-out scene-equal L* MAE: 4.081 -> 2.437; 3/3 wins. Delta E76: 7.554 -> 6.583.
NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.

## Limitations

- References are from firmware 10.20.27.20; current tables are extracted from 30.22.23.34.
- No phone metering or shutter/ISO policy evaluated. RAW exposure and recorded camera WB held fixed.
- No DNG GainMap was supplied by these metadata exports; no lens-shading correction added. Central-region sensitivity is reported below.
- Reference JPEGs and native output have different demosaic, optical/lens corrections and sharpening. Flat patches reduce but do not eliminate those confounds.
- L* residual is an empirical diagnostic fitted to three scenes, not recovered firmware arithmetic or an approved app change.
- Target-native and white-normalized source-adapter conditions are both reported; normalization sensitivity prevents a full-pipeline attribution.

No APK produced, no photographic baseline promotion, no firmware-exactness claim. Results come from the CI run stated in results.json; no claim of independent local rerun. Native arithmetic is checked against an independently expressed array implementation; image formation uses the original C++ function.

Reference source: https://www.photographyblog.com/reviews/leica_m10_r_review
Frozen baseline: a66b73cc339ebcb863d345c7a9ee7ff631fc86f0
Audit source commit: be0ca7671dc79fa88d997f463511784223b58136
Actions run: 35520127954


## Actual-pixel validation and central-crop sensitivity

The original native function is unchanged. OpenCV 4.13.0 is pinned; a distinct-RGB constant-CFA fixture passes. Registration is shared across all conditions and candidates. Initial correction-of-patch-mean scores from PHOTOAUDIT1A are superseded. No firmware clipping candidate was inserted.

| Held-out scene | Baseline L* MAE | Tone diagnostic L* MAE | Central baseline L* MAE | Central diagnostic L* MAE | Chromatic hue error (degrees) | Chroma ratio |
|---|---:|---:|---:|---:|---:|---:|
| 02 | 2.676 | 1.348 | 2.490 | 0.980 | 5.44 | 0.807 |
| 04 | 2.460 | 1.390 | 2.064 | 1.148 | 2.44 | 0.720 |
| 06 | 2.479 | 1.642 | 3.393 | 2.264 | 3.62 | 0.687 |

The colour columns describe baseline chromatic patches (reference C* >=20, rendered C* >=5). Ratio <1 means lower chroma, not necessarily a correctable global saturation deficit.

## Validation metadata

```json
{
  "validation": {
    "cfa_fixture": "GBRG CFA -> RGB channels [10000,20000,30000] exact interior",
    "candidate_scoring": "Pixelwise L* correction -> bounded RGB -> round to uint8 -> patch RGB means -> Lab -> errors",
    "registration": "Reference registration solved on target_native then reused unchanged by normalization control and tone candidate; 6-sample-pixel search radius",
    "center_region": "Central half-width by half-height of aligned common raster; same global fitted curve, no refit",
    "old_measurement_superseded": "PHOTOAUDIT1A initial correction-of-patch-mean scores are superseded by actual-RGB-pixel scores",
    "baseline_original_cpp_sha256": "27d42e3090435732bba6331380d2110227d3b713f59d3917b659d19cbea0f934"
  },
  "tone_diagnostic": {
    "target_native": {
      "fit": {
        "neutral_training_patches": 1260,
        "scene_weighting": "equal total weight per training scene",
        "knots_input_L": [
          0.0,
          5.0,
          10.0,
          15.0,
          20.0,
          25.0,
          30.0,
          35.0,
          40.0,
          45.0,
          50.0,
          55.0,
          60.0,
          65.0,
          70.0,
          75.0,
          80.0,
          85.0,
          90.0,
          95.0,
          100.0
        ],
        "knots_output_L": [
          0.0,
          4.198970438470228,
          8.431332865065967,
          12.687950621535123,
          18.210020948243773,
          22.634037479619746,
          27.38559283941166,
          35.0,
          39.08826643195841,
          44.830648932658455,
          49.32575066085636,
          55.0,
          59.100672805326404,
          63.46146360819147,
          68.13342102222532,
          73.6100954446556,
          78.67744679831279,
          82.99904969547816,
          88.12088353314114,
          95.0,
          100.0
        ],
        "identity_prior_per_bin": 0.01
      },
      "heldout_scene_equal_mean_L_mae_baseline": 2.538583670660399,
      "heldout_scene_equal_mean_L_mae_candidate": 1.4602291153933507,
      "heldout_L_mae_relative_reduction": 0.4247859023636279,
      "heldout_scene_equal_mean_DE76_baseline": 6.971257195232583,
      "heldout_scene_equal_mean_DE76_candidate": 6.43562774154717,
      "heldout_L_wins": 3,
      "promotion": "NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.",
      "central_heldout": {
        "baseline_L_mae": 2.6488959789425532,
        "candidate_L_mae": 1.4641945940469405,
        "L_wins": 3,
        "baseline_ab_error": 6.7871048917403485,
        "candidate_ab_error": 6.8061763989806545
      }
    },
    "white_normalized_control": {
      "fit": {
        "neutral_training_patches": 1260,
        "scene_weighting": "equal total weight per training scene",
        "knots_input_L": [
          0.0,
          5.0,
          10.0,
          15.0,
          20.0,
          25.0,
          30.0,
          35.0,
          40.0,
          45.0,
          50.0,
          55.0,
          60.0,
          65.0,
          70.0,
          75.0,
          80.0,
          85.0,
          90.0,
          95.0,
          100.0
        ],
        "knots_output_L": [
          0.0,
          3.9631864090664566,
          7.907366813112506,
          12.001980514541064,
          16.9753626062529,
          21.84075814991877,
          26.43248252891132,
          33.82962019395566,
          39.08826643195841,
          45.0,
          48.883578046482405,
          54.35575366260061,
          59.154402383008794,
          62.80221243734445,
          67.53972532101095,
          73.25000496463325,
          77.91687297780408,
          82.59690881021582,
          87.47577231027384,
          95.0,
          100.0
        ],
        "identity_prior_per_bin": 0.01
      },
      "heldout_scene_equal_mean_L_mae_baseline": 4.081297069331755,
      "heldout_scene_equal_mean_L_mae_candidate": 2.436662743875879,
      "heldout_L_mae_relative_reduction": 0.4029685410097231,
      "heldout_scene_equal_mean_DE76_baseline": 7.553907922641483,
      "heldout_scene_equal_mean_DE76_candidate": 6.583436754286897,
      "heldout_L_wins": 3,
      "promotion": "NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.",
      "central_heldout": {
        "baseline_L_mae": 4.121928714724227,
        "candidate_L_mae": 2.367652951875426,
        "L_wins": 3,
        "baseline_ab_error": 6.361630756232138,
        "candidate_ab_error": 6.369307115265443
      }
    }
  }
}
```
