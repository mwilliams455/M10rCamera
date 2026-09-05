# M10-R v1.85 — CA9 rendered CC → IMG → B2Y handoff FROZEN

Status: **FROZEN** for first-parity renderer work.

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

This note freezes the proven handoff from CA9 color management into the live B2Y color-correction hardware records. It supersedes the earlier possibility that the B2Y `colorcorrection0/1` calibration records were independent per-frame color matrices.

## 1. Frozen end-to-end chain

```text
integer WB gains R/G/B
    ↓
clamp [1,2000]
    ↓
ASN doubles = 256.0 / gain
    ↓
CA9 color management
    ↓
NeutralToXY → SetWhiteXY → MapWhiteMatrix
    ↓
rendered CC0 / rendered CC1 (0x2C-byte records)
    ↓
IMG parameter ABI
    CC0 at +0xFC
    CC1 at +0x128
    ↓
0x4215220C marshals those records into its local B2Y object
    ↓
central B2Y selector 0x42154F84
    ↓
colorcorrection0 / colorcorrection1 selectors
    ↓
0x420D0C70 / 0x420D0ED4
    ↓
B2Y CC hardware register windows
```

No separate per-frame B2Y matrix derivation is required to explain the live rendering path.

## 2. CA9 callback writes the stable IMG fields

`ColorManagementFinished` receives the returned CA9 color-management result and copies:

```text
returned source +0x28  → IMG destination +0xFC   size 0x2C   rendered CC0
returned source +0x54  → IMG destination +0x128  size 0x2C   rendered CC1
```

It also copies the same rendered records to the diagnostic/shared globals:

```text
0x408FE130  rendered CC0
0x408FE15C  rendered CC1
```

Those globals are useful for tracing and direct hardware-update paths, but the stable per-operation IMG ABI fields are `+0xFC` and `+0x128`.

## 3. Exact IMG → local B2Y marshalling

Function `0x4215220C` has `r4 = input_parameter_ptr` and constructs a local B2Y parameter block at `SP+0x104`.

### WB gains

```text
input +0xF4  → local +0x04  uint16
input +0xF6  → local +0x06  uint16
input +0xF8  → local +0x08  uint16
```

### Rendered CC0

```text
input +0xFC   → local +0x0C
input +0x100  → local +0x10
input +0x104  → local +0x14
input +0x108  → local +0x18
input +0x10C  → local +0x1C
input +0x110  → local +0x20
input +0x114  → local +0x24
input +0x118  → local +0x28
input +0x11C  → local +0x2C
input +0x120  → local +0x30  control/scale field carried with CC0
```

### Rendered CC1

```text
input +0x128  → local +0x34
input +0x12C  → local +0x38
input +0x130  → local +0x3C
input +0x134  → local +0x40
input +0x138  → local +0x44
input +0x13C  → local +0x48
input +0x140  → local +0x4C
input +0x144  → local +0x50
input +0x148  → local +0x54
input +0x14C  → local +0x58  control/scale field carried with CC1
```

The `+0x124` gap between the two matrix coefficient groups is consistent with the 0x2C-byte rendered-CC record geometry.

## 4. Central-object coordinate proof

The owner function begins:

```text
0x4215220C  push {r4,r5,r6,r7,lr}
...
0x42152216  r6 = SP + 4
```

The local B2Y CC block is repeatedly addressed explicitly as:

```text
SP + 0x104
```

The two small preparation helpers are called with the same object by arithmetic on `r6`:

```text
0x4215245A  r0 = r6 + 7
0x4215245C  r0 += 0xF9
             => r0 = r6 + 0x100
             => r0 = (SP+4) + 0x100
             => r0 = SP + 0x104
```

Later the central selector is called with:

```text
0x42152ED8  r0 = r6
0x42152EDA  call 0x42154F84
```

Inside `0x42154F84`, every B2Y parameter selector is given:

```text
r0 = central_object + 0x2C
```

For CC0 specifically:

