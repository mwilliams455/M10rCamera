# M10-R RENDER1S GAMUT1A — bounded output-stage correction

Date: 20 September 2026. Repository: `mwilliams455/M10rCamera`.
Branch: `m10r-render1s-gamut1a`.
Base: RENDER1R report head `77bee650e6141718b248c5f7da230fa74475b7d5`.
Exact validated and APK-built commit: **b73c017783cbbed374f96d4318cdf8989a56c458**.
Actions run: **35533742561**; both `validate` and `build-candidate` succeeded.

**Decision: isolated test APK built. Not device validated or production-promoted. The supplied phone DNG was NOT replayed in this pass. No claim that its window colour is now photographically correct.**

## 1. What was changed

The inspected, hash-verified native RENDER1R source computed unbounded post-CC1 RGB and independently clamped/rounded each component in `linear8`. TONECAL1A then ran on the already-quantized ARGB8 value. The new header `native/m10rOutputGamut1A.h` is inserted immediately before that first quantization. The existing TONECAL1A header, coefficients and later call are unchanged.

```text
Original source calibration / CA9 / MEDIUM / DG / k=0.35 reconstruction
    -> unchanged CC1
    -> new GAMUT1A out-of-range-only projection
    -> original direct 8-bit clamp/round
    -> unchanged TONECAL1A
    -> original JPEG path
```

Every finite RGB triplet already in [0,1]^3 is returned without modification. For an out-of-range triplet, the three components are adjusted together rather than independently flattened. This is an engineering candidate for output-range handling, NOT a recovered Leica Y BLEND equation or a new white balance/exposure policy.

The patch changes the generated native file, adds its header, updates Java diagnostic fields/counters, and updates versionName. It does not alter source matrices, white balance, CA9 clipping, MEDIUM/DG tables, YC coefficients, k=0.35, capture ISO/shutter decisions, demosaic, image dimensions/orientation, JPEG quality setting, DNG saving or preview. No HDR or stacking is introduced. There is no new full-image processing pass or new quantization stage; the previous RENDER1R post-ARGB8 tone pass and its precision limitations remain.

## 2. Exact projection and limitations

For conceptual input x=(R,G,B), let w=(0.2126,0.7152,0.0722), and let clip bound each coordinate to [0,1]. For an out-of-range finite input:

```text
a = dot(w, clip(x))
d = x - dot(w, x) * (1,1,1)
s = min(1, all applicable positive component bounds)
  where d_i > 0 gives s <= (1-a)/d_i
        d_i < 0 gives s <= -a/d_i
out = a * (1,1,1) + s*d
```

The implementation first normalizes extreme finite input before centering, avoiding overflow. A final bound removes floating-point boundary residue. Non-finite input uses the original per-component non-finite-to-zero fallback and has a distinct counter.

This preserves the **weighted code-luma of the independently clipped baseline**, and the direction of the unbounded RGB opponent vector before quantization. These coordinates are the existing direct post-CC1 output coordinates. They are NOT asserted to be linear light. The weights are an explicit engineering choice, not recovered firmware constants.

**It does not mathematically preserve perceptual hue or CIE L*.** Final appearance/lightness can change in the affected pixels, especially after the existing TONECAL1A conversion and rounding. There is no global exposure adjustment or blanket saturation change. Entirely in-range pixels have an exact bypass.

The projection does not recover sensor clipping, preceding target-neutral/CA9 clipping, or information already collapsed upstream. If every independently clipped component is white, the anchor is white and no extra colour headroom is created. It cannot establish that a real blue window should be neutral. Broader source calibration and chroma-fidelity questions remain separate.

For outside context only: W3C CSS Color 4 documents why independent clipping can change colour and why in-gamut-preserving mappings exist. This candidate is NOT an implementation of its perceptual CSS mapping algorithms; the specification also distinguishes photographic rendering from individual CSS-colour mapping. No Leica semantics are imported from that source.

## 3. Misleading diagnostics corrected

The inspected Java source passes a clone of the current `DEFAULT_SRGB_CC1` to the native processor, with rows:

```text
 2.0341 -0.7273 -0.3067
-0.2288  1.2317 -0.0029
-0.0086 -0.1533  1.1619
```

Its old REDTRACE label nevertheless printed the older matrix beginning 1.3895, and REDTRACE1B still claimed CC1 was bypassed. GAMUT1A removes those stale labels without changing the actual matrix arithmetic.

`cc1Matrix` and new `cc1MatrixRowMajor` now serialize the actual `workingToSrgb` array. The red equation is built from that same array. CC1-bypass and counterfactual flags are false; stratified mean keys identify actual pre-gamut CC1 values. Existing preSrgb and red-trace distributions are explicitly marked **before GAMUT1A, quantization and TONECAL1A**, not final JPEG measurements. The legacy EDGE0A-only-photographic-variable flag is corrected to false.

