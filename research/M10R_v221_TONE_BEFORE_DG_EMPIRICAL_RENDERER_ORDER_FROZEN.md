# M10-R v2.21 — DEFAULT STILL TONE → DIFFERENTIAL GAMMA RENDERER ORDER FROZEN

Status: **FROZEN for first-parity software rendering of factory/default STILL**.

Evidence class: **empirical renderer-order freeze**, supported by firmware active-set evidence and independent same-capture JPEG/DNG replication.

This is **not** a direct hardware mux/routing proof. The physical internal B2Y graph remains unresolved unless a future register/mux/block-diagram trace proves the edge directly.

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

Firmware SHA256:

```text
ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498
```

## 1. Frozen renderer order

For factory/default still rendering, use:

```text
... post-WB / rendered-CC RGB domain ...
              ↓
       tone control
              ↓
   differential gamma
              ↓
       downstream B2Y
```

In the current scalar first-parity nonlinear oracle this is the candidate named:

```text
tone-dg
```

Do **not** use `dg-tone` for the default STILL first-parity renderer unless later stronger evidence supersedes this freeze.

## 2. Firmware active-set prerequisite

The order experiment is meaningful because v2.17 proved that the two other obvious nonlinear candidates are inactive for the factory/default STILL calibration:

- de-knee record ID `0x01`: complete active record is zero; hardware enable bit resolves disabled;
- interpolation-gamma record ID `0x09`: complete active record is zero; hardware enable bits resolve disabled;
- differential-gamma control ID `0x0B`: active control is `(1,1)`, therefore enabled;
- tone-control path is active and the default STILL contrast selection is MEDIUM.

Primary evidence:

- `research/M10R_v217_still_deknee_interpgamma_enable.txt`
- `research/M10R_v206_DEFAULT_STILL_CONTRAST_MEDIUM_FROZEN.md`
- `research/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md`
- `research/M10R_v189_DIFFERENTIAL_GAMMA_ENCODING_FROZEN.md`

Therefore the empirical test is not silently omitting an enabled de-knee or interpolation-gamma stage from the default STILL nonlinear pair.

## 3. Tone-bank ambiguity already closed

v2.13/v2.14 established that TBL0/TBL1 are alternate banks of one tone-control stage, selected by a field in `0x20020804`; they are not two sequential tone stages.

For this firmware, TBL0 and TBL1 are byte-identical for the corresponding contrast assets, so tone-bank switching is functionally neutral for the present first-parity model.

References:

- `research/M10R_v213_tone_table_bank_select.txt`
- `research/M10R_v214_SINGLE_TONE_DUAL_BANK_FROZEN.md`

## 4. Exact nonlinear assets/model used

The empirical discriminator used the exact firmware-extracted assets validated by v2.07:

### Differential gamma

- exact 2048 coarse anchors + 2048 × 16 differential encoding;
- exact expanded coordinate curve length: `32768`;
- output range: `0..16383`;
- encoding/model frozen by v1.89.

### Tone MEDIUM

- default STILL contrast enum `2 = MEDIUM`;
- Q15 gain table;
- first-parity coordinate indexing `x >> 1`;
- Q15 unity `0x8000`;
- active coordinate domain represented by the current oracle: `0..0x4FFF`.

References:

- `tools/m10r_b2y_assets.py`
- `tools/m10r_b2y_nonlinear_oracle.py`
- `research/M10R_v207_b2y_asset_extractor_validation.txt`

## 5. One-scene precursor: v2.19

The first verified same-capture Leica M10-R JPEG/DNG pair already strongly favored `tone-dg`.

The pair was independently verified by matching:

- Make/Model;
- camera serial number;
- `ImageUniqueID`;
- capture timestamp;
- exposure time;
- aperture;
- ISO;
- focal length;
- exposure compensation.

The JPEG also reports default/normal controls:

```text
Contrast   0
Saturation 0
Sharpness  0
```

In v2.19, `tone-dg` reduced held-out fit error substantially and required an output gamma near unity, whereas `dg-tone` required a much stronger compensatory gamma around 1.6.

This result was intentionally not frozen on one scene.

## 6. Multi-scene independent replication: v2.20

v2.20 repeated the comparison over six independently verified JPEG/DNG pairs from the same public M10-R sample sequence.

Each capture was:

1. independently identity-checked from metadata;
2. confirmed to use default JPEG contrast/saturation/sharpness controls;
3. geometrically aligned independently;
4. reduced to low-chroma, low-texture patches;
5. fitted independently rather than pooled into a single scene-dominated optimization.

The proxy input was an oriented, linear camera-space green channel produced from the DNG with camera WB, normalized back toward DNG raw-code scale.

### Per-scene held-out RMSE advantage

Positive delta means `tone-dg` has lower held-out RMSE than `dg-tone`.

#### Truncation candidate

