# M10-R YBLEND REFERENCE1E

Same-shot genuine M10-R RAW/JPEG discriminator. Only Y/C chroma inheritance changes. No ASIC-equation claim and no APK.

## Target-native equal-scene aggregate

| Model | L* MAE | a*b* error | DE76 | Chroma ratio | Hue err deg | Warm a*b* | Warm chroma ratio | Warm hue err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ABS_k0 | 1.661 | 15.530 | 15.842 | 0.319 | 5.12 | 28.997 | 0.339 | 9.88 |
| CURRENT_k035 | 2.374 | 7.060 | 7.781 | 0.754 | 4.39 | 9.762 | 0.836 | 9.23 |
| MID_k050 | 2.722 | 4.777 | 5.729 | 0.927 | 4.11 | 7.900 | 1.044 | 8.91 |
| REL_k100 | 4.035 | 9.082 | 10.101 | 1.412 | 4.71 | 28.658 | 1.657 | 9.76 |

## Guardrails

- k=0.50 is a midpoint hypothesis only; p1=32 has not been proven to use denominator 64.
- A lower error does not prove hardware arithmetic.
- Reference firmware version differs from recovered firmware tables.
- No phone capture/exposure/frontend behavior is evaluated.
- Do not promote a renderer solely from this sweep.
