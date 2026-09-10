# M10-R v2.70A — Baseline registry and return-to-device gate

Date: 2026-09-10
Status: RESEARCH-ONLY PROCESS CORRECTION

## 0. Purpose

This checkpoint deliberately stops the open-ended CC0/CC1/B2Y consumer trace from becoming the project loop.

The project already has enough static evidence to distinguish what is proven from what is hidden inside the Leica ISP. The next useful question is no longer "what else can be disassembled?" It is "which unresolved seam actually changes a real rendered photograph?"

No Android rendering arithmetic is changed here.

---

## 1. Canonical photographic baseline

The canonical executable validation baseline is **not** the moving `m10r-render1a` branch.

Use:

- build branch: `m10r-render1f-diag1a-build`
- APK-producing commit: `3946fb454a71c0f87adab96ae2f269a79939cd10`
- successful Actions run: `34269491592`
- artifact: `M10RCam-RENDER1F-YC2A-MATRIX1A-DIAG1A-debug-apk`
- artifact id: `10073339965`
- artifact SHA-256: `e353bee87985b38a372cc99d0342ae5d78eec121575183f17e6ec13987c0e943`
- artifact expiry recorded by GitHub: 2026-12-07

Current tip of `m10r-render1f-diag1a-build`:

- `c5d7cc5dd53e9e944983af06b88ce53901bdab24`
- parent: `3946fb454a71c0f87adab96ae2f269a79939cd10`
- the tip adds the v2.67 WB ColorSpec/D50/B2Y research closure; it does not replace the APK-producing render commit.

Therefore, for photographic comparisons, identify the baseline by the APK-producing commit/run above rather than by a mutable branch shorthand.

### Important branch correction

`m10r-render1a` currently points to an EDGE1B/SCALE1A experimental lineage rather than the canonical RENDER1F+YC2A+MATRIX1A+DIAG1A executable baseline. Do not use `m10r-render1a` as shorthand for photographic truth.

---

## 2. What is frozen in this baseline

Keep frozen unless a bounded A/B explicitly promotes a replacement:

- single RAW source
- HDR OFF
- RENDER1F
- YC2A
- MATRIX1A
- DIAG1A diagnostics only
- MEDIUM / DG behavior already carried by the baseline
- SCALE1A / EDGE1A / GAIN1A behavior already carried by the baseline
- Y_BLEND OFF
- LF OFF
- TEXTURE OFF

The firmware-derived YC matrix carried by the RENDER1F stack remains:

```text
 1224,  2403,   469
 -691, -1357,  2048
 2048, -1715,  -333
```

DIAG1A is diagnostics-only: it changes sidecar persistence/location and asserts that image arithmetic remains unchanged.

---

## 3. Static evidence that remains useful

### PROVEN

- rendered CC records use the recovered 0x2C ABI
- CC0 and CC1 are distinct records
- finite rendered-CC coefficient rounding is nearest, ties away from zero
- signed coefficient integer range is `[-2048, +2047]`
- automatic scale search tests scaleCode `0,1,2,3` in increasing order and accepts the first rounded representation that fits
- coefficient multipliers are therefore `512, 256, 128, 64`
- for the inspected genuine M10-R DNG, AsShotNeutral and B2Y Q8 direct WB gains close exactly through reciprocal 256:

```text
AsShotNeutral ~= [256/Rq8, 256/Gq8, 256/Bq8]
```

### STRONG

- M10-R CA9 ColorSpec follows a DNG-ColorSpec-like D50 PCS adaptation topology
- CC0/CC1 are routed through the same downstream color-correction family with different bank selection
- B2Y hardware is the likely physical consumer of at least part of this color state

### OPEN

- exact downstream CC MAC accumulator width
- exact runtime decode/shift/round/clamp semantics inside the hidden B2Y consumer
- whether `0x1D8FD4` is the final MMIO writer or a staging/descriptor routine
- whether B2Y direct WB is the sole physical realization of ColorSpec WB or an additional operation
- exact seam from CA9 CameraToPCS/D50 state into the fixed rendered CC0 working basis

These OPEN items are real, but none currently justifies a pixel change by itself.

---

## 4. Why v2.69 did not close the photographic question

The v2.69 WB/CC0 workflow successfully closed producer-side arithmetic/self-test facts.

However, the latest run (`34391471927`) executed only the `selftest` job. The `explicit-reference` job was skipped because no explicit per-scene firmware-derived CC0 mapping was supplied.

Correspondingly, the research branch currently has no committed:

```text
research/M10R_v269_wb_cc0_boundary.txt
research/M10R_v269_wb_cc0_boundary.json
```

So v2.69 strengthened the encoder/quantizer model but did **not** add a new real-scene photographic discriminator.