```text
sample 01  +0.257184
sample 02  +0.652488
sample 03  +0.226619
sample 04  +1.002119
sample 05  -0.007164
sample 06  +0.286916
```

Result:

```text
tone-dg wins 5 / 6
median advantage ≈ 0.272050
mean advantage   ≈ 0.403027
```

#### Round-to-nearest candidate

```text
sample 01  +0.255038
sample 02  +0.645923
sample 03  +0.236490
sample 04  +1.000063
sample 05  -0.009388
sample 06  +0.295297
```

Result:

```text
tone-dg wins 5 / 6
median advantage ≈ 0.275168
mean advantage   ≈ 0.403904
```

The lone reverse result, sample 05, is a near-tie: the disadvantage is below `0.01` under both rounding assumptions, compared with positive advantages of approximately `0.23..1.00` in the other five scenes.

## 7. Nuisance-output-gamma sanity check

The independently fitted downstream nuisance gamma provides a useful secondary consistency check.

Across the six valid scenes:

```text
median fitted output gamma

tone-dg : 1.00
dg-tone : 1.59
```

Thus the `tone-dg` candidate explains the reference JPEG relation while requiring essentially no additional power-law compensation in the fitted downstream transfer.

The `dg-tone` candidate can be made closer only by introducing a much stronger compensatory output nonlinearity.

This is supporting evidence, not a standalone proof.

## 8. Predeclared acceptance criterion

Before the v2.20 results were available, the workflow defined support as:

```text
>= 4 valid independently verified pairs
AND tone-dg wins >= 80% of valid pairs, minimum 4
AND this holds under BOTH trunc and nearest rounding candidates
AND median held-out RMSE advantage > 0.05
```

Observed:

```text
valid pairs = 6
wins = 5/6 under trunc
wins = 5/6 under nearest
median advantage ≈ 0.272 / 0.275
```

Therefore:

```text
EMPIRICAL_TONE_DG_PREFERENCE_SUPPORTED = True
```

This was not a post-hoc threshold chosen after viewing the six-scene result.

Primary evidence:

- `research/M10R_v220_reference_order_multiscene.txt`
- `research/M10R_v220_reference_order_multiscene.json`
- `tools/m10r_reference_order_fit.py`

## 9. What is frozen

For **factory/default STILL first-parity software rendering**:

```text
tone before differential gamma
```

The current first-parity nonlinear renderer should therefore model:

```text
y_tone = tone_MEDIUM(x)
y_out  = differential_gamma(y_tone)
```

with the exact already-frozen tone/DG assets and coordinate models.

## 10. What is NOT frozen

### 10.1 Physical hardware routing

Do not rewrite this result as:

> register/mux hardware proves tone physically feeds DG.

The v2.08 routing investigation did not find such a direct edge. The hardware graph remains open at that evidentiary level.

### 10.2 Tone Q15 rounding

Do not freeze truncation versus round-to-nearest from v2.20.

Within the selected `tone-dg` order:

```text
trunc wins   4 / 6
nearest wins 2 / 6
median(nearest RMSE - trunc RMSE) ≈ +0.00103
```

That magnitude is tiny and inconsistent by scene compared with the stage-order effect.

Exact hardware-cycle rounding remains open.

### 10.3 Exact post-WB/post-CC scalar input mapping

The v2.20 empirical fitter uses linear camera-space green as a proxy for the exact B2Y input coordinate.

The firmware has separately frozen the WB/rendered-CC provenance, but the empirical fitter has not yet reconstructed every per-pixel WB + rendered CC + B2Y coordinate step from the DNG.

That is the preferred next strengthening step.

### 10.4 Downstream JPEG transfer

The fitted affine/gamma nuisance transform absorbs downstream B2Y YC/JPEG/display-like transfer effects. It is not itself a frozen Leica transfer curve.

## 11. Renderer implication

The first-parity implementation can now stop branching on nonlinear order for the default STILL path.

Use:

```text
TONE_MEDIUM → DIFFERENTIAL_GAMMA
```

Keep tone rounding configurable until stronger evidence resolves it.

Keep the hardware-routing status separately marked as unresolved.

## 12. Next investigation

Strengthen the empirical freeze by replacing the green-channel proxy with the closest firmware-reconstructed per-pixel B2Y input possible:

1. recover/reuse exact DNG WB / camera-neutral interpretation;
2. apply the already-frozen rendered CC0/CC1 fixed-point matrices with their correct scale semantics;
3. determine which rendered CC bank/domain supplies the scalar nonlinear stage in default STILL;
4. repeat the same independent JPEG/DNG residual comparison with fewer nuisance degrees of freedom;
5. only revisit physical B2Y stage routing if a new explicit mux/source field appears.

A successful stronger validation may reduce the empirical uncertainty, but it should still remain distinct from a direct hardware route proof unless the latter is actually found.
