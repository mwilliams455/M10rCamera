# M10-R v2.26 — CA9 ColorSpec core mathematics FROZEN

Status: **FROZEN for first-parity rendered-CC reconstruction**, limited to the rules directly established by firmware evidence below.

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Scope

This note freezes the CA9 color-spec mathematics that no longer need to be treated as unknown/proprietary renderer state:

1. the chromatic-adaptation matrix used by `MapWhiteMatrix`;
2. the white-point iteration convergence threshold and Leica loop bound used by `NeutralToXY`;
3. the dual-illuminant matrix interpolation rule used by `MatrixInterpolate`.

It does **not** freeze the entire CA9 `ColorSpec` implementation by analogy to any public source. Each rule below is grounded in the M10-R firmware itself.

## 2. `MapWhiteMatrix`: exact linearized Bradford matrix

Firmware function:

```text
ca9_cm_ColorSpec_MapWhiteMatrix
0x400058B8 .. 0x40005B3C
```

The matrix loaded from firmware address `0x400142B0` is exactly:

```text
 0.8951   0.2664  -0.1614
-0.7502   1.7135   0.0367
 0.0389  -0.0685   1.0296
```

The v2.25 probe compared the nine firmware doubles against the canonical linearized Bradford constants and obtained:

```text
max_abs_diff = 0.0
exact_python_float_equality = true
```

A second firmware matrix at `0x400142F8` is:

```text
 0.9869929  -0.1470543   0.1599627
 0.4323053   0.5183603   0.0492912
-0.0085287   0.0400428   0.9684867
```

Multiplying the first by the second gives identity to the precision of the stored truncated inverse coefficients:

```text
max identity error ≈ 8.445e-08
```

The function transforms each white through the Bradford matrix, forms the three component-wise ratios, builds the diagonal adaptation and maps it back using the inverse matrix.

### Frozen renderer rule

Use the firmware-stored Bradford pair, preserving the second matrix at its stored precision rather than silently replacing it with a freshly computed higher-precision inverse.

## 3. `NeutralToXY`: Leica convergence rule

Firmware string/function:

```text
ca9_cm_ColorSpec_NeutralToXY
owner around 0x400060F0 .. 0x400062A4
```

The firmware initializes:

```text
d8 = 0.5
threshold d9 = *(double *)0x400062C8
```

and v2.25 proves:

```text
*(double *)0x400062C8 = 1.0e-7
```

Each iteration computes:

```text
abs(x_new - x_last) + abs(y_new - y_last)
```

and compares that sum with the exact `1e-7` threshold.

### Leica-specific loop bound

The M10-R implementation does **not** use the 30-pass bound found in the compared public DNG SDK version.

Firmware control flow is:

```text
if pass_counter == 0x0E:
    x = 0.5 * (x_new + x_last)
    y = 0.5 * (y_new + y_last)
    evaluate once more

pass_counter += 1
continue while pass_counter < 0x0F
```

Thus the first-parity implementation must preserve the Leica `0x0F` / 15-pass boundary and the `0x0E` averaging fallback rather than copying the public SDK loop count.

## 4. `MatrixInterpolate`: exact reciprocal-temperature weighting

Firmware string/function:

```text
ca9_cm_ColorSpec_MatrixInterpolate
0x40005C5C .. approximately 0x40005D48
```

The interpolation object contains:

```text
+0x00  T1 double
+0x08  T2 double
+0x10  matrix 1
+0x58  matrix 2
```

Boundary behavior is directly visible:

```text
if Tcurrent <= T1:
    return matrix1

if Tcurrent >= T2:
    return matrix2
```

Inside the bracket the firmware computes:

```text
g = (1/Tcurrent - 1/T2) / (1/T1 - 1/T2)
```

then constructs the interpolated matrix as:

```text
M = g * matrix1 + (1 - g) * matrix2
```

This is proven from the explicit sequence of `vdiv`, `vsub`, scale calls and final matrix-combine call; it is not inferred from programming order.

## 5. What this closes

The following are no longer unknown for first-parity reconstruction:

```text
DNG AsShotNeutral
    ↓ v2.24 empirical exact inverse of live ABI
integer CA9 WB gains
    ↓ 256/gain
ASN neutral triplet
    ↓
NeutralToXY
    - convergence threshold = 1e-7
    - Leica max loop boundary = 15
    - final fallback average at pass 14
    ↓
dual-illuminant matrix selection
    - reciprocal-temperature interpolation
    ↓
MapWhiteMatrix
    - exact firmware Bradford constants
```

## 6. Remaining boundary

The next unresolved step is **not** general white-balance provenance or generic dual-illuminant interpolation.

The remaining work is to freeze the exact `FindXYZtoCamera`/constructor wiring that maps:

```text
DNG-visible CM1/CM2 + T1/T2
and recovered ASN
```

to the two CA9 rendered records:

```text
rendered CC0
rendered CC1
```

Specifically:

1. disassemble the helper at `0x40005D80` called by `NeutralToXY` and determine exactly how it forms XYZ→camera from the interpolated matrix;
2. trace the higher-level constructor around `0x40003C10..0x40003D50` to label every matrix object passed into `SetWhiteXY`, `MapWhiteMatrix`, and the final two matrix products;
3. determine whether any scene-varying input beyond ASN enters this constructor;
4. if none does, implement the full CA9 rendered-CC reconstruction in software and use it as the input transform for the v2.21 `TONE MEDIUM → DG` renderer oracle.

Until that final wiring is frozen, do not equate DNG CM1/CM2 directly with rendered CC0/CC1.
