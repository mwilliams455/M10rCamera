# M10-R v2.24 — DNG AsShotNeutral → CA9 integer WB gain reconstruction EMPIRICAL FROZEN

Status: **FROZEN for first-parity renderer reconstruction**, with a deliberately narrower evidence class than a direct firmware-writer identity.

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

Firmware SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Frozen reconstruction rule

For Leica M10-R DNG first-parity reconstruction, recover the three CA9 integer WB gains from DNG `AsShotNeutral` as:

```text
gainR = round(256.0 / AsShotNeutral.R)
gainG = round(256.0 / AsShotNeutral.G)
gainB = round(256.0 / AsShotNeutral.B)
```

Then apply the already-frozen CA9 clamp:

```text
1 <= gain[channel] <= 2000
```

The firmware-side normalized neutral representation is:

```text
ASN[channel] = 256.0 / integer_gain[channel]
```

Thus the first-parity DNG reconstruction is the exact inverse of the frozen live CA9 gain→ASN ABI.

## 2. Six-capture empirical proof

v2.22 tested the same six public Leica M10-R DNGs used by the v2.20/v2.21 same-capture JPEG/DNG renderer-order experiment.

All six DNGs contained `AsShotNeutral`, and all six reconstructed to clean integer gains:

```text
sample 01  ASN = [0.2853957637, 1.0, 0.6564102564]  -> [897, 256, 390]
sample 02  ASN = [0.2969837587, 1.0, 0.6289926290]  -> [862, 256, 407]
sample 03  ASN = [0.2853957637, 1.0, 0.6530612245]  -> [897, 256, 392]
sample 04  ASN = [0.2892655367, 1.0, 0.6213592233]  -> [885, 256, 412]
sample 05  ASN = [0.2853957637, 1.0, 0.6614987080]  -> [897, 256, 387]
sample 06  ASN = [0.2813186813, 1.0, 0.6614987080]  -> [910, 256, 387]
```

Re-encoding those integers through the firmware formula `256.0 / gain` reproduces the DNG values to decimal-export precision:

```text
valid AsShotNeutral samples       = 6 / 6
all gains inside firmware clamp   = true
max absolute round-trip error     = 4.336681014294186e-11
max relative round-trip error     = 1.5195323707932758e-10
```

The green component is exactly `1.0` in every tested DNG and reconstructs to integer gain `256` in every case, matching the firmware normalization convention.

## 3. Live firmware side independently confirmed

The v2.23 IMG-System trace re-confirmed the live wrapper reading the three integer WB fields from the IMG parameter object:

```text
input +0xF4  R gain
input +0xF6  G gain
input +0xF8  B gain
```

and independently found the shared ASN block rooted at:

```text
0x43705760
```

The existing v1.45 freeze remains authoritative for the exact live ABI:

```text
integer gain -> clamp [1,2000] -> ASN double = 256.0 / gain
```

## 4. Evidence boundary — what is NOT frozen

This note does **not** claim that the M10-R firmware DNG writer has been directly proven to copy the shared CA9 ASN block into TIFF/DNG tag `0xC628` (`AsShotNeutral`).

v2.23 intentionally searched only IMG-System for coherent known-DNG-tag tables and writer references. It did not expose a sufficiently strong direct tag-writer→ASN source edge.

Therefore distinguish:

```text
FROZEN empirical first-parity identity:
    DNG AsShotNeutral numerically equals the frozen CA9 ASN representation
    across the six verified M10-R captures.

NOT frozen as direct firmware provenance:
    DNG tag 0xC628 is written directly from shared CA9 ASN address 0x43705760.
```

The lack of direct writer proof does not block renderer reconstruction because the numerical representation already round-trips the live ABI essentially exactly.

## 5. Renderer implication

The earlier green-channel proxy is no longer necessary for white-balance reconstruction.

For each M10-R DNG, a first-parity renderer can now recover the exact integer-form WB input expected by the proven CA9 color-management path:

```text
DNG AsShotNeutral
    ↓ round(256 / ASN)
CA9-form integer WB gains
    ↓ 256 / gain
firmware-form ASN doubles
    ↓
NeutralToXY → SetWhiteXY → MapWhiteMatrix
    ↓
rendered CC0 / CC1
```

The next unresolved dependency is therefore **rendered CC reconstruction**, not WB provenance.

## 6. Next investigation boundary

Determine whether the CA9 `NeutralToXY`, `FindXYZtoCamera`, `SetWhiteXY`, and `MapWhiteMatrix` implementation can be reproduced exactly from the DNG-visible inputs and frozen camera profile state.

Priority checks:

1. identify the exact Bradford/adaptation constants used by `MapWhiteMatrix`;
2. freeze `NeutralToXY` iteration/tolerance behavior;
3. freeze the dual-illuminant interpolation used by `FindXYZtoCamera`;
4. determine whether any per-capture input other than DNG `AsShotNeutral` enters the rendered CC calculation;
5. if no hidden scene-varying input remains, implement a software CA9 color-spec reconstruction and feed it into the v2.21 `TONE MEDIUM → DG` renderer-order oracle.
