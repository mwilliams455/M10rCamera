M10-R REFERENCE TRANSFER RGB1B — FULL RGB DOMAIN PLACEMENT

Base: RGB1A result branch; live m10r-capture1b remains untouched.
Frozen upstream: DNG WhiteLevel clamp -> bilinear Bayer -> CA9 neutral clip -> Leica ColorSpec -> linear sRGB.
Nonlinear assets: exact SHA-gated MEDIUM -> Differential Gamma, fixed 14-bit coordinate mapping, shared-gain chroma preservation.
Fit freedom: NONE. No exposure, affine, gamma, tone-power, WB or colour fit.
Encoded domain means bounded standard sRGB code values derived from the same linear-sRGB pixel.

Modes:
  LL_OETF: linear luma -> MEDIUM/DG -> gain linear RGB -> sRGB OETF (RGB1A ON)
  LL_IDENTITY: linear luma -> MEDIUM/DG -> gain linear RGB -> identity (RGB1A OFF control)
  LE_IDENTITY: linear luma -> MEDIUM/DG -> gain encoded RGB -> identity
  EL_OETF: encoded luma -> MEDIUM/DG -> gain linear RGB -> sRGB OETF
  EE_IDENTITY: encoded luma -> MEDIUM/DG -> gain encoded RGB -> identity

=== Per-sample core ranking ===
sample 01 identity=True defaults=True align=0.94064
  LL_IDENTITY RGB=13.8875 Y=8.8949 dE76=10.4549 hue=7.8856 sat=0.102033 hi=24.11296916477209
  EL_OETF RGB=37.6022 Y=37.9481 dE76=16.2973 hue=9.3127 sat=0.137422 hi=15.273003082421779
  LL_OETF RGB=65.3562 Y=67.8442 dE76=28.2842 hue=9.3785 sat=0.148590 hi=26.297111462415707
  EE_IDENTITY RGB=101.0246 Y=107.6644 dE76=45.0693 hue=9.7327 sat=0.122661 hi=27.583899523333404
  LE_IDENTITY RGB=160.3698 Y=159.6537 dE76=65.4746 hue=39.1041 sat=0.313515 hi=51.47546767002201
sample 02 identity=True defaults=True align=0.94293
  LL_IDENTITY RGB=14.1562 Y=7.0708 dE76=12.1908 hue=12.7504 sat=0.115457 hi=13.960144417323876
  EL_OETF RGB=28.8193 Y=27.8881 dE76=11.5113 hue=12.7116 sat=0.073253 hi=15.741589565545992
  LL_OETF RGB=59.6689 Y=59.6009 dE76=24.1014 hue=12.7040 sat=0.076114 hi=31.031075662749643
  EE_IDENTITY RGB=89.5937 Y=88.5539 dE76=34.7154 hue=13.0005 sat=0.070283 hi=32.73282189103752
  LE_IDENTITY RGB=134.3307 Y=131.9813 dE76=50.1987 hue=38.0371 sat=0.212162 hi=59.2134567073526
sample 03 identity=True defaults=True align=0.95575
  EL_OETF RGB=60.5794 Y=57.1296 dE76=28.8840 hue=17.3862 sat=0.289707 hi=88.2838912442571
  LL_IDENTITY RGB=66.0944 Y=63.8971 dE76=32.7778 hue=18.6597 sat=0.258699 hi=107.95411750468897
  LL_OETF RGB=91.2054 Y=90.5956 dE76=39.9964 hue=17.3824 sat=0.291954 hi=66.83511417573038
  EE_IDENTITY RGB=112.6812 Y=114.9270 dE76=52.5653 hue=17.3008 sat=0.288021 hi=58.122082044074006
  LE_IDENTITY RGB=162.7306 Y=160.1928 dE76=67.1035 hue=31.0032 sat=0.432330 hi=69.19001766310829
