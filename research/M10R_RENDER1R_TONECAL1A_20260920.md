# M10-R RENDER1R TONECAL1A — native tone candidate built

Date: 20 September 2026. Branch: `m10r-render1r-tonecal1a`.

**Status: native photographic gate passed; Android test APK built. Not device validated, not production-promoted, not a recovered Y BLEND equation. Gate-C remains unresolved.**

Exact successful CI/build commit: `0c4c444d927eea7249b223490ee779518b8841b3`. Actions run: **35524055153**. Later report/index persistence commits are distinct from this tested commit.

## Implemented change

`native/m10rToneCal1A.h` implements a fixed smooth empirical output-lightness correction. `patches/fix-m10r-render1r-tonecal1a.py` adds one include and one call after the original RENDER1Q ARGB8 publication. Removing those two additions recovers the original native source exactly; its SHA256 is guarded.

Unchanged: source calibration, WB, matrices, CA9 clipping, MEDIUM/DG, YC2A coefficients, k=0.35 chroma policy, capture shutter/ISO/exposure decisions, demosaic, dimensions, orientation, JPEG quality setting, DNG saving and viewfinder path. No HDR, scene-adaptive normalization or saturation adjustment is added. Java identifies the new render and labels the inherited distributions as pre-correction diagnostics.

This is a saved-image renderer candidate, not a preview-parity update. The correction cannot recover details clipped upstream.

## Model, fitting and test split

```text
t = L*/100
Lout = L* + 4 t (1-t) [b0 + b1 (2t-1) + b2 (6t²-6t+1)]
b0 = -3.229545380578171
b1 = -0.25128474545011054
b2 = -0.17860038493017244
```

Fit: Photography Blog M10-R captures 01/03/05 only, native-input neutral patches (894/206/160), equal total capture weight, ridge 0.01. The fixed coefficients are reproduced in CI from these development captures alone. The previous 21-knot PHOTOAUDIT1B diagnostic is not the implemented model.

02/04/06 are the previously inspected original validation set, not new independent evidence. Additional pairs **07/08/09/10** were declared and the fixed header committed before their retrieval/scoring. They are test-only. They are not four statistically independent environments: 07/08 are related statue views, and 09/10 are shop scenes from the same publisher/camera/lens family. All four are ISO100; broad indoor, high-ISO and phone generalization remains untested.

Continuous slope is approximately 0.873727–1.146375; maximum darkening is 3.14572 L*. Exact black and white remain fixed. Examples: 10→8.880, 25→22.689, 50→46.860, 75→72.500, 90→88.735. This is not a constant EV adjustment or firmware-derived coefficient set.

## Actual native photographic results

Both original and integrated native functions execute on ten RAWs under two source-normalization conditions. Alignment is solved on baseline and shared by candidate and normalization control. Relatively uniform reference-selected patches are measured after actual bounded RGB output and uint8 rounding, not by correcting only patch means. Same-shot identity checks use camera/model, serial, unique image ID, timestamp and exposure fields. Fresh metadata, source hashes and raw geometry are retained. Fresh alignment correlations are 0.986–0.991, away from the search boundary.

| Additional test capture | Baseline L* MAE | Native candidate L* MAE |
|---|---:|---:|
| 07 | 1.208338 | 0.254834 |
| 08 | 1.493579 | 0.287740 |
| 09 | 1.982948 | 0.367159 |
| 10 | 1.809757 | 0.244241 |
| Equal-capture average | **1.623655** | **0.288494** |

Four improvements out of four; **82.23% lower measured lightness error**, not 82% better overall Leica fidelity.

| Set / input condition | Baseline L* MAE | Candidate L* MAE | Reduction | Improvements |
|---|---:|---:|---:|---:|
| Original 02/04/06, target-native | 2.538584 | 0.445870 | 82.44% | 3/3 |
| Additional 07–10, target-native | 1.623655 | 0.288494 | 82.23% | 4/4 |
| Original, white-normalized control | 4.081297 | 1.592802 | 60.97% | 3/3 |
| Additional, white-normalized control | 2.652033 | 0.938538 | 64.61% | 4/4 |

One fixed curve is used for all conditions, with no refit. Central target-native checks improve **2.648896→0.634605** on original validation and **1.934984→0.279848** on additional captures. Optical/demosaic confounds are reduced, not eliminated.

The APK gate required mean lightness improvement, at most one non-improving capture per set/condition, and less than 0.15 mean a*b* worsening. It was specified before scoring additional captures and was not relaxed.

## Colour and exposure remain separate

Additional target-native a*b* error is **4.585014→4.590059**, essentially unchanged/slightly worse. Combined Delta E76 improves **5.080615→4.613866**, about 9.19%. Additional white-normalized a*b* error is **4.396585→4.408970**. Analytic Lab a*/b* preservation precedes gamut clipping and RGB quantization; final-pixel colour invariance is not claimed.

A separate trace identifies the current chroma/luma gain relationship:

```text
luma gain = mappedY / Y
chroma gain = 1 + 0.35 (luma gain - 1)
chroma gain / luma gain = 0.35 + 0.65 / (luma gain)
```

In positive boosted-luminance, non-near-white samples from the original six captures, median relative gains are 0.468–0.493. This is a known attenuation relative to full proportional reconstruction in working coordinates, not the Lab chroma ratio to the camera JPEG, proof of every colour error's cause, or evidence that Leica uses k=1. No chroma setting changed.

