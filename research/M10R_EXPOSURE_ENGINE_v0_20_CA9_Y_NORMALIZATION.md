# M10-R Exposure Engine v0.20 — CA9 Y-Statistic Normalization

**Date:** 2026-09-04  
**Branch:** `m10r-metering-latch-trace`  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Firmware SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Milestone

This pass closes the remaining scale factor inside the generic CA9 BV evaluator `0x40000178`.

The candidate evaluator can now be represented substantially as:

```text
cell_normalizer = (cell_step_x * cell_step_y) >> 2

normalized_cell_Y[i] = uint32_Y[i] / cell_normalizer

masked_Y = weighted mean of normalized_cell_Y using 0..100 mask weights

EV256 = 256 * log2(masked_Y / 524)

BV256 = EV256 + TV + AV - SV + 0x011A
```

Integer truncation/rounding occurs at multiple firmware steps and should be preserved when exact parity is implemented.

## 2. Why the two normalizer fields are geometry steps

The top-level CA9 evaluator configuration reads the two fields from the incoming AE-data object at:

```text
AE_data +0x28
AE_data +0x2C
```

and `0x40000178` multiplies them and shifts right two bits:

```text
(A * B) >> 2
```

The dynamic Spot quantity-table builder is called by the quantity-table selector with a pointer to:

```text
AE_data + 4
```

Inside that builder, its local structure offsets:

```text
builder +0x24
builder +0x28
```

therefore resolve back to the original:

```text
AE_data +0x28
AE_data +0x2C
```

The builder uses these exact fields as coordinate increments across the AE grid.

For each axis it constructs the first cell centre as:

```text
origin + step/2
```

then increments the centre by `step` for each subsequent grid cell.

Thus these two fields are proved to be the two AE-cell coordinate steps/pitches used by the metering grid.

## 3. Grid geometry

The dynamic Spot builder also establishes the grid dimensions used by the 16x22 quantity masks.

Because it receives `AE_data + 4`, its local offsets map as:

```text
builder +0x18 -> AE_data +0x1C
builder +0x1C -> AE_data +0x20
```

These are the two grid-cell counts used by the nested loops.

The static quantity masks contain exactly:

```text
352 = 16 * 22
```

entries, matching this runtime AE-grid geometry family.

The exact orientation label (which stored field should be called X vs Y after all camera rotations) should remain implementation-neutral until the orientation path is traced. `cell_step_x/cell_step_y` here denotes the two orthogonal grid axes behaviorally.

## 4. Y statistic and reference

v0.83b established:

```text
cell statistic type = uint32
firmware term        = Y data
reference            = 524 (0x20C)
```

The evaluator uses unsigned-integer-to-double conversions for both the cell Y values and the reference.

The CA9 firmware contains the direct diagnostic:

```text
CA9: AE MODULE: Y data = 0 -> Set EV to %i
```

The Y-statistic array begins at:

```text
AE_data +0x80
```

for the CA9 evaluator path.

## 5. Meaning of the >> 2

What is proved:

```text
normalizer = (orthogonal AE-cell step A * step B) / 4
```

The steps are the same coordinate pitches used to move from one AE cell centre to the next.

The most natural interpretation is therefore that the firmware converts an accumulated per-cell Y quantity to an average by dividing by the number of contributing sub-samples in a cell.

The factor of four is consistent with a 2x2 source-pixel/CFA sampling unit:

```text
samples_per_cell ~= cell_width * cell_height / 4
```

but **the CFA/2x2 explanation remains an inference**. No recovered firmware string currently names the factor as Bayer/CFA normalization.

## 6. Important data-layout observation

The generic evaluator uses a data-row stride derived as approximately:

```text
5 * grid_inner_dimension
```

with even alignment.

Yet the evaluator only reads one uint32 statistic stream and calls it Y data.

This suggests the AE-data payload contains multiple statistic planes/channels per grid row, with Y being one of them. The exact identities of the other four planes remain open and should not be named yet.

## 7. Current numerical candidate model

Ignoring firmware integer-rounding details, the Spot/Integral/AV-field path is now approximately reproducible as:

```text
for each selected AE grid cell i:
    y_avg_i = Y_sum_i / ((step_A * step_B) / 4)
    w_i     = mask_i / 100

Y_meter = sum(y_avg_i * w_i) / sum(w_i)

EV = log2(Y_meter / 524)

BV = EV + Tv + Av - Sv + (0x011A / 256)
```

All exposure coordinates are ultimately represented in 1/256-EV units in the CA9 path.

## 8. Next unresolved seam

The next high-value target is the AE-data payload at `+0x80`:

```text
- confirm whether each uint32 Y value is a sum, average, or another preprocessor accumulation before CA9 normalization;
- identify the other statistic planes implied by the ~5x row stride;
- identify the IMG/preprocessor producer that fills this grid.
```

Closing that producer would move the metering model from arithmetic parity to sensor-statistic parity.
