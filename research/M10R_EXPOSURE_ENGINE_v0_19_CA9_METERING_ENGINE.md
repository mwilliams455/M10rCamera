# M10-R Exposure Engine v0.19 — CA9 Metering Engine Architecture

**Date:** 2026-09-04  
**Branch:** `m10r-metering-latch-trace`  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Firmware SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Milestone

This pass moves the M10-R CMOS metering model from transport-level reverse engineering into the CA9 metering arithmetic itself.

The four CA9 brightness candidates are now structurally recovered as:

```text
Spot
Integral
MFM
AV-field
```

All four use the same logarithmic CA9 brightness evaluator, but with different spatial-selection policy. MFM adds a deterministic multi-field scene-classification and feature-blending stage.

## 2. CA9 result layout

The CA9 AE result object contains:

```text
+0x30  Spot BV
+0x32  Integral BV
+0x34  MFM BV
+0x36  AV-field BV

+0x38  Spot EV
+0x3A  Integral EV
+0x3C  MFM EV
+0x3E  AV-field EV
```

Firmware diagnostics explicitly print:

```text
AE spot ready (BV %i, EV %i)
AE integral ready (BV %i, EV %i)
AE MFM ready (BV %i, EV %i)
AE AV field ready (BV %i, EV %i)
```

The result fields are initially seeded from the incoming AE parameter structure before candidate-specific evaluation runs, providing fallback values when an evaluation/table is unavailable.

## 3. Candidate IDs

The CA9 quantity-table selector uses:

```text
0 = Spot
1 = Integral
2 = MFM
3 = AV-field
```

This is independent upstream confirmation of the candidate identities later transported into CTRL.

## 4. Generic CA9 BV evaluator

Core evaluator:

```text
0x40000178
```

Spatial weights are byte values interpreted as percentages and normalized by:

```text
weight / 100.0
```

The evaluator computes a weighted sensor statistic, forms a ratio against its reference quantity, and converts that ratio to an exposure coordinate using:

```text
EV256 = 256 * log2(weighted_statistic / reference)
```

The candidate BV then follows:

```text
BV256 = EV256 + TV + AV - SV + 0x011A
```

The scale is therefore exactly:

```text
256 units = 1 EV
```

`0x011A` is retained as a fixed CA9 BV offset; its deeper calibration meaning is not yet assigned.

## 5. Static spatial masks

The static masks are each exactly:

```text
0x160 bytes = 352 bytes = 16 x 22 byte weights
```

### Integral — 0x4001349C

Integral uses a smooth, symmetric centre-weighted field.

Recovered properties:

```text
weights: 0,10,20,30,40,50,60,80,100
non-zero cells: 312 / 352
sum of weights: 14160
```

The broad central field reaches weight 100 and falls progressively toward the edges.

### MFM base mask — 0x400135FC

All 352 entries are:

```text
100
```

Therefore MFM's spatial selectivity is not encoded in this base mask. It is created procedurally by the later multi-field engine.

### AV-field — 0x4001375C

AV-field uses a tight central island.

Recovered properties:

```text
weights: 0,5,15,20,30,50,60,80
non-zero cells: 44 / 352
sum of weights: 1260
```

Most of the 16x22 field is zero.

The complete byte matrices are preserved in:

```text
research/M10R_v076b_ca9_quantity_masks_fast.txt
```

## 6. Dynamic Spot mask

Spot candidate ID 0 uses a dynamic table built at:

```text
0x4002698C
```

by the builder around:

```text
0x400003E0
```

Behavior:

1. iterate the live AE grid;
2. derive each cell's centre coordinate;
3. compare that coordinate with a dynamic rectangular Spot ROI;
4. write weight 100 inside the ROI;
5. write weight 0 outside;
6. when sufficiently populated, soften selected ROI boundary cells to weight 50.

Thus Spot is a dynamic rectangular region on the same AE grid rather than a fixed centre mask.

## 7. MFM regional sampling

MFM subdivides the AE field procedurally and invokes `0x40000178` repeatedly.

The core MFM input to the aggregator is:

```text
24 regional BV values = 4 x 6 matrix
```

Early evaluations show small rectangular regions stepped systematically across the frame. The base MFM quantity mask remains uniformly 100; the field geometry is supplied by evaluator start-coordinate and extent parameters.

## 8. MFM aggregator