sample 04 identity=True defaults=True align=0.94629
  EL_OETF RGB=64.4365 Y=58.9335 dE76=28.1468 hue=47.0279 sat=0.232734 hi=95.74721992647919
  LL_IDENTITY RGB=74.7326 Y=67.9607 dE76=34.7597 hue=47.1185 sat=0.282467 hi=119.78054973562266
  LL_OETF RGB=91.8679 Y=88.3442 dE76=37.5953 hue=46.7569 sat=0.231994 hi=67.65000629419465
  EE_IDENTITY RGB=108.2211 Y=106.7950 dE76=45.7532 hue=46.5268 sat=0.234528 hi=47.08225822865678
  LE_IDENTITY RGB=154.0677 Y=149.1225 dE76=57.1506 hue=65.9729 sat=0.283231 hi=49.31861640313315
sample 05 identity=True defaults=True align=0.93278
  EL_OETF RGB=75.8391 Y=76.1394 dE76=40.8293 hue=22.0893 sat=0.335335 hi=108.62925235803526
  LL_IDENTITY RGB=80.7383 Y=84.9741 dE76=43.0820 hue=22.8923 sat=0.287696 hi=134.6427605025329
  LL_OETF RGB=96.7364 Y=99.3355 dE76=49.9366 hue=22.0753 sat=0.336943 hi=91.7377269526101
  EE_IDENTITY RGB=116.6506 Y=121.6696 dE76=61.0948 hue=22.0905 sat=0.332295 hi=71.0199224425406
  LE_IDENTITY RGB=160.3435 Y=160.2690 dE76=74.5520 hue=30.6799 sat=0.429976 hi=80.3693246464653
sample 06 identity=True defaults=True align=0.92768
  EL_OETF RGB=66.4179 Y=66.6399 dE76=34.8442 hue=15.9717 sat=0.291003 hi=93.58752748178827
  LL_IDENTITY RGB=70.2634 Y=72.6824 dE76=39.0976 hue=16.8508 sat=0.269712 hi=114.95858758452233
  LL_OETF RGB=90.1539 Y=93.4596 dE76=44.7576 hue=15.9489 sat=0.293528 hi=68.94703694586221
  EE_IDENTITY RGB=109.7241 Y=116.0268 dE76=54.4451 hue=15.9510 sat=0.277150 hi=55.658468701867356
  LE_IDENTITY RGB=154.1462 Y=154.6600 dE76=65.4196 hue=24.1538 sat=0.379105 hi=60.52496828362915

=== Aggregate ranking ===
EL_OETF composite=1.000000 medians={'encoded_rgb_rmse': 62.507981183412525, 'encoded_rgb_mae': 50.93496298041412, 'luma_rmse': 58.03151262981173, 'luma_mae': 47.16799749583849, 'delta_e76_mean': 28.515371179833053, 'hue_error_deg_mean': 16.67895673588561, 'saturation_error_abs_mean': 0.2612203139956478} wins={'encoded_rgb_rmse': 4, 'luma_rmse': 4, 'delta_e76_mean': 5}
  bins={'shadow': {'rgb_rmse': 83.15705864608326, 'luma_rmse': 86.8700030047336}, 'midtone': {'rgb_rmse': 50.16464046040978, 'luma_rmse': 43.06811726068065}, 'highlight': {'rgb_rmse': 90.93570936302268, 'luma_rmse': 81.58579354087094}, 'neutral_pixels': {'rgb_rmse': 77.84656519223816, 'luma_rmse': 77.92092412953889}, 'colourful_pixels': {'rgb_rmse': 56.54785934173245, 'luma_rmse': 50.026441900402716}} false-highlight-clips=140991
LL_IDENTITY composite=1.137013 medians={'encoded_rgb_rmse': 68.1789357344904, 'encoded_rgb_mae': 53.414463094705965, 'luma_rmse': 65.92887459629537, 'luma_mae': 53.30392832984905, 'delta_e76_mean': 33.768737507983744, 'hue_error_deg_mean': 17.755216836147802, 'saturation_error_abs_mean': 0.26420572522540686} wins={'encoded_rgb_rmse': 2, 'luma_rmse': 2, 'delta_e76_mean': 1}
  bins={'shadow': {'rgb_rmse': 72.49052384180092, 'luma_rmse': 77.59628387147825}, 'midtone': {'rgb_rmse': 63.414028431340085, 'luma_rmse': 57.12877649951331}, 'highlight': {'rgb_rmse': 111.45635254460565, 'luma_rmse': 100.66904630740822}, 'neutral_pixels': {'rgb_rmse': 78.8659470168183, 'luma_rmse': 75.6928685186443}, 'colourful_pixels': {'rgb_rmse': 63.79294031417828, 'luma_rmse': 59.36128045686958}} false-highlight-clips=445203
