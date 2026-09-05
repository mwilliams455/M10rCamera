# M10-R v2.32 — B2Y CC0 internal-working-space / CC1 output-space architecture FROZEN

Status: **FROZEN as a structural renderer boundary**.

This freeze deliberately does **not** assign the factory/default STILL output-space enum. That remains the separate v2.31 provenance question.

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Proven runtime record roles

Earlier freezes establish:

```text
ColorSpec result +0x28 -> rendered CC0 -> IMG +0xFC -> B2Y CC bank 0
ColorSpec result +0x54 -> rendered CC1 -> IMG +0x128 -> B2Y CC bank 1
```

v2.27/v2.28 now establish how those records are constructed.

### CC0 source matrix

The main double-precision matrix constructed immediately before the first rendered record is:

```text
CC0_double = M_internal_from_PCS
           * SetWhiteXY_matrix_at_object_plus_0x28
           * diag(returned_gain_R,
                  returned_gain_G,
                  returned_gain_B)
```

where the fixed firmware matrix returned by getter `0x40012FB8` is at `0x400139F8`:

```text
 1.3460  -0.2556  -0.0511
-0.5446   1.5082   0.0205
 0.0000   0.0000   1.2123
```

This matrix is numerically the D50 XYZ->ProPhoto-RGB transform rounded to Leica's stored precision. The structural freeze does not depend on the external name: firmware data flow proves that it maps the ColorSpec PCS-side matrix into a fixed internal RGB working basis before CC0 quantization.

### CC1 source matrix

The second rendered record is **not** generated from the per-capture ColorSpec matrix.

The constructor selects one of three precomputed matrices from the table at `0x40013940`, stores the selected field-1 getter result, and later passes that matrix directly to the same rendered-record quantizer used for CC0.

Thus:

```text
CC1_double = mode_specific_internal_RGB_to_output_RGB_matrix
```

The mode field comes from the ColorSpec input object at `+0x20`.

## 2. Internal working-space pair

A second fixed firmware matrix returned by getter `0x40012DD0` is stored at `0x40013A40`:

```text
0.7977  0.1352  0.0313
0.2880  0.7119  0.0001
0.0000  0.0000  0.8249
```

This is the companion internal-RGB->PCS transform corresponding to the fixed `0x400139F8` PCS->internal-RGB matrix, at Leica's stored rounded precision.

The pair is numerically consistent with the standard D50 ProPhoto RGB pair, but the architectural claim frozen here is firmware-local:

```text
PCS  <->  fixed internal RGB working space
```

## 3. Three output modes

The mode table contains exactly three meaningful rows:

```text
mode 0: field1 getter 0x40012DDC -> 0x40013AD0
        field2 getter 0x40012FC4 -> 0x40013BF0

mode 1: field1 getter 0x40012DB8 -> 0x40013B18
        field2 getter 0x40012FA0 -> 0x40013BA8

mode 2: field1 getter 0x40012DC4 -> 0x40013B60
        field2 getter 0x40012FAC -> 0x40013C38
```

The field-2 matrices are exact standard D50 PCS->output-RGB matrices:

```text
mode 0 field2 = Adobe RGB (1998) PCS->RGB
mode 1 field2 = sRGB PCS->RGB
mode 2 field2 = ECI RGB PCS->RGB
```

The enum labels above are a **matrix semantic identification**, not yet the final firmware-enum naming freeze. v2.31 separately traces `_COLORSPACE:*` strings and default ownership.

## 4. CC1 precomposition identity

The field-1 matrices are not inverses of the field-2 matrices. Instead, they are precomposed transforms from Leica's fixed internal working RGB to the selected output RGB.

Using the firmware matrices themselves:

```text
M_working_to_PCS = matrix @ 0x40013A40
```

and each mode's field-2 matrix:

```text
predicted_CC1(mode) = M_PCS_to_output(mode) * M_working_to_PCS
```

produces the stored field-1 matrices to their deliberate four-decimal coefficient precision.

Stored field-1 matrices:

### mode 0 — `0x40013AD0`

```text
 2.0341  -0.7273  -0.3067
-0.2288   1.2317  -0.0029
-0.0086  -0.1533   1.1619
```

### mode 1 — `0x40013B18`

```text
 1.3895  -0.1693  -0.2202
-0.2288   1.2317  -0.0029
-0.0176  -0.0963   1.1139
```

### mode 2 — `0x40013B60`

```text
 1.2789  -0.1128  -0.1661
-0.2042   1.2569  -0.0527
 0.0183  -0.1126   1.0943
```

The maximum difference between `field2 * firmware_working_to_PCS` and the stored field-1 matrices is below approximately `4.9e-4`, consistent with the field-1 matrices being stored at four decimal places.

Therefore the meaningful hardware color chain is:

```text
camera-native / demosaiced RGB
    ↓ recovered WB / ASN ColorSpec
per-capture CameraToPCS-like transform
    ↓ fixed PCS->internal-working-RGB matrix
CC0
    ↓
internal working RGB
    ↓ tone / nonlinear stages according to frozen renderer order
    ↓ precomputed internal-working-RGB->selected-output-RGB matrix
CC1
    ↓
selected output RGB
```

## 5. Why this matters

This explains why treating CC0 and CC1 as two unrelated generic correction matrices was incomplete.

They form a deliberate color-space sandwich:

```text
CC0: scene/camera-dependent entrance into Leica's internal working RGB
CC1: static mode-dependent exit from that working RGB into output color space
```

Only CC0 is scene-dependent through white balance and the dual-illuminant ColorSpec construction. CC1 is selected from a fixed firmware table by the output color-space enum.

This also means the first-parity renderer does **not** need to infer a second per-scene color matrix after the nonlinear stages.

## 6. Quantization boundary retained from v2.28

Both matrices use the same rendered-CC record builder:

```text
denominator = 1 << (9 - scaleCode)
q[i] = clamp(round(matrix[i] * denominator), -2048, +2047)
```

with `scaleCode` selected from the firmware's bounded scale search and stored at record `+0x24`.

Kelvin is stored at record `+0x28`.

The `+0x26` halfword remains unresolved and must not be invented.

## 7. Remaining first-parity question

The structural matrix pipeline is now sufficiently constrained. The immediate remaining question is:

```text
which output-space enum is the factory/default STILL path?
```

v2.31 is tracing:

```text
_COLORSPACE:SRGB
_COLORSPACE:ADOBERGB
_COLORSPACE:ECI
```

back to their enum mapper and factory initializer/registration path.

Once that is frozen, the next implementation step is a software CA9 ColorSpec/CC reconstructor using:

1. DNG `AsShotNeutral` -> integer WB gains (v2.24);
2. Leica NeutralToXY / reciprocal-temperature interpolation / Bradford adaptation (v2.26);
3. exact constructor wiring (v2.27-v2.28);
4. fixed internal working-space matrices and mode-specific CC1 table (this freeze);
5. rendered-CC fixed-point quantization (v2.28);
6. factory TONE MEDIUM -> DG nonlinear order (v2.21).
