# M10-R v1.26 — DNG CM1/CM2 + T1/T2 layout FROZEN

Date: 2026-09-04

## Scope

This freezes the logical DNG dual-illuminant matrix layout exposed by `ca9_cm_ColorManagementFinished` at Thumb entry `0x420A3639`.

It supersedes the v1.23 tentative interpretation of a `0x2C` DNG matrix record with an independent `+0x28` tail word.

## Copy helper direction

`0x4204F2EC` is an ARM-state `memcpy(dest=r0, src=r1, size=r2)` implementation.

Proof in the helper body:

```text
ldm  r1!, {...}   ; read source
stm  r0!, {...}   ; write destination
...
ldr  r3, [r1], #4
str  r3, [r0], #4
```

Therefore the `ColorManagementFinished` copies serialize already-existing color state OUTWARD. They do not import DNG matrices into the source state.

## Source-state root

Within the callback:

```text
source_state = original r0
output       = original r1
cm_root      = *(source_state + 0x24)
```

The DNG dual-illuminant block within `cm_root` is:

```text
cm_root +0x38 : T1 double
cm_root +0x40 : CM1 logical matrix record
cm_root +0x68 : T2 double
cm_root +0x70 : CM2 logical matrix record
```

The firmware debug path prints both temperatures directly from the double pairs at `+0x38/+0x3C` and `+0x68/+0x6C`.

The second debug string incorrectly reuses `Color Temperature CM1` for T2; treat that as a diagnostic typo.

## Logical DNG matrix record

The logical DNG matrix record is **0x28 bytes**, not 0x2C:

```c
struct M10RDngMatrixFixed {
    int32_t coeff[9];     // +0x00 .. +0x20
    int32_t denominator;  // +0x24
};                         // sizeof = 0x28
```

The debug path converts each signed coefficient and the signed 32-bit denominator to double and divides coefficient values by that denominator before printing the 3x3 matrix.

Conceptually:

```text
M[r][c] = coeff[r*3+c] / denominator
```

## Why the old +0x28 field is rejected

CM1 begins at `cm_root+0x40`.

A hypothetical CM1 `+0x28` field would therefore be at:

```text
cm_root + 0x40 + 0x28 = cm_root + 0x68
```

But `cm_root+0x68/+0x6C` is directly read and printed as the T2 double.

So the previously suspected CM1 `+0x28` word is actually the low 32 bits of T2. It is not part of the logical matrix record.

This is independently reinforced by outward serialization:

```text
source cm_root+0x40 -> output+0x154, memcpy size 0x2C
source cm_root+0x70 -> output+0x17C, memcpy size 0x2C
```

The output starts differ by only `0x28`, so the two `0x2C` memcpy operations overlap by four bytes. The second copy overwrites the extra four bytes from the first copy. Therefore the memcpy width is a serialization implementation detail and must not be used as the logical DNG matrix structure size.

The next output region begins at `output+0x1A4`, again only `0x28` after `output+0x17C`, reinforcing the same packed-boundary interpretation.

## Separate 0x2C embedded color-spec records

Do not confuse the DNG records above with the separate embedded records at:

```text
source_state +0x28
source_state +0x54
```

Those are genuinely spaced `0x2C` apart, copied as `0x2C`, and mirrored to globals:

```text
0x408FE130
0x408FE15C
```

For these embedded records, firmware reads a **16-bit** field at `+0x24` and derives:

```text
scale = 1 << (9 - field_u16)
```

So their `+0x24` semantics differ from the DNG matrix `int32 denominator` at `cm_root+0x40/+0x70 +0x24`.

The embedded-record upper halfword at `+0x26` and word at `+0x28` remain unresolved and are NOT part of this DNG freeze.

## Frozen implementation ABI

```c
struct M10RDngMatrixFixed {
    int32_t coeff[9];
    int32_t denominator;
};

struct M10RDngDualIlluminantView {
    // offsets relative to cm_root
    double t1;                 // +0x38 (view offset; earlier fields omitted)
    M10RDngMatrixFixed cm1;    // +0x40
    double t2;                 // +0x68
    M10RDngMatrixFixed cm2;    // +0x70
};
```

Do not instantiate the second structure literally from offset zero without padding/earlier fields; it is an offset map for the observed `cm_root` region.

## Ownership conclusion

At callback time, DNG CM1/CM2 and T1/T2 already exist in the color-management source state rooted by `*(source_state+0x24)`.

`ca9_cm_ColorManagementFinished` exports/serializes those values to its outward result/output buffer.

This closes the v1.24 copy-direction/CM-ownership blocker.

## Next

1. Freeze the separate rendered CC0/CC1 structure.
2. Trace WB/AWB and color-spec white mapping.
3. Trace B2Y matrix/gamma/tone stages.
4. Build the offline M10-R color oracle.