LL_OETF composite=1.450987 medians={'encoded_rgb_rmse': 90.67965756313339, 'encoded_rgb_mae': 75.86597056386667, 'luma_rmse': 89.46991699413559, 'luma_mae': 75.65862216578358, 'delta_e76_mean': 38.79584466490506, 'hue_error_deg_mean': 16.665664343453408, 'saturation_error_abs_mean': 0.2619740518863223} wins={'encoded_rgb_rmse': 0, 'luma_rmse': 0, 'delta_e76_mean': 0}
  bins={'shadow': {'rgb_rmse': 115.84458085806398, 'luma_rmse': 125.29012204730162}, 'midtone': {'rgb_rmse': 74.61826283172331, 'luma_rmse': 72.27126073701854}, 'highlight': {'rgb_rmse': 67.24256023496253, 'luma_rmse': 50.462659527700126}, 'neutral_pixels': {'rgb_rmse': 98.13169694929547, 'luma_rmse': 100.10864491273767}, 'colourful_pixels': {'rgb_rmse': 84.77716427731377, 'luma_rmse': 82.23910835845221}} false-highlight-clips=454873
EE_IDENTITY composite=1.795049 medians={'encoded_rgb_rmse': 108.97263474515032, 'encoded_rgb_mae': 94.36961916735687, 'luma_rmse': 111.29570591555861, 'luma_mae': 101.99147041877868, 'delta_e76_mean': 49.15929066409447, 'hue_error_deg_mean': 16.62589655854499, 'saturation_error_abs_mean': 0.25583876290653557} wins={'encoded_rgb_rmse': 0, 'luma_rmse': 0, 'delta_e76_mean': 0}
  bins={'shadow': {'rgb_rmse': 145.6311713668652, 'luma_rmse': 158.8233919969051}, 'midtone': {'rgb_rmse': 92.210331339954, 'luma_rmse': 91.09909244628678}, 'highlight': {'rgb_rmse': 51.370363465262066, 'luma_rmse': 29.742946671483104}, 'neutral_pixels': {'rgb_rmse': 123.28583454783022, 'luma_rmse': 128.04302128886155}, 'colourful_pixels': {'rgb_rmse': 103.00003089890663, 'luma_rmse': 103.52064778293386}} false-highlight-clips=1122795
LE_IDENTITY composite=2.506293 medians={'encoded_rgb_rmse': 157.2448782233682, 'encoded_rgb_mae': 143.26920317891307, 'luma_rmse': 157.15686509655086, 'luma_mae': 144.5524328066257, 'delta_e76_mean': 65.44708281039914, 'hue_error_deg_mean': 34.52018028648168, 'saturation_error_abs_mean': 0.3463101940823675} wins={'encoded_rgb_rmse': 0, 'luma_rmse': 0, 'delta_e76_mean': 0}
  bins={'shadow': {'rgb_rmse': 194.8390568297291, 'luma_rmse': 203.92554131280332}, 'midtone': {'rgb_rmse': 139.48092655112865, 'luma_rmse': 132.11981073695682}, 'highlight': {'rgb_rmse': 59.86921249549087, 'luma_rmse': 45.71529103870046}, 'neutral_pixels': {'rgb_rmse': 169.20381080585926, 'luma_rmse': 174.52778019799914}, 'colourful_pixels': {'rgb_rmse': 152.75934534628857, 'luma_rmse': 146.85867477978874}} false-highlight-clips=32874021

VERDICT MIXED_DOMAIN_PLACEMENT_EVIDENCE

Interpretation boundary: RGB1B discriminates output-domain placement inside the current reconstructed pipeline. It still does not prove the literal CA9/B2Y hardware mux or the exact live B2Y coordinate source.
Do not change m10r-capture1b unless one domain placement clears both the broad core and colour/highlight guards.
Workflow run id: 34199000803
Analysis input commit: 2c0a85baf4048e0c9821e5355338a313a8a60f22
