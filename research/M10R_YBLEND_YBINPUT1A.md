# M10-R YBLEND YBINPUT1A

Pre-CC0 Yb source-location offline discriminator. No APK and no parameter fitting.

## Primary holdout 07-10 / target-native

| Model | L* MAE | a*b* error | DE76 | Chroma ratio | Warm a*b* | Warm chroma | High-R frac |
|---|---:|---:|---:|---:|---:|---:|---:|
| CURRENT_k035 | 1.624 | 4.585 | 5.081 | 0.808 | 7.727 | 0.771 | 0.03423 |
| MID_k050 | 1.723 | 3.992 | 4.567 | 0.974 | 5.361 | 0.978 | 0.03716 |
| PRECC0_YB32_k035 | 22.260 | 8.206 | 24.885 | 0.656 | 15.210 | 0.643 | 0.00005 |
| PRECC0_YB32_k050 | 22.102 | 8.617 | 24.815 | 0.771 | 14.110 | 0.808 | 0.00009 |
| TCYC_ABS | 1.512 | 6.985 | 7.375 | 0.386 | 20.829 | 0.295 | 0.03026 |
| TCYC_RGB | 2.092 | 5.894 | 6.469 | 1.473 | 20.408 | 1.652 | 0.04878 |
| TCYC_RGB_YB32 | 19.601 | 9.953 | 22.893 | 1.175 | 20.200 | 1.387 | 0.00250 |
| TCYC_RGB_YB32_PRECC0 | 21.478 | 10.390 | 24.827 | 1.121 | 20.141 | 1.326 | 0.00044 |

DE76 ranking: MID_k050, CURRENT_k035, TCYC_RGB, TCYC_ABS, TCYC_RGB_YB32, PRECC0_YB32_k050, TCYC_RGB_YB32_PRECC0, PRECC0_YB32_k035
a*b* ranking: MID_k050, CURRENT_k035, TCYC_RGB, TCYC_ABS, PRECC0_YB32_k035, PRECC0_YB32_k050, TCYC_RGB_YB32, TCYC_RGB_YB32_PRECC0

Interpretation: a winning topology is evidence for further reconstruction only. It does not prove the Leica ASIC equation or authorize Android promotion.
