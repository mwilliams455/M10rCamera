# M10-R Exposure Engine Recon v0.02 — CTRL-System and Photon Boundary

Firmware: `M10-R-30.22.23.34-Customer.FW`

This note extends `M10R_EXPOSURE_ENGINE_v0_01.md`. It records newly verified binary structure, instruction-level AE configuration findings, additional metering/calibration evidence, and the intended boundary for a future PhotonCamera-based M10-R implementation.

## 1. Reproducible firmware extraction

Two tools now exist in this repository:

- `tools/m10r_unpack.py` — deterministic Leica COMP decoder.
- `tools/m10r_sections.py` — parser/extractor for the decoded Leica section table.

The decoded image SHA-256 is:

```text
859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0
```

The decoded top-level firmware header reports:

```text
section count = 102
section table size = 0xE8B0
section table offset = 0x24
section entry size = 584 bytes (0x248)
```

The previously observed 584-byte repetition is therefore explained: it is the fixed section-descriptor size, not an image predictor.

## 2. Exposure binary isolated

Section 90 is:

```text
Name:       CTRL-System
Rel offset: 0x0672D210
Size:       0x0004C548 = 312,648 bytes
Image base: 0x08000000
Aux:        0x00002000
```

`CTRL-System` begins with an ARM-style vector/address table and contains the Leica Camera Control exposure, shutter, meter, wheel, service and adjustment logic.

This means exposure reverse engineering can now focus on a ~305 KiB image instead of the complete 125 MiB decoded firmware.

## 3. AE configuration verified from instructions

The AE configuration state is at RAM address:

```text
0x2001A6F8
```

The default initializer at approximately `0x080213F0` writes the following values directly:

```text
+0x68 SV step = 0x0100 = 1 EV
+0x6A SV max  = 0x0C00 = 12 EV
+0x6C SV min  = 0x0500 = 5 EV
+0x6E TV max  = 0x0C00 = 12 EV
+0x70 TV min  = 0xF900 = -7 EV
+0x72 AV step = 0x0100 = 1 EV
+0x74 AV max  = 0x0C00 = 12 EV
+0x76 AV min  = 0x0000 = 0 EV
+0x78 SV table pointer = null by default
+0x7C AV table pointer = null by default
+0x80 SV table size = 0 by default
+0x81 AV table size = 0 by default
```

The default limits are therefore now instruction-level verified rather than inferred from text.

## 4. Clamp / table-snap helpers

Three helpers immediately following the main AE routine confirm the field roles.

### TV clamp — ~0x080215A0

Reads:

```text
TV min from config +0x70
TV max from config +0x6E
```

and clamps the signed Q8.8 TV input.

### SV clamp/table snap — ~0x080215DA

Reads:

```text
SV min from +0x6C
SV max from +0x6A
```

and, when AE-control type enables the table path, uses:

```text
SV table pointer +0x78
SV table size    +0x80
```

before returning the signed SV.

### AV clamp/table snap — ~0x08021650

Reads:

```text
AV min from +0x76
AV max from +0x74
```

and, when enabled, uses:

```text
AV table pointer +0x7C
AV table size    +0x81
```

A shared nearest-table-value helper starts at approximately `0x080216D0` and walks signed 16-bit table entries by absolute distance.

This confirms that the production AE representation is continuous signed Q8.8 first, with optional discrete snapping layered on top.

## 5. Main AE routine confirmed

The main AE routine starts at approximately:

```text
0x080203B8
```

(`0x080203B4` is immediately adjacent data/alignment; the real Thumb function prologue is visible at `0x080203B8`).

The first operations independently confirm the input offsets recovered in v0.01:

```text
+0x00 TV -> TV clamp helper
+0x02 AV -> AV clamp/table helper
+0x04 SV -> SV clamp/table helper
+0x0A P-shift -> quantization helper
```

The routine also accesses the flags at `+0x25`, including the Auto-ISO/AE-lock/bracketing/flash paths already mapped in v0.01.

## 6. Additional metering state exposed by Leica diagnostics

The CTRL-System debug state explicitly distinguishes:

```text
TTL:   four integer values
EXT:   four integer values
Tlog
Tlm20
Av
AvMan
Bv
Tv
TvMan
Sv
SvMan
Ev
dEv
AvAdj
f
BvExt
BvCMOS
```

This is important architectural evidence. Leica does not treat all of these as aliases for one generic brightness variable.

Interpretation still requiring exact xref tracing:

- the four TTL/EXT values may be raw, filtered, calibrated or staged measurements;
- `Tlog` and `Tlm20` are clearly internal meter-domain quantities but their exact equations remain to be recovered;
- `AvAdj` appears in the aperture/meter-calibration path;
- `BvExt` and `BvCMOS` remain distinct even when final `Bv` has already been selected.

Do not assign production semantics to the four-value arrays until their call sites are reconstructed.

## 7. External-light calibration is brightness-dependent

The external ambient-light calibration/debug path explicitly contains anchor corrections at:

```text
BV -2
BV  0
BV  3
BV 10
```

with separate reported function slopes for:

```text
BV -2 -> 0
BV  0 -> 3
BV  3 -> 10
```

The firmware exposes messages for:

```text
Adjust value for BV -2
Adjust value for BV 0
Adjust value for BV 3
Adjust value for BV 10
Function slope for BV 0 - BV -2
Function slope for BV 3 - BV 0
Function slope for BV 10 - BV 3
```

This is strong evidence that at least the EXT meter calibration is piecewise brightness-dependent rather than one constant EV offset.