```text
0x42154FE6  r1 = 0
0x42154FE8  r0 = r4
0x42154FEA  r0 += 0x2C
0x42154FEC  call 0x42153D24
```

`0x42153D24` then supplies the runtime coefficient block to `0x420D0C70` as:

```text
r2 = selector_object + 0xD4
```

Therefore:

```text
SP+4 + 0x2C + 0xD4
= SP+4 + 0x100
= SP+0x104
```

CC1 uses the same `selector_object +0xD4` runtime object when calling `0x420D0ED4`.

This three-way address identity is the decisive proof that the local object marshalled from IMG `+0xFC/+0x128` is exactly the runtime CC object consumed by the B2Y hardware helpers.

### Disassembly caveat

A linear Thumb pass through the beginning of `0x4215220C` can decode inline data/pool bytes as apparent writes to `r6` around `0x4215222C..0x4215222E`. Those decodes are incompatible with the later pointer arithmetic (`r6+0x100` must equal the explicitly addressed `SP+0x104` object) and are not part of the live pointer semantics. The address identity above is based on the actual object uses and is the frozen interpretation.

## 5. Runtime B2Y CC helper ABI

The object passed as `r2` into the two hardware helpers is:

```c
struct M10RB2YRuntimeCC {
    uint8_t  control0;        // +0x00 etc.; non-matrix control area
    // ...
    uint32_t cc0[9];          // +0x0C .. +0x2C
    uint32_t cc0Control;      // +0x30
    uint32_t cc1[9];          // +0x34 .. +0x54
    uint32_t cc1Control;      // +0x58
};
```

The precise signed/fixed interpretation of each coefficient is inherited from the rendered-CC record and the B2Y register packing; do not reinterpret these as arbitrary unsigned integers in a renderer.

## 6. Static B2Y.bin CC records are not the live per-frame matrix source

Calibration selector IDs:

```text
ID 0x06  colorcorrection0
ID 0x0A  colorcorrection1
```

Their payloads contain plausible fixed matrix values. Example CC0 contains:

```text
 955  -338  -105
-135   716   -69
   2  -258   768
```

However, in the enabled helper path the matrix coefficient register words come from the runtime `r2` object described above. The static calibration records supply enable/control/offset/limit fields and also appear in initialization/default/fallback behavior.

A static initialization path around `0x42169BAC` writes values matching the ID-6 matrix into the rendered-CC global state. That supports the interpretation of these calibration values as baseline/default material rather than a second per-frame matrix multiplied after CA9 output.

Do **not** model the static B2Y CC matrix and CA9 rendered CC as two sequential 3x3 transforms unless later firmware evidence proves an additional distinct hardware stage.

## 7. Hardware destinations

CC0 helper:

```text
0x420D0C70
MMIO base 0x20020100
coefficient register window begins around base +0x20
```

CC1 helper:

```text
0x420D0ED4
MMIO base 0x20020880
coefficient register window begins around 0x200208A0
```

The previously traced CA9-rendered CC hardware programmer also touches the CC1 register window around `0x200208A0`. This is evidence of shared/alternative programming of the same hardware stage, not evidence for an additional downstream matrix.

Exact temporal ordering of every initialization/update writer remains a lower-priority hardware-scheduling question; it is not needed to reproduce the proven per-frame mathematical transform.

## 8. Renderer implication

For first-parity software rendering, use the CA9-derived rendered CC0/CC1 as the authoritative per-frame color matrices. Preserve their fixed-point scale semantics. Do not apply the ID-6/ID-0xA static matrices as an additional transform on top.

The next unresolved color-rendering boundary is no longer matrix provenance. It is the nonlinear B2Y transform semantics:

1. differential-gamma main 0x8000-byte table addressing/interpolation,
2. differential-gamma FL 2048-entry u16 curve semantics,
3. tone-control TBL0/TBL1 indexing/interpolation and LOW/MEDIUM/HIGH selection.

Those stages should now be investigated independently of WB/matrix provenance.