New `outputGamut1A` JSON includes full native pixel counts, not a 1/64 sample:

| Native count slots | Meaning |
|---|---|
| 0–7 | Original counts, unchanged |
| 8 | Total processed pixels |
| 9 | Exact in-gamut bypass pixels |
| 10 | Finite out-of-range projection pixels |
| 11 | Non-finite fallback pixels |
| 12–14 | Pre-map RGB below zero |
| 15–17 | Pre-map RGB above one |
| 18–20 | Post-map RGB below zero |
| 21–23 | Post-map RGB above one |

It also supplies per-tile source-sensor row-band counts, the rotation-coordinate convention, and count/frame consistency flags. Row bands are not a full two-dimensional excursion map. Full-pixel native counts must not be compared as raw counts with the old subsampled statistics; use their denominators.

The native array interface accepts the original minimum of eight entries and returns up to 24. Original first-eight semantics remain unchanged. The new Android Java caller allocates 24.

## 4. Executed unit and integration tests

All tests ran in GitHub Actions. Local container and Python calls continued to time out. No independent local rerun, local APK inspection or visual inspection of newly generated comparison images is claimed.

| Executed check | Result |
|---|---|
| 236,193 in-gamut RGB probes | Exact input/output equality; exact bypass status |
| 300,000 extended-range RGB probes | Finite bounded outputs; independent vector-form oracle agrees |
| Independent oracle maximum component difference | 2.886579864025407e-15 |
| Weighted code-luma maximum error | 2.220446049250313e-16 |
| Extreme finite and non-finite fixtures | 8 passed |
| Three 4,097-step channel ramps | Continuous floating outputs; maximum tested adjacent step 0.000561524 |
| 256-code equal-channel grayscale ramp | Final output exactly equals RENDER1R |
| Synthetic blue-channel plateau after TONECAL1A | Old independent clipping: 1 output colour; candidate: 39 |
| Native 600,000-pixel whole-vs-40,000-pixel chunk execution | Exact pixel and accumulated-counter equality |

The synthetic plateau deliberately holds R/G fixed while blue rises from 1 to 3. Its 39-vs-1 result shows that this model can retain distinctions lost by independent clipping on that artificial signal. It is NOT detail recovered from the supplied phone photo or proof of a Leica response.

For every photographic case, an instrumented host-only copy of RENDER1R records unbounded post-CC1 doubles. Its photographic pixels and original counts equal the uninstrumented baseline. The actual integrated GAMUT1A native function is then checked pixel-for-pixel against applying the standalone header to those doubles, followed by original rounding and the unchanged TONECAL1A header. A separately expressed NumPy model agrees before rounding. All in-gamut final pixels are compared against the actual RENDER1R output. Original upstream counters remain equal.

Instrumentation is not shipped in the APK.

## 5. Fixed photographic regression

The same ten Photography Blog Leica M10-R pairs from the previous audit were reused, under target-native and white-normalized input conditions: 20 cases. No coefficients or per-scene exposure/WB values were fitted. Same-shot metadata checks and first-six input-manifest verification were retained. These are existing references, not new independent holdouts; the inherited downloader's word “new” refers to their earlier introduction in TONECAL1A, not this pass.

Each input condition covers 25,401,600 evaluated sample pixels across the ten captures. These are correlated pixels, not that many independent photographic trials. Baseline/candidate alignment is shared within a case and solved on RENDER1R. In capture07, that produces slightly different selection scores from the earlier RENDER1Q-aligned audit, so do not splice the two metric tables together.

Equal-capture aggregate metrics, lower is better:

| Input condition / metric | RENDER1R | RENDER1S |
|---|---:|---:|
| Target-native L* MAE | 0.410441632 | 0.409880214 |
| Target-native a*b* error | 6.075137679 | 6.059949602 |
| Target-native Delta E76 | 6.117139507 | 6.102140989 |
| White-normalized L* MAE | 1.269529107 | 1.268649641 |
| White-normalized a*b* error | 5.698293602 | 5.681112539 |
| White-normalized Delta E76 | 5.998472261 | 5.981347675 |

Worst per-capture Delta E76 increase: 0.032071262 target-native and 0.032984665 white-normalized. The gate, committed before scoring this candidate, allowed no more than +0.15 mean increase in each listed metric and +0.5 worst-capture Delta E76. It was not relaxed. These very small aggregate changes establish a regression pass, not a solved colour-fidelity problem.

Target-native: 818,032 mapped samples and **24,583,568 exactly unchanged in-gamut pixels**. White-normalized: 889,718 mapped samples and **24,511,882 exactly unchanged in-gamut pixels**. Total exact in-gamut comparisons: 49,095,450. All per-case post-map excursion counts are zero; every original upstream counter matches.