This does **not** yet prove the same exact calibration shape for the final TTL BV path, but it strongly reinforces a key cross-generation lesson for M9 work: meter calibration should be treated as a function of meter state/brightness until evidence supports reducing it to one constant.

## 8. Mechanical aperture path remains important

The firmware continues to report both:

```text
AV
measured AV
```

and the v0.01 reconstruction of the measured-AV estimator remains consistent with the newly isolated controller image.

The debug state also explicitly contains:

```text
Av
AvMan
AvAdj
```

which supports a layered model:

```text
meter-derived aperture estimate
+ calibration/adjustment
+ manual/selected state
-> AV supplied to AE
```

Exact precedence remains a target for further tracing.

## 9. Important consequence for a future Photon M10-R profile

A phone camera has a fixed physical aperture. Therefore a Photon implementation should **not** mechanically reproduce the M10-R's EXT-vs-TTL aperture-estimation subsystem just because the Leica firmware contains it.

Instead, preserve the M10-R AE coordinate system while adapting the physical input layer:

```text
phone sensor meter proxy
        |
        v
M10-R-like BV estimator/calibration
        |
        v
fixed phone AV expressed in Q8.8 APEX
        |
        v
M10-R AE target equation
        |
        v
TV/SV constraint solver
        |
        v
Photon Camera2 exposure time + ISO allocation
```

The photographic policy should be ported; hardware-specific mechanisms should be translated.

## 10. Shared Photon infrastructure boundary

When implementation begins, M10-R should reuse the stable generic infrastructure proven by the M9 project where that infrastructure is camera-agnostic:

```text
Photon/Camera2 session management
capture ownership and queues
DNG creation
JPEG/DNG naming and save flow
12 MP routing where appropriate
metadata/timing framework
native-processing infrastructure
threading and queue safety
lens/device discovery
```

It should **not** inherit M9-specific photographic policy by default:

```text
M9 TC20 meter calibration
M9 VirtualBV calibration
M9 Auto-ISO constants
M9 ISO160 base assumptions
M9 R3.8/H25/TG1 renderer
M9 Cobalt calibration
M9 LUMA2.4 exposure feedback
M9 backlight thresholds
M9 motion/exposure constants unless separately justified
```

The intended architecture is therefore:

```text
                 Photon shared camera platform
                           |
             +-------------+-------------+
             |                           |
             v                           v
       M9 personality              M10-R personality
       / meter / AE                / meter / AE
       / renderer                  / renderer
```

not:

```text
M9Camera fork -> edit constants until it looks like M10-R
```

## 11. M10-R implementation gate

Do not begin the full M10-R renderer yet.

A useful first Photon milestone becomes justified once the following are stable enough:

1. final production BV source and calibration path;
2. exact Auto-ISO / TV-ISO behavior;
3. fixed-AV adaptation strategy for the phone;
4. default/base ISO behavior and discrete SV table;
5. 1/f / focal-length shutter policy where applicable;
6. user Override semantics;
7. a diagnostic-only AE oracle that can produce expected TV/SV from synthetic BV/AV inputs.

At that point the first Photon M10-R build should be **diagnostic/capture only**, with no attempt yet to claim final M10-R rendering parity.

## 12. Proposed first Photon stages

### `M10R-PHOTON0A` — shared-platform bootstrap

- build from a clean Photon baseline or shared camera core;
- prove capture, DNG, JPEG, metadata and queue stability;
- no M9 renderer inheritance;
- no M10-R exposure mutation yet.

### `M10R-AE1A` — diagnostic APEX engine

Log:

```text
meterProxy
virtualBvEv / virtualBvQ8_8
fixedAvEv / fixedAvQ8_8
overrideEv
requestedTvEv
requestedSvEv
selectedIso
selectedExposureNs
constraint/limit reason
```

No capture mutation initially.

### `M10R-AE1B` — bounded live allocation

Only after oracle parity and scene validation:

- allow the M10-R AE solver to request signed exposure changes;
- route requests through safe Camera2/Photon physical constraints;
- retain complete diagnostics.

### Rendering track

Begin independently after exposure/capture behavior is stable enough to produce useful DNG/JPEG reference captures.

## 13. Cross-project significance

The M10-R analysis continues to support the M9 project's move toward a virtual Leica meter/BV abstraction.

The newer firmware confirms that Leica separates:

```text
measurement
calibration
BV selection
user Override
AE arithmetic
TV/AV constraints
SV/Auto-ISO allocation
```

The new piecewise EXT calibration evidence further argues against treating scene exposure as one universal correction constant.

For M9, this strengthens `M9VirtualBv` as the next diagnostic direction.

For M10-R, it gives a clean path to a future Photon implementation without coupling that implementation to M9-specific photographic behavior.

## 14. Next reverse-engineering targets

Priority order:

1. trace the production final-BV update around the `Update BV value for calculation` path;
2. recover the equations/roles of `Tlog` and `Tlm20`;
3. identify exactly what the four TTL and four EXT diagnostic values represent;
4. reconstruct piecewise EXT raw->BV calibration numerically;
5. trace `TV ISO` generation from focal length / Auto-ISO settings;
6. recover the production SV table and ISO mapping;
7. recover the 22-entry AV table and distinguish it from phone adaptation needs;
8. turn the AE routine into a host-side executable oracle.

**Status:** exposure architecture stable enough for parallel M9/M10-R research; not yet at full M10-R Photon photographic implementation gate.
