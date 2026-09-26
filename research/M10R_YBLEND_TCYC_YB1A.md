# M10-R YBLEND TCYC/YB1A

Source-backed two-luminance offline discriminator. No APK and no parameter fitting.

## Primary holdout 07-10 / target-native

| Model | L* MAE | a*b* error | DE76 | Chroma ratio | Warm a*b* | Warm chroma | High-R frac |
|---|---:|---:|---:|---:|---:|---:|---:|
| CURRENT_k035 | 1.624 | 4.585 | 5.081 | 0.808 | 7.727 | 0.771 | 0.03423 |
| MID_k050 | 1.723 | 3.992 | 4.567 | 0.974 | 5.361 | 0.978 | 0.03716 |
| TCYC_ABS | 1.512 | 6.985 | 7.375 | 0.386 | 20.829 | 0.295 | 0.03026 |
| TCYC_RGB | 2.092 | 5.894 | 6.469 | 1.473 | 20.408 | 1.652 | 0.04878 |
| TCYC_RGB_YB32 | 19.601 | 9.953 | 22.893 | 1.175 | 20.200 | 1.387 | 0.00250 |

DE76 ranking: MID_k050, CURRENT_k035, TCYC_RGB, TCYC_ABS, TCYC_RGB_YB32
a*b* ranking: MID_k050, CURRENT_k035, TCYC_RGB, TCYC_ABS, TCYC_RGB_YB32

Interpretation: a winning topology is evidence for further reconstruction only. It does not prove the Leica ASIC equation or authorize Android promotion.
