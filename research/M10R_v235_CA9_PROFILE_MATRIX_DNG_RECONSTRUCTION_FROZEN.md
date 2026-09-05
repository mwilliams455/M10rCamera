# M10-R v2.35 — CA9 profile matrices are exact DNG CM expansions (FROZEN)

## Scope

Freeze the relationship between the DNG-visible dual-illuminant color matrices in the shared CA9 color-management state and the 3x3 double matrices consumed by the rendered ColorSpec/CC0 constructor.

This closes the remaining provenance gap between:

- `cm_root+0x40/+0x70` — DNG CM1/CM2 fixed-rational records, and
- `cm_root+0x98/+0xE0` — rendered-path 3x3 `double` profile matrices.

## Shared state root

The shared color-management object is:

```text
cm_root = 0x43705830
```

The already-frozen DNG layout is:

```text
cm_root+0x38 : T1 double
cm_root+0x40 : CM1 { int32 coeff[9]; int32 denominator; }
cm_root+0x68 : T2 double
cm_root+0x70 : CM2 { int32 coeff[9]; int32 denominator; }
```

The rendered constructor reads the same T1/T2 and copies 72-byte double matrices from:

```text
cm_root+0x98 : PROFILE1_DOUBLE[3][3]
cm_root+0xE0 : PROFILE2_DOUBLE[3][3]
```

`0x40012E24` is a 72-byte copy helper, so those matrices are fully materialized before the rendered ColorSpec constructor begins.

## Exact initializer ownership

`0x420A5DE4` loads `r0 = 0x43705830` and calls:

```text
0x420A4AAC
```

Thus `0x420A4AAC` is the direct initializer/owner for the shared `cm_root` region.

## CM1 construction

The initializer receives/parses nine CM1 integer coefficients in stack words:

```text
SP+0x130 ... SP+0x150
```

and a CM1 scale exponent at:

```text
SP+0x154
```

It constructs the fixed-rational DNG record directly:

```text
cm_root+0x40 ... +0x60 = the same nine coefficient words
cm_root+0x64            = 1 << exponent
```

The same nine coefficient values are each converted to double and divided by the converted common denominator. The nine resulting doubles are stored consecutively at:

```text
cm_root+0x98 ... +0xDF
```

Therefore, coefficient-for-coefficient:

```text
PROFILE1_DOUBLE[r][c] = CM1.coeff[r*3+c] / CM1.denominator
```

## CM2 construction

The second illuminant repeats the same construction from:

```text
SP+0x15C ... SP+0x17C   nine coefficient words
SP+0x180                scale exponent
```

The fixed-rational record is stored at:

```text
cm_root+0x70 ... +0x90 = nine coefficient words
cm_root+0x94            = 1 << exponent
```

and the nine corresponding floating-point quotients are stored at:

```text
cm_root+0xE0 ... +0x127
```

Therefore:

```text
PROFILE2_DOUBLE[r][c] = CM2.coeff[r*3+c] / CM2.denominator
```

## DNG serialization proof

v1.26 independently froze the DNG matrix record as:

```c
struct M10RDngMatrixFixed {
    int32_t coeff[9];
    int32_t denominator;
};
```

with logical matrix values:

```text
M[r][c] = coeff[r*3+c] / denominator
```

and proved that `ca9_cm_ColorManagementFinished` serializes the already-existing `cm_root+0x40/+0x70` records outward rather than importing or transforming them.

## Frozen reconstruction ABI

For a Leica M10-R DNG carrying the firmware CM1/CM2 values, reconstruct the exact rendered-path profile matrices as:

```python
profile1 = matrix_from_dng_cm1_rationals()
profile2 = matrix_from_dng_cm2_rationals()
```

or, at the firmware integer-record level:

```python
profile1[i] = cm1_coeff[i] / cm1_denominator
profile2[i] = cm2_coeff[i] / cm2_denominator
```

The associated T1/T2 are already the same double values consumed by the rendered constructor and exported through the DNG-facing color-management state.

## Consequence

There is **no hidden proprietary matrix state between DNG CM1/CM2 and the CA9 rendered ColorSpec profile matrices**.

The DNG-visible dual-illuminant color matrices plus T1/T2 are sufficient to reconstruct this complete profile input boundary exactly.

The remaining scene-dependent input is the white/neutral state; first-parity recovery of the CA9 integer WB gains from DNG `AsShotNeutral` is frozen separately as empirical reconstruction evidence.

## Evidence boundary

This freeze establishes only the CM1/CM2 → PROFILE1/PROFILE2 relationship and shared T1/T2 ownership. It does not by itself freeze the complete final CC0 numerical output unless all downstream Leica ColorSpec operations and quantization are applied with their separately proven semantics.
