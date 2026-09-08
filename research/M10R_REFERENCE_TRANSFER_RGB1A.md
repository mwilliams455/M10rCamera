M10-R REFERENCE TRANSFER RGB1A — FULL RGB OETF ON/OFF

Branch base: m10r-render-parity1a; promoted upstream highlight policy C.
Upstream held fixed: DNG WhiteLevel clamp -> bilinear Bayer -> CA9 neutral clip -> Leica ColorSpec -> linear sRGB -> TONEDG1B luminance MEDIUM->DG -> shared RGB gain.
Only variable: final standard sRGB OETF ON versus identity/OETF OFF.
Fit freedom: NONE. No exposure, affine, gamma, tone-power, WB or colour fit.
Firmware assets are SHA-gated to the recovered MEDIUM and expanded DG tables.

=== Per-sample scorecard ===
sample 01 identity=True defaults=True align=0.94064
  ON : RGB_RMSE=65.3562 LUMA_RMSE=67.8442 dE76=28.2842 hue=9.3785 sat=0.148590
  OFF: RGB_RMSE=13.8875 LUMA_RMSE=8.8949 dE76=10.4549 hue=7.8856 sat=0.102033
  RGB winner=OFF; highlight RMSE ON/OFF=26.297111462415707/24.11296916477209
sample 02 identity=True defaults=True align=0.94293
  ON : RGB_RMSE=59.6689 LUMA_RMSE=59.6009 dE76=24.1014 hue=12.7040 sat=0.076114
  OFF: RGB_RMSE=14.1562 LUMA_RMSE=7.0708 dE76=12.1908 hue=12.7504 sat=0.115457
  RGB winner=OFF; highlight RMSE ON/OFF=31.031075662749643/13.960144417323876
sample 03 identity=True defaults=True align=0.95575
  ON : RGB_RMSE=91.2054 LUMA_RMSE=90.5956 dE76=39.9964 hue=17.3824 sat=0.291954
  OFF: RGB_RMSE=66.0944 LUMA_RMSE=63.8971 dE76=32.7778 hue=18.6597 sat=0.258699
  RGB winner=OFF; highlight RMSE ON/OFF=66.83511417573038/107.95411750468897
sample 04 identity=True defaults=True align=0.94629
  ON : RGB_RMSE=91.8679 LUMA_RMSE=88.3442 dE76=37.5953 hue=46.7569 sat=0.231994
  OFF: RGB_RMSE=74.7326 LUMA_RMSE=67.9607 dE76=34.7597 hue=47.1185 sat=0.282467
  RGB winner=OFF; highlight RMSE ON/OFF=67.65000629419465/119.78054973562266
sample 05 identity=True defaults=True align=0.93278
  ON : RGB_RMSE=96.7364 LUMA_RMSE=99.3355 dE76=49.9366 hue=22.0753 sat=0.336943
  OFF: RGB_RMSE=80.7383 LUMA_RMSE=84.9741 dE76=43.0820 hue=22.8923 sat=0.287696
  RGB winner=OFF; highlight RMSE ON/OFF=91.7377269526101/134.6427605025329
sample 06 identity=True defaults=True align=0.92768
  ON : RGB_RMSE=90.1539 LUMA_RMSE=93.4596 dE76=44.7576 hue=15.9489 sat=0.293528
  OFF: RGB_RMSE=70.2634 LUMA_RMSE=72.6824 dE76=39.0976 hue=16.8508 sat=0.269712
  RGB winner=OFF; highlight RMSE ON/OFF=68.94703694586221/114.95858758452233

=== Aggregate medians / wins ===
ON medians: encoded_rgb_rmse=90.67965756313339 encoded_rgb_mae=75.86597056386667 luma_rmse=89.46991699413559 luma_mae=75.65862216578358 delta_e76_mean=38.79584466490506 hue_error_deg_mean=16.665664343453408 saturation_error_abs_mean=0.2619740518863223
ON wins: {'encoded_rgb_rmse': 0, 'encoded_rgb_mae': 0, 'luma_rmse': 0, 'luma_mae': 0, 'delta_e76_mean': 0, 'hue_error_deg_mean': 5, 'saturation_error_abs_mean': 2}
ON tonal bins: {'shadow': {'rgb_rmse': 115.84458085806398, 'luma_rmse': 125.29012204730162}, 'midtone': {'rgb_rmse': 74.61826283172331, 'luma_rmse': 72.27126073701854}, 'highlight': {'rgb_rmse': 67.24256023496253, 'luma_rmse': 50.462659527700126}, 'neutral_pixels': {'rgb_rmse': 98.13169694929547, 'luma_rmse': 100.10864491273767}, 'colourful_pixels': {'rgb_rmse': 84.77716427731377, 'luma_rmse': 82.23910835845221}}
ON false-highlight channel clips: 454873
OFF medians: encoded_rgb_rmse=68.1789357344904 encoded_rgb_mae=53.414463094705965 luma_rmse=65.92887459629537 luma_mae=53.30392832984905 delta_e76_mean=33.76873750798376 hue_error_deg_mean=17.755216836147802 saturation_error_abs_mean=0.26420572522540686
OFF wins: {'encoded_rgb_rmse': 6, 'encoded_rgb_mae': 6, 'luma_rmse': 6, 'luma_mae': 6, 'delta_e76_mean': 6, 'hue_error_deg_mean': 1, 'saturation_error_abs_mean': 4}
OFF tonal bins: {'shadow': {'rgb_rmse': 72.49052384180092, 'luma_rmse': 77.59628387147825}, 'midtone': {'rgb_rmse': 63.414028431340085, 'luma_rmse': 57.12877649951331}, 'highlight': {'rgb_rmse': 111.45635254460565, 'luma_rmse': 100.66904630740822}, 'neutral_pixels': {'rgb_rmse': 78.8659470168183, 'luma_rmse': 75.6928685186443}, 'colourful_pixels': {'rgb_rmse': 63.79294031417828, 'luma_rmse': 59.36128045686958}}
OFF false-highlight channel clips: 445203

VERDICT MIXED_FULL_RGB_TRANSFER_EVIDENCE

Interpretation boundary: RGB1A tests the current diagnostic linear-sRGB -> TONEDG1B shared-gain -> transfer placement. It does not prove the firmware B2Y signal coordinate or that JPEG hardware literally consumes linear RGB.
Do not alter m10r-capture1b solely from this run unless OFF wins the broad gate including hue, saturation and highlight guards.
Workflow run id: 34197509286
Analysis input commit: e6c6cf161b0653caf3fae548e8ff0efb378cfa0b
