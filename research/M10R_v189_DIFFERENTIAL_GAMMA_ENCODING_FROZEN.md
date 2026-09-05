# M10-R v1.89 — Differential-gamma encoding FROZEN

Status: **FROZEN for functionally equivalent first-parity software rendering.**

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

This note freezes the differential-gamma calibration ABI and the exact equivalent transfer-curve reconstruction supported by firmware data. It deliberately distinguishes the proven *table-coordinate transfer function* from unresolved internal B2Y datapath bit width.

## 1. Selector / hardware ABI

B2Y selector `0x42153F60` loads three records:

```text
ID 0x0B -> 0x420D15E8  differential-gamma control
ID 0x1C -> 0x420D1648  main differential table
ID 0x1D -> 0x420D1690  FL/coarse-anchor table
```

All three records use the same mode aliases:

```text
_B2YMODE:STILL
_B2YMODE:STILLLINK
_B2YMODE:SLIVE
_B2YMODE:SMAGNI
```

The matched key selects the same payload record; these are mode aliases, not separate mode LUTs.

## 2. Control record

ID `0x0B` is exactly 8 bytes:

```text
+0x00  uint32  1
+0x04  uint32  1
```

`0x420D15E8` reads the low byte of each field and maps them directly to B2Y register `0x20020800`:

```text
control +0 -> bit 24
control +4 -> bit 25
```

M10-R calibration therefore enables both differential-gamma sub-blocks.

If the selector lookup is invalid/fallback, both bit 24 and bit 25 are cleared.

## 3. Main and FL uploads

### Main differential table — ID 0x1C

Calibration allocation:

```text
0x10000 bytes reserved
```

Active upload:

```text
first 0x8000 bytes only
copy destination 0x20A40000
```

`0x420D1648` performs a pure 0x8000-byte copy on the valid path.

### FL table — ID 0x1D

Calibration allocation:

```text
0x2000 bytes reserved
```

Active upload:

```text
first 0x1000 bytes only
copy destination 0x20A68000
```

`0x420D1690` performs a pure 0x1000-byte copy on the valid path.

The FL active region is exactly:

```text
2048 x uint16
range 0 .. 0x3FFF
```

## 4. Main-table geometry — 32^3 hypothesis rejected

The active main table is exactly 32768 bytes, numerically equal to `32^3`, but firmware-data structure strongly rejects treating it as a 32x32x32 color cube.

The exact structural factorization is:

```text
32768 bytes = 2048 groups x 16 bytes/group
FL           = 2048 uint16 anchors
```

Every one of the 2048 main-table groups has:

```text
group[0] == 0
```

The nonzero extent of the main groups and the non-saturated extent of FL terminate at the same index:

```text
last nonzero main group = 924
last FL value below 0x3FFF = 924
```

This one-to-one correspondence is decisive evidence that the two records are paired components of one scalar transfer function.

## 5. Exact coarse/fine relationship

For every interval `i = 0..2046`:

```text
D = FL[i+1] - FL[i]
q = floor(D / 16)
r = D mod 16
```

The 15 stored nonzero-position bytes:

```text
DG[i][1] .. DG[i][15]
```

plus the implicit boundary transition to the next FL anchor contain exactly:

```text
(16-r) increments equal to q
r      increments equal to q+1
```

This holds for **2047 / 2047 intervals with zero exceptions**.

Example first interval:

```text
FL[0] =   0
FL[1] = 156
D = 156 = 16*9 + 12

DG[0] =
[0, 9,10,10,10, 9,10,10,10, 9,10,10,10, 9,10,10]
```

The 15 stored increments contain four 9s and eleven 10s; the implicit transition to the next anchor is the twelfth 10. Thus all sixteen fine transitions exactly sum to 156.

## 6. Renderer-ready equivalent reconstruction

Define a table coordinate `x` over the 32768-addressable fine positions:

```text
coarse = x >> 4
fine   = x & 15
```

Then the function represented by the two firmware tables is exactly reconstructed by:

```text
y = FL[coarse]
for j = 1 .. fine:
    y += DG[coarse][j]
```

Equivalent concise form:

```text
y(x) = FL[x >> 4] + sum(DG[x >> 4][1 : (x & 15)+1])
```

The reconstructed table-coordinate curve has:

```text
32768 positions
output range 0 .. 16383 (0x3FFF)
monotonic = true
coarse anchor identity: y[16*i] == FL[i] for all i
```

The boundary transition between `fine=15` in one group and `fine=0` in the next group is exactly the one implicit sixteenth increment required by the FL anchor difference.

## 7. Important bit-depth caveat

The storage geometry provides a **15-bit table-coordinate capacity** (`32768 = 2^15`) and a 14-bit output range (`0x0000..0x3FFF`).

Do **not** yet freeze the statement that the live B2Y signal entering this block is itself a full-range 15-bit signal.

Reason:
- FL reaches saturation around coarse index 925, corresponding to table coordinate roughly `925*16`, well below 32767.
- This may reflect actual B2Y signal normalization/headroom, a smaller live input bit depth within a larger table address space, or calibrated early saturation.

For first-parity software rendering, the table-coordinate function above is exact. Mapping the software renderer's normalized linear/luma signal onto that coordinate remains a separate hardware-domain question.

## 8. Implementation implication

Do not emulate differential gamma as:
- a 32x32x32 3D color LUT,
- a single 2048-point curve with generic interpolation,
- or an arbitrary cubic/spline interpolation.

For firmware-equivalent lookup behavior, preserve the exact coarse/fine encoding:

```text
2048 uint16 anchors
2048 x 16 uint8 differential groups
```

A software implementation may pre-expand these into the equivalent 32768-entry uint16 monotonic curve at initialization. That is mathematically identical to the encoded calibration function and is likely simpler/faster for CPU/GPU parity testing.

## 9. Remaining nonlinear boundary

Differential-gamma *encoding* is now closed for first-parity purposes.

Next investigate tone control:

```text
ID 0x08  tone descriptor
ID 0x19  tone TBL0 LOW/MEDIUM/HIGH
ID 0x1A  tone TBL1 LOW/MEDIUM/HIGH
helper around 0x420D3C1C
```

Questions:
1. exact tone-table value representation (Q-format / gain vs direct output),
2. exact index domain and table geometry,
3. TBL0/TBL1 role and selection,
4. LOW/MEDIUM/HIGH semantic relationship,
5. equivalent renderer formula.