This is the point at which continued generic consumer tracing becomes circular.

---

## 5. Return-to-device gate — exactly one controlled tungsten capture

Do **not** build another APK first.

Use the existing DIAG1A APK from Actions run `34269491592` and make one controlled tungsten/very-warm indoor capture in a scene where the current renderer visibly shows the yellow/amber concern.

Preserve:

1. rendered JPEG
2. matching `_M10R_CAPTURE1B.json` sidecar

Do not change renderer parameters between capture and analysis. The purpose is diagnosis, not aesthetic tuning.

Priority sidecar fields:

```text
sourceSensorNeutral
sourceInterpolationFactor
sourceSensorToXYZD50
sourceWhiteLevelClipCount
neutralDomainClipCounts
m10rCa9Gains
sceneWhiteX
sceneWhiteY
sceneCctKelvinLeicaLocus
m10rSyntheticAsShotNeutral
```

### Derived checks to run from that one capture

A. **Neutral-domain clipping test**

- If `neutralDomainClipCounts` are zero/negligible while the JPEG still has the broad yellow/amber midtone cast, reject CA9 neutral clipping as the primary explanation.
- If clipping is material and channel-asymmetric, keep the physical WB/headroom boundary alive and quantify it before any color-matrix change.

B. **Reciprocal-256 ownership check**

From the recorded normalized neutral, compute the expected direct-WB Q8 values using the recovered reciprocal relationship and compare with `m10rCa9Gains` / the renderer's current synthetic neutral state.

The objective is to detect a double-WB or wrong-ownership error, not to invent a new gain stage.

C. **Scene-white / ColorSpec consistency check**

Use `sceneWhiteX/Y`, Leica-locus CCT, interpolation factor and `sourceSensorToXYZD50` to verify that the warm scene is being normalized through a self-consistent D50 ColorSpec state before blaming downstream CC finite precision.

---

## 6. Hard decision tree after the capture

### Outcome T1 — cast present, neutral clipping negligible, reciprocal-256 state consistent

Interpretation:

- clipping hypothesis rejected for the visible cast
- B2Y direct-WB ownership looks internally consistent
- highest-value next A/B is the **ColorSpec/D50 bridge / fixed working-basis seam**

Action:

- build exactly one controlled renderer A/B against the frozen DIAG1A baseline
- no generic B2Y trace first
- only alter the mathematically identified ColorSpec/D50-to-working-basis seam

### Outcome T2 — cast present and channel-asymmetric neutral clipping is material

Interpretation:

- physical WB/headroom boundary remains a plausible visible cause

Action:

- quantify where clipping begins and whether it predicts the observed hue direction
- trace only the specific clamp/ownership operation needed to reproduce that prediction
- do not reopen unrelated CC0/CC1 consumer tracing

### Outcome T3 — reciprocal-256 state is inconsistent with recorded neutral / current synthetic state

Interpretation:

- likely WB ownership or representation mismatch

Action:

- fix/AB that ownership seam before any downstream color look work
- explicitly guard against applying both ColorSpec WB and direct B2Y WB as two independent corrections

### Outcome T4 — JPEG no longer shows the original tungsten concern

Interpretation:

- do not manufacture a fix for a non-reproducing problem

Action:

- freeze WB path and move photographic validation to the next visible discrepancy (daylight color separation / saturation / highlight behavior) using the same one-hypothesis-at-a-time rule

---

## 7. Stop rule for future firmware research

A new static firmware investigation is allowed only if it has all three:

1. a named unresolved operation,
2. a predicted measurable effect in the current renderer or DIAG output,
3. a decision that changes depending on the result.

If an investigation cannot satisfy those three conditions, record it as OPEN and defer it.

This rule specifically prevents another sequence of:

```text
record producer -> consumer candidate -> deeper consumer candidate -> hidden hardware -> another handoff
```

without a photographic discriminator.

---

## 8. Current verdict

```text
CANONICAL_EXECUTABLE_BASELINE = RENDER1F_YC2A_MATRIX1A_DIAG1A @ 3946fb454a71c0f87adab96ae2f269a79939cd10
CANONICAL_ACTIONS_RUN = 34269491592
M10R_RENDER1A_IS_NOT_THE_BASELINE = TRUE
V269_PRODUCER_ARITHMETIC = CLOSED_ENOUGH_FOR_NOW
V269_REAL_SCENE_REFERENCE_GATE = NOT_RUN
GENERIC_B2Y_CONSUMER_TRACE = DEFERRED
NEXT_GATE = ONE_EXISTING_DIAG1A_TUNGSTEN_CAPTURE
NEW_APK_BEFORE_GATE = NO
```