Unique MFM aggregator:

```text
0x4000301C
```

with unique caller:

```text
0x40001398
```

The aggregator:

1. ingests the 24 regional BV measurements;
2. constructs a parallel exposure-adjusted matrix;
3. sorts all 24 values;
4. computes min/max and full scene spread;
5. computes four six-field row means;
6. computes six four-field column means;
7. computes additional larger rectangular/block means;
8. derives five binary scene-condition flags;
9. converts those conditions into a 13-feature inclusion mask;
10. invokes the feature/confidence generator at `0x40001598`;
11. forms the final weighted feature mean;
12. clamps the result around the baseline MFM value.

## 9. Five-condition feature inclusion table

The static table begins at:

```text
0x400138BC
```

Its first 65 bytes are five rows of 13 binary feature enables:

```text
row 0: 0 0 0 0 0 0 0 0 0 0 0 0 1
row 1: 0 0 0 0 0 0 0 0 0 0 0 1 0
row 2: 1 1 1 0 0 0 0 1 1 1 1 0 0
row 3: 1 1 1 0 0 1 0 1 1 1 1 0 0
row 4: 0 0 0 1 0 1 0 0 0 0 0 0 0
```

Active condition rows are ORed together, producing one 13-byte binary inclusion mask.

Do not yet assign photographic names to these five condition rows; the threshold behavior is known but the firmware does not provide semantic labels.

## 10. Thirteen expert features

Feature/confidence generator:

```text
0x40001598
```

Exact output layout:

```text
feature[i] = signed halfword at work +0x152 + 2*i
weight[i]  = byte            at work +0x180 + i
for i = 0..12
```

The 13-byte mask passed to this function is the binary inclusion mask generated from the five scene-condition rows.

Therefore each feature is either disabled or, when enabled, assigned a dynamic confidence in the range 0..100.

The feature engine uses hand-authored photographic rules based on regional means, brightness differences and piecewise ramps. It is not a neural or opaque learned meter.

Recovered floating blend constants include:

```text
0.80
0.20
0.45
0.35
0.30
```

and one directly encoded constant:

```text
0.25
```

The piecewise confidence helper around `0x4000147C` maps exposure/statistic ranges into byte weights in the 0..100 domain.

The complete per-feature disassembly catalog is preserved in:

```text
research/M10R_v082_ca9_mfm_feature_catalog.txt
```

## 11. Final MFM blend

The final MFM reduction uses:

```text
effective_weight[i] = inclusion[i] * confidence[i]
```

where:

```text
inclusion[i] is binary 0/1
confidence[i] is 0..100
```

Thus the final aggregate is:

```text
MFM_candidate =
    sum(feature[i] * confidence[i], enabled features)
    -------------------------------------------------
         sum(confidence[i], enabled features)
```

If the denominator is zero, the prior/baseline value is retained by the surrounding control flow.

The result is then hard-clamped to:

```text
baseline_MFM - 0x200
    <= final MFM <=
baseline_MFM + 0x200
```

Since the CA9 coordinate uses 256 units/EV:

```text
0x200 = 512 = 2.0 EV
```

Therefore MFM scene adaptation is explicitly bounded to ±2 EV relative to its baseline.

## 12. Current implementation-level architecture

```text
16 x 22 AE statistic grid
        |
        +--> Spot dynamic ROI mask
        +--> Integral fixed centre-weighted mask
        +--> AV-field fixed central mask
        +--> MFM uniform base mask + procedural 4x6 regional sampling
                                |
                                v
                         24 regional BVs
                                |
                                v
                        sort / row / column /
                        block statistics
                                |
                                v
                      five scene conditions
                                |
                                v
                   OR 5 x 13 inclusion rows
                                |
                                v
                     13 enabled expert rules
                     + 0..100 confidences
                                |
                                v
                       weighted feature mean
                                |
                                v
                         clamp ±2 EV
                                |
                                v
                            MFM BV
```

## 13. Next unresolved seam

The highest-value remaining upstream seam is the input to `0x40000178` itself:

```text
what exact per-cell sensor statistic populates the 16x22 CA9 AE grid,
and what exact reference quantity forms the denominator of the log2 ratio?
```

That should be traced before implementing the M10-R metering engine on a phone, because reproducing Leica's spatial masks without matching the statistic domain would only provide structural parity, not numerical parity.
