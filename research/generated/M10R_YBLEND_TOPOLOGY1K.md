# M10-R YBLEND TOPOLOGY1K

Offline public-reference discriminator; no APK and no M10-R ASIC parity claim.

## Fresh holdout 07–10, target-native

| Model | L* MAE | a*b* error | DE76 | chroma ratio | hue err | warm a*b* | warm chroma | warm hue |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CURRENT_K035 | 1.624 | 4.585 | 5.081 | 0.808 | 5.87 | 7.727 | 0.771 | 8.64 |
| TOPO_RGBDG_YBDG | 5.540 | 1.615 | 5.924 | 0.975 | 4.02 | 4.075 | 1.086 | 4.49 |
| TOPO_RGBDG_YBRAW | 20.119 | 5.548 | 22.012 | 0.674 | 16.55 | 11.251 | 0.928 | 25.03 |
| TOPO_LUMADG_YBDG | 5.707 | 6.282 | 9.876 | 1.474 | 6.20 | 19.984 | 1.637 | 9.44 |
| TOPO_LUMADG_YBRAW | 19.601 | 9.953 | 22.893 | 1.175 | 26.33 | 20.200 | 1.387 | 28.00 |

## Boundaries

- The Fujitsu patent supplies an architecture/equation family, not proof that Leica's ASIC uses the exact same internal routing.
- The related R2Y source supplies slot names/order for a closely related generation; M10-R selector values 0..4 and addresses are firmware-proven but their semantic labels remain cross-revision.
- No coefficients are fitted to 07–10; all topology variants are predeclared.
- Reference JPEG firmware differs from recovered M10-R firmware.
