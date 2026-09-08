M10-R PAIRED RAW/JPEG TRANSFER AUDIT1A
source: Photography Blog Leica M10-R samples 01..06; same-capture identity and default JPEG controls gated
fixed upstream candidate: exact firmware MEDIUM -> Differential Gamma
fit freedom: input coordinate scale + output affine only; NO arbitrary fitted output gamma
IMPORTANT: empirical photographic evidence, not direct CA9/B2Y mux proof.

=== per-sample fixed-transfer fits ===
sample 01 identity=True defaults=True ISO=320 patches=152
  trunc: identity rmse=0.361368 scale=0.970 | srgb_eotf rmse=2.511323 scale=2.820 | gamma22_eotf rmse=2.521242 scale=2.760 | gamma22_oetf rmse=5.710608 scale=0.350 | srgb_oetf rmse=6.629754 scale=0.350
    vs identity: srgb_oetf=+6.268385 gamma22_oetf=+5.349239 srgb_eotf=+2.149954 gamma22_eotf=+2.159874
  nearest: identity rmse=0.361728 scale=0.960 | srgb_eotf rmse=2.510555 scale=2.820 | gamma22_eotf rmse=2.520738 scale=2.770 | gamma22_oetf rmse=5.655926 scale=0.350 | srgb_oetf rmse=6.564669 scale=0.350
    vs identity: srgb_oetf=+6.202941 gamma22_oetf=+5.294199 srgb_eotf=+2.148828 gamma22_eotf=+2.159010
sample 02 identity=True defaults=True ISO=640 patches=81
  trunc: identity rmse=0.321938 scale=0.960 | gamma22_eotf rmse=2.398063 scale=3.000 | srgb_eotf rmse=2.528676 scale=3.000 | gamma22_oetf rmse=3.665017 scale=0.430 | srgb_oetf rmse=3.854248 scale=0.390
    vs identity: srgb_oetf=+3.532310 gamma22_oetf=+3.343079 srgb_eotf=+2.206738 gamma22_eotf=+2.076125
  nearest: identity rmse=0.339199 scale=0.960 | gamma22_eotf rmse=2.398723 scale=3.000 | srgb_eotf rmse=2.529519 scale=3.000 | gamma22_oetf rmse=3.632654 scale=0.520 | srgb_oetf rmse=3.869181 scale=0.390
    vs identity: srgb_oetf=+3.529983 gamma22_oetf=+3.293455 srgb_eotf=+2.190321 gamma22_eotf=+2.059525
sample 03 identity=True defaults=True ISO=100 patches=64
  trunc: identity rmse=0.340075 scale=0.940 | srgb_eotf rmse=2.213519 scale=3.000 | gamma22_eotf rmse=2.314094 scale=3.000 | gamma22_oetf rmse=5.942218 scale=0.350 | srgb_oetf rmse=6.746668 scale=0.350
    vs identity: srgb_oetf=+6.406594 gamma22_oetf=+5.602143 srgb_eotf=+1.873444 gamma22_eotf=+1.974019
  nearest: identity rmse=0.322561 scale=0.950 | srgb_eotf rmse=2.211046 scale=3.000 | gamma22_eotf rmse=2.311532 scale=3.000 | gamma22_oetf rmse=6.107108 scale=0.370 | srgb_oetf rmse=6.913395 scale=0.370
    vs identity: srgb_oetf=+6.590833 gamma22_oetf=+5.784547 srgb_eotf=+1.888484 gamma22_eotf=+1.988971
sample 04 identity=True defaults=True ISO=100 patches=282
  trunc: identity rmse=0.707168 scale=0.920 | srgb_eotf rmse=2.794320 scale=2.340 | gamma22_eotf rmse=2.801911 scale=2.260 | gamma22_oetf rmse=3.271138 scale=0.450 | srgb_oetf rmse=3.656275 scale=0.430
    vs identity: srgb_oetf=+2.949107 gamma22_oetf=+2.563970 srgb_eotf=+2.087151 gamma22_eotf=+2.094743
  nearest: identity rmse=0.704070 scale=0.920 | srgb_eotf rmse=2.793533 scale=2.340 | gamma22_eotf rmse=2.802012 scale=2.260 | gamma22_oetf rmse=3.246383 scale=0.450 | srgb_oetf rmse=3.599166 scale=0.430
    vs identity: srgb_oetf=+2.895096 gamma22_oetf=+2.542313 srgb_eotf=+2.089463 gamma22_eotf=+2.097942
