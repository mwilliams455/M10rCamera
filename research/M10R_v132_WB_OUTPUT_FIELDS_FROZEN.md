# M10-R v1.32 — WB OUTPUT FIELDS FROZEN

Date: 2026-09-04

## Scope

This freezes the white-point and WB-gain representation exported/logged by `ca9_cm_ColorManagementFinished` on the IMG-System side.

It does **not** yet freeze WB preset selection, auto-WB decision logic, or the complete CA9 white-point call graph. Those remain the next tracing task.

## Source-state white-point fields

Relative to the callback source-state base:

```text
source +0x86 : x numerator   (u16)
source +0x88 : x denominator (u16)
source +0x8A : y numerator   (u16)
source +0x8C : y denominator (u16)
```

The callback converts each u16 to double and uses the firmware double-division helper as:

```text
x = double(*(u16*)(source+0x86)) / double(*(u16*)(source+0x88))
y = double(*(u16*)(source+0x8A)) / double(*(u16*)(source+0x8C))
```

This direction is frozen from AAPCS register flow into the division helper: the +0x86/+0x8A values occupy the first double argument (`r0:r1`) and +0x88/+0x8C occupy the second (`r2:r3`).

Nearby fields already frozen in v1.28 remain:

```text
source +0x80 : CC0 default flag (u8)
source +0x81 : CC1 default flag (u8)
source +0x84 : CC0 tint (s16)
source +0x9C : CC1 tint (s16)
```

Do not infer a monolithic symmetric structure merely from adjacency.

## WB gain fields

The callback directly reads three IEEE-754 doubles:

```text
source +0xB8 : R gain (double)
source +0xC0 : G gain (double)
source +0xC8 : B gain (double)
```

The diagnostic string explicitly labels the output order:

```text
[out] Gain remapped R: %4d | G: %4d | B: %4d
```

## Gain remap formula

For each channel, firmware computes:

```text
256.0 / gain
+ 0.5
truncate to integer
```

Therefore for normal positive gains the logged/programming-style integer is:

```text
remapped = round(256.0 / gain)
```

with the observed implementation equivalent to:

```c
int remap_gain(double gain) {
    return (int)(256.0 / gain + 0.5);
}
```

The callback processes B, G, then R internally, but places the final values into the log/output argument order R, G, B.

## Important distinction

The doubles at `+0xB8/+0xC0/+0xC8` are the high-level WB/color-management gain representation observed at the callback boundary.

The rounded reciprocal-256 integers are a remapped representation. Do not substitute the integer form for the doubles in the offline color oracle unless a downstream hardware/B2Y interface specifically consumes that format.

## Relationship to CC0/CC1

Current frozen rendered-color state now includes:

```text
CC0 matrix + Kelvin + tint
CC1 matrix + Kelvin + tint
white chromaticity x/y
R/G/B gains
```

This is enough to preserve the output-side color-management ABI while CA9 WB/AWB ownership is traced.

## Next unresolved WB tasks

1. Resolve exact CA9 function starts/xrefs for:
   - `ca9_cm_Temperature_ToXYCoord`
   - `ca9_cm_Temperature_FromXYCoord`
   - `ca9_cm_ColorSpec_MapWhiteMatrix`
   - `ca9_cm_ColorSpec_SetWhiteXY`
   - `ca9_cm_ColorSpec_NeutralToXY`
   - `ca9_cm_ColorSpec_MatrixInterpolate`
2. Trace preset vs Auto-WB mode ownership.
3. Determine which path produces Kelvin/tint and which produces x/y.
4. Trace `+0xB8/+0xC0/+0xC8` gain production.
5. Follow the gain representation into B2Y WB-gain programming.

## Frozen implementation view

```c
struct M10RWhitePointRational16 {
    uint16_t x_num;
    uint16_t x_den;
    uint16_t y_num;
    uint16_t y_den;
};

static inline double m10r_x(const M10RWhitePointRational16 *p) {
    return (double)p->x_num / (double)p->x_den;
}

static inline double m10r_y(const M10RWhitePointRational16 *p) {
    return (double)p->y_num / (double)p->y_den;
}

struct M10RWBGainDoubles {
    double r;
    double g;
    double b;
};
```

These are logical views. The surrounding callback source-state should not yet be frozen as one packed C structure.