Reference-selected relatively flat patches avoid some optical/demosaic confounds but also exclude many textured or extreme highlight regions. The aggregate metric is therefore not a sufficient oracle for the visual quality of the newly mapped highlight colours. The slight average colour improvement must not be promoted to a verified fix for the user's room/window scene.

The existing reference-firmware versus extracted-table version mismatch and Leica-DNG-versus-Camera2 frontend limitation remain. The ordinary-colour chroma deficit was not retuned by this patch.

## 6. Build and provenance

Both validation and Android build succeeded in run **35533742561**, exact source commit **b73c017783cbbed374f96d4318cdf8989a56c458**. The Android-generated native and Java hashes equal the validated patch-fixture hashes. The fixture uses actual retained renderer source, with a synthetic Gradle version string only; the APK uses the original build's actual Gradle file.

The APK's ZIP CRC check, DEX feature-marker checks, ARM64 dngCreator library presence and Android apksigner verification passed in the build runner. That does not test installation compatibility, Android rendering, device latency, autofocus or camera-session stability.

```text
Original RENDER1R native SHA256:
483a547259615c928a9dce82f88770995cec81f2900177db8439231f32d3baec
GAMUT1A candidate native SHA256:
af0d5fb85b5df55a00b7765f58ca96d5484900333e552c1591f99e5cb31f3895
GAMUT1A header SHA256:
30ff4b4f2a5f4e24677d5b3b193bfdb2a7808981543490a0c23faabecdf6412f
Candidate Java SHA256:
91cc7e5840d746567648447b1f2f149d12090ac42362087e0d32496a52f05bd6
```

Evidence artifact **10611948211**: `M10R-RENDER1S-GAMUT1A-EVIDENCE`, 3,256,602 ZIP bytes. GitHub-reported ZIP digest:
`3667ebe2413a48c6aa2db8fe1af16d5715af2f263b744fb9e66cf955579c1546`.

APK artifact **10611618545**: `M10RCam-RENDER1S-GAMUT1A-TONECAL1A-TEST-APK`, 76,290,870 ZIP bytes. GitHub-reported ZIP digest:
`d19721d23d7d8c1df3bda9c42facc482c29ad79a39f57c95c1c56ab1bd42694d`.

Both artifacts were retrieved through the GitHub connector. Their local ZIP hashes were not recomputed because the local runtime was unavailable. The APK archive contains the installable `.apk`, build provenance and signature-check output. The evidence archive contains the generated measurement report, full results, test source, patch, headers, reduced reference comparisons and a checksum manifest. This later narrative report is persisted separately in the repository.

VersionName contains `render1s-gamut1a-tonecal1a`. Sidecar renderLook:
`RENDER1S_GAMUT1A_TONECAL1A_CC1MAP1A_YBLEND1B_K035_EDGE0A`.

After the successful build, frozen reference heads were re-read:
RENDER1Q `a66b73cc339ebcb863d345c7a9ee7ff631fc86f0`;
capture `3b1e86b5055a21b548d56b23bd47f9dc66c57012`.
They remain unchanged. Later report-persistence commits are not the exact APK-tested commit.

## 7. Next bounded device check

Use the established Xiaomi15Ultra/main path and retain JPEG+DNG+JSON. Revisit the same mixed-light window/room scene without deliberately changing EV or WB to compensate for the renderer. Inspect the SAVED JPEG: the preview path is unchanged. Check the new renderLook, outputGamut1A counts and row bands, corrected CC1 metadata, smooth colour transitions and total render time.

The remaining private-DNG replay is still required for a same-input comparison on that actual phone capture. No private phone RAW/JPEG was copied into this public repository or CI artifacts. A phone result can confirm operation and guide colour judgement; no exact M10-R hardware parity is asserted. The Y BLEND reconstruction gate remains open.

## Reproduction

Use the workflow's pinned dependencies, Java17, g++, exiftool and the verified PHOTOAUDIT input artifact10608056498/run35518775600. Preserve that separately; its original retention is short.

```bash
python3 tools/m10r_tonecal1a_fetch_refs.py /path/to/inputs
python3 tools/m10r_gamut1a_validate.py /path/to/inputs results
```

Do not disable assertions. The APK workflow reconstructs exact RENDER1Q, applies the existing TONECAL1A patch, applies the new bounded GAMUT1A patch, compares generated hashes against validation, and only builds after the gate passes.

Primary evidence: committed headers/patch/validator/workflow; validation job106138931015 logs and artifact results; build job106139264920 step outcomes and artifact provenance. External background only: W3C CSS Color 4 https://www.w3.org/TR/css-color-4/ .