The pinned Photon converter normalizes forward transforms into XYZ D50. The audit uses a matrix-only Leica DNG adapter, not equivalent Camera2 forward transforms. The white-normalized condition is sensitivity evidence, **not full phone-frontend equivalence**. Camera2 source calibration and lens/WB normalization still need device evidence.

RAW exposure and recorded WB remain fixed in comparisons. No phone shutter/ISO selection or metering fix is claimed. Reference firmware 10.20.27.20 differs from extracted tables 30.22.23.34. A version/adapter contribution to the measured tone error is not ruled out.

## Numerical, CI and APK checks

The original six-capture baseline rerun matched retained PHOTOAUDIT1B scores. Final CI and local native results match exactly across 144 metric comparisons (three metrics, baseline/candidate/central variants, twelve original capture/condition combinations).

All 20 integrated native outputs equal the standalone native lightness function applied to the original core output, pixel-for-pixel; upstream diagnostic counts match. Local numerical checks pass a 256-code monotonic equal-channel gray ramp, exact black/white, 100,000 alpha fixtures and 135,937 RGB probes against independently expressed OpenCV float Lab. Maximum difference is one channel code; mean absolute difference 0.218564 codes. Photographic scoring uses actual native output.

Quantization caveat: post-ARGB8 retone-and-round produces 248 distinct codes in the gray ramp. No lossless-retone claim. Device gradient/banding checks and Android latency measurement remain necessary. Host timings are not device benchmarks. No precision reduction was introduced for speed.

First CI run 35523781196 stopped on urllib HTTP403 fetching capture07. The original audit's curl recipe succeeded on the same published URLs in run35524055153. No captures, fitting parameters or scoring thresholds were substituted.

Evidence artifact **10609079325**, ZIP SHA256 `accb012e143fe5132cf71a52e86c3dbfd7f4588be1921b1c548cc51a2f6f803d`: CRC and all 33 validation-manifest entries pass; header, patch and validator match local source byte-for-byte.

APK artifact **10608363908**, ZIP SHA256 `8be334f82e9fc63b63e2284bf13c2b7ffac462c644d259a96d43acefeaf3798d`. Extracted APK SHA256 `1ce99f58e870fe30effcda1b51ce08d9c5d3a82312d01e52fefcce4d445f8577`, 113321240 bytes. CRC passes, DEX has the new marker, ARM64 and ARMv7 libdngCreator.so contain original M10R entry and TONECAL1A apply symbols. Code is linked there, not into a separate libm10r.so. Installation/signing compatibility and device runtime were not tested.

```text
Original native cpp SHA256:
27d42e3090435732bba6331380d2110227d3b713f59d3917b659d19cbea0f934
Candidate native cpp SHA256:
483a547259615c928a9dce82f88770995cec81f2900177db8439231f32d3baec
Native header SHA256:
890b55b3e27f02c1f6cbbdf3f5a5f4b1d272e39a88c0102f5f9059d3bbf93334
Photon upstream:
f0e6425d2509fb8ab834d5d3af593183038b778c
```

Version name contains `render1r-tonecal1a`. Sidecar `renderLook` is `RENDER1R_TONECAL1A_CC1MAP1A_YBLEND1B_K035_EDGE0A`; the `toneCal1A` object identifies empirical status, stage, coefficients and unchanged exposure/WB/chroma policy. Legacy histograms remain pre-correction.

## Decision and continuation

Ready for a bounded **phone test**, not production promotion. Use the established Xiaomi15Ultra/main-lens path; retain JPEG+DNG+JSON. Prioritize neutral indoor, daylight and high-contrast conditions; inspect gradients, shadows and processing delay. Compare baseline/candidate offline on the same new RAWs. A colour candidate should isolate the measured source/working-space and gain relationship, not silently add global saturation or claim firmware exactness.

Branch base: photoaudit head `2d16e275a887822a7c9d385441079010a398fd50`. Frozen RENDER1Q `a66b73cc339ebcb863d345c7a9ee7ff631fc86f0` and capture `3b1e86b5055a21b548d56b23bd47f9dc66c57012` were re-read after the build and remain unchanged.

## Evidence/reproduction

Primary evidence: native header, bounded patch, `tools/m10r_tonecal1a_validate.py`, CI `validation/results.json`, `inputs/fresh/provenance.json`, APK provenance, and compact downloadable package's local results/quality checks/chroma trace. The package includes a fuller report and reduced comparison images, not firmware binaries, original RAWs or third-party libraries; APK is separate.

Published reference source: https://www.photographyblog.com/reviews/leica_m10_r_review . Source-converter code: pinned Photon `processing/render/Converter.java` plus the reconstructed M10RNativeRenderer.java in input artifact10608056498. OpenCV official colour-conversion documentation supplies the independent Lab implementation, not Leica semantics.

```bash
python3 tools/m10r_tonecal1a_fetch_refs.py /path/to/verified/photoaudit_inputs
python3 tools/m10r_tonecal1a_validate.py /path/to/verified/photoaudit_inputs results --fresh
```

Use workflow-pinned dependencies, Java17, g++ and exiftool. Input artifact10608056498/run35518775600 contains first-six RAW arrays, source/tables and a checksum manifest; preserve it separately before its short retention expires. Report-persistence head is recorded separately from the actual tested source commit.