sample 05 identity=True defaults=True ISO=100 patches=49
  trunc: identity rmse=0.475207 scale=0.950 | gamma22_eotf rmse=3.263762 scale=2.360 | srgb_eotf rmse=3.263998 scale=2.360 | gamma22_oetf rmse=5.750104 scale=0.350 | srgb_oetf rmse=6.703358 scale=0.350
    vs identity: srgb_oetf=+6.228152 gamma22_oetf=+5.274898 srgb_eotf=+2.788791 gamma22_eotf=+2.788555
  nearest: identity rmse=0.489311 scale=0.930 | gamma22_eotf rmse=3.259023 scale=2.360 | srgb_eotf rmse=3.259726 scale=2.360 | gamma22_oetf rmse=5.765118 scale=0.350 | srgb_oetf rmse=6.714414 scale=0.350
    vs identity: srgb_oetf=+6.225103 gamma22_oetf=+5.275807 srgb_eotf=+2.770415 gamma22_eotf=+2.769711
sample 06 identity=True defaults=True ISO=100 patches=122
  trunc: identity rmse=0.217357 scale=0.910 | srgb_eotf rmse=2.294549 scale=3.000 | gamma22_eotf rmse=2.319501 scale=3.000 | gamma22_oetf rmse=6.072865 scale=0.350 | srgb_oetf rmse=6.934597 scale=0.350
    vs identity: srgb_oetf=+6.717240 gamma22_oetf=+5.855509 srgb_eotf=+2.077192 gamma22_eotf=+2.102144
  nearest: identity rmse=0.213803 scale=0.910 | srgb_eotf rmse=2.293531 scale=3.000 | gamma22_eotf rmse=2.318176 scale=3.000 | gamma22_oetf rmse=6.039376 scale=0.350 | srgb_oetf rmse=6.890029 scale=0.350
    vs identity: srgb_oetf=+6.676227 gamma22_oetf=+5.825573 srgb_eotf=+2.079729 gamma22_eotf=+2.104373

=== aggregate ===
trunc: wins={'identity': 6, 'srgb_oetf': 0, 'gamma22_oetf': 0, 'srgb_eotf': 0, 'gamma22_eotf': 0}
  median RMSE delta (candidate-identity): sRGB OETF=6.248268329823218 gamma2.2 OETF=5.312068419572194 sRGB EOTF=2.1185527670665483
nearest: wins={'identity': 6, 'srgb_oetf': 0, 'gamma22_oetf': 0, 'srgb_eotf': 0, 'gamma22_eotf': 0}
  median RMSE delta (candidate-identity): sRGB OETF=6.214022137881965 gamma2.2 OETF=5.285002534360908 sRGB EOTF=2.1191452963832247

VERDICT PAIRED_REFERENCES_FAVOR_NO_ADDITIONAL_OETF_AFTER_TONE_DG
Interpretation boundary: this discriminates observable RAW->JPEG transfer shape around the recovered MEDIUM->DG chain; it does not by itself locate the transfer in CA9 vs B2Y vs JPEG hardware.
If identity wins strongly, the Android renderer should NOT remove its final sRGB OETF until an RGB/full-pipeline validation confirms the neutral-patch result.

LIMITATIONS
- neutral low-texture patches use rawpy linear camera-space green as the scalar input proxy.
- per-candidate input scale and output affine absorb exposure/level nuisance terms but not nonlinear transfer shape.
- JPEG luminance is measured from encoded 8-bit RGB; this test intentionally asks which fixed candidate best predicts that observable output.
- local processing, demosaic differences, chroma transforms and exact CA9 output-space matrices are not solved here.
