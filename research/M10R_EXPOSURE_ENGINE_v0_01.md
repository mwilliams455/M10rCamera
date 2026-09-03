# M10-R Exposure Engine Recon v0.01

Firmware: `M10-R-30.22.23.34-Customer.FW`

Purpose: reconstruct the Leica M10-R still-exposure / metering architecture and use it as a cross-generation reference for the M9 exposure project. This document separates instruction-level findings from interpretation. It does **not** propose copying M10-R policy into M9 unchanged.

## 1. Executive finding

The M10-R uses a coherent APEX-domain exposure engine rather than a scene classifier that directly emits a positive exposure boost.

The architecture recovered so far is:

```text
meter hardware / CMOS scene estimate
        |
        +--> TTL Bv
        +--> EXT Bv
        +--> EXT-IR Bv
        +--> CMOS Bv
        |
        +--> measured-aperture AV estimate where needed
        |
        v
selected / calibrated Bv
        |
        v
AE equation in Q8.8 APEX units
        |
        +--> user Override / exposure compensation
        +--> exposure-correction term
        +--> per-SV correction
        |
        v
program solver (M / A / T / P / Bulb)
        |
        +--> TV / AV bounds
        +--> 1/f TV rule
        +--> flash/strobo constraints
        +--> bracketing / P-shift
        |
        v
Auto-ISO residual solver
        |
        +--> discrete SV table / min / max
        |
        v
final TV, AV, SV and dEV
```

All main photographic exposure coordinates use signed 16-bit Q8.8 APEX units:

```text
1 EV = 0x0100 = 256
```

This strongly converges with the independently recovered M9 Q8.8 APEX controller.

---

## 2. Camera-control subsystem

The exposure engine is in an ARM/Thumb Leica Camera Control subsystem, distinct from the MIPS/OpenWrt Linux side of the firmware.

Recovered identity strings include:

```text
AE library: LCC AEAlgorithm V%i.%i ...
Application: LCC Honey
```

The debug/service interface exposes operations corresponding to:

```text
SetTV
SetISO
SetAV
AE lock
metering mode
exposure compensation
Auto ISO configuration
```

This subsystem therefore owns the actual photographic exposure policy rather than delegating it to Linux.

---

## 3. AE initialization and default domain

AE configuration pointer:

```text
RAM 0x2001A6F8
```

Default configuration is loaded by the AE initializer when no explicit init block is supplied.

Recovered defaults / limits:

| Field | Raw | EV interpretation |
|---|---:|---:|
| SV step | `0x0100` | 1 EV |
| SV min | `0x0500` | 5 EV = ISO 100 |
| SV max | `0x0C00` | 12 EV ≈ ISO 12,800 |
| TV max | `0x0C00` | 12 EV ≈ 1/4096 s |
| TV min | `0xF900` | -7 EV = 128 s |
| AV step | `0x0100` | 1 EV |
| AV min | `0x0000` | 0 EV |
| AV max | `0x0C00` | 12 EV |

The config also contains:

- 52 signed halfwords of per-SV correction;
- SV table pointer / size;
- AV table pointer / size;
- AE-control type;
- debug level.

Recovered helpers perform:

- signed APEX quantization to configured step;
- TV clamp;
- SV clamp and optional table snap;
- AV clamp and optional table snap;
- nearest / next-higher / previous table lookup;
- constraint and Auto-ISO redistribution.

---

## 4. AE input structure

Main AE routine:

```text
VA 0x080203B4
```

Input structure:

| Offset | Meaning |
|---:|---|
| `+0x00` | TV |
| `+0x02` | AV |
| `+0x04` | SV |
| `+0x06` | BV |
| `+0x08` | Override |
| `+0x0A` | P-shift EV |
| `+0x0C` | Strobo TV |
| `+0x0E` | Threshold TV |
| `+0x10` | TV ISO |
| `+0x12` | 1/f TV |
| `+0x14` | Exposure correction |
| `+0x16` | EV limit |
| `+0x18` | Bracketing step |
| `+0x1C` | Bracketing picture index / number |
| `+0x20` | Number of bracket pictures |
| `+0x24` | Program |
| `+0x25` | Flags |

Program values:

```text
0 = M
1 = A
2 = T
3 = P
4 = Bulb
```

Flags include:

```text
bit 0 = Auto ISO
bit 1 = AE lock
bit 2 = Bracketing
bit 3 = Flash ready
bit 4 = Strobo
```

The firmware's own diagnostic CSV headings independently match these offsets.

---

## 5. AE output structure

Output:

| Offset | Meaning |
|---:|---|
| `+0x00` | TV |
| `+0x02` | AV |
| `+0x04` | SV |
| `+0x06` | dEV |
| `+0x08` | P-shift EV |
| `+0x0A` | Bracketing EV |
| `+0x0C` | warning bits |

Warning bits include overexposure, underexposure and strobo warnings.

---

## 6. Central exposure equation

The recovered instruction sequence computes an exposure target equivalent to:

```text
EV_target =
      BV
    + SV
    - Override
    - ExposureCorrection
    - SVCorrection[SV_index]
```

The selected exposure program then tries to satisfy:

```text
TV + AV ~= EV_target
```

The final residual is equivalent to:

```text
dEV =
      BV
    + SV
    - TV
    - AV
    - Override
    - ExposureCorrection
    - SVCorrection
```

This is classical APEX-domain exposure arithmetic.

### User exposure compensation

The normal user exposure-compensation value is supplied to the AE library through the `Override` input.

It is therefore distinct from:

- meter calibration;
- Auto-ISO;
- per-SV correction;
- separate internal ExposureCorrection.

A positive user compensation lowers the required `TV + AV` and therefore increases exposure, as expected.

---

## 7. Program behavior

### M mode

TV and AV are user/program fixed. If Auto ISO is active, the solver moves SV to satisfy the exposure equation within configured limits.

Conceptually:

```text
SV_required ~= TV + AV - BV + Override + corrections
```

This is the direct newer-generation analogue of the recovered M9 fixed-TV AUTO-SV solve.

### A mode

The routine begins with:

```text
TV = EV_target - AV
```

Then it applies flash/strobo constraints and the Auto-ISO shutter threshold (`TV ISO`) when Auto ISO is active.

`TV ISO` behaves as the shutter-value trigger / preference boundary at which residual exposure begins moving into SV.

This is closely analogous to the M9 `Slowest speed` / lens-dependent AUTO-ISO activation threshold.

### T mode

The routine begins with:

```text
AV = EV_target - TV
```

Then AV limits and Auto-ISO constraints redistribute residual EV as needed.

### P mode

P mode explicitly uses the `1/f TV` input.

The recovered program line is anchored approximately around:

```text
lower = (1/f TV) + AV_min
upper = lower + 2 * (AV_max - AV_min)
```

Within the normal range, TV and AV are redistributed around the 1/f reference before table snapping / clamping. At the ends, AV is held at min or max and TV absorbs the remaining EV.

Auto ISO is invoked only when the TV/AV program constraints cannot satisfy the exposure target.

### Bulb

Bulb uses the configured slow-TV boundary (`TV_min`, default -7 EV / 128 s).

---

## 8. Auto ISO

Auto ISO is **not** an exposure-brightening heuristic.

The recovered sequence is constraint driven:

1. Start from configured minimum SV.
2. Solve the requested program's TV/AV against the target EV.
3. Apply TV/AV limits and mode-specific thresholds.
4. If those constraints leave unresolved EV, transfer that residual into SV.
5. Snap/clamp SV against the configured Leica sensitivity table and min/max bounds.
6. If SV cannot absorb the residual, TV/AV carry the remaining error subject to their constraints.

This architecture is important for M9 work because it prevents ISO selection from being conflated with metering compensation.

---

## 9. Metering topology

The LCC state retains separate brightness values for:

```text
TTL
EXT
EXT IR
BvCMOS
final BV
```

The still-exposure diagnostic explicitly reports:

```text
BV_Ext
BV_IR
BV
AV
SV
TV
ISO
exposure time
```

### Final BV source

The recovered source selector uses:

- TTL-derived BV in the traditional still/rangefinder path;
- BvCMOS in live-view / sensor-metered paths.

During source changes it applies an approximately:

```text
25 / 256 EV = 0.09765625 EV
```

stability band / hysteresis.

This means Leica does not simply expose from one generic image-luma number.

### Fixed BV storage calibration

The final-BV state setter stores a value offset by:

```text
59 / 256 EV = 0.23046875 EV
```

and the corresponding internal getter restores the 59-count offset.

This should be treated as a calibration / coordinate offset in this path, not as user exposure compensation and not as a universal +0.23 EV photographic bias.

---

## 10. Measured aperture estimation

This is an especially important finding for understanding a mechanical M lens.

The firmware has two aperture states that its debug text labels as:

```text
selected AV
measured AV
```

The measured-AV setter is called directly from a routine at:

```text
VA 0x0800F98C
```

The firmware debug string prints the pair as:

```text
(AV 0x%04X, k %i) (measured AV 0x%04X, k %i)
```

The estimator's core arithmetic is:

```text
AV_estimate = meter_B - meter_A + calibration
```

In the traditional TTL branch, one of those meter inputs is explicitly `EXT` and the other is the selected final meter value, which in that path is TTL. Thus the normal mechanical-lens case reduces structurally to:

```text
measured_AV ~= EXT_BV - TTL_BV + calibration
```

before stabilization / quantization / clamping.

The estimator then:

1. clamps negative results to zero;
2. applies approximately `+/- 0x41` counts of hysteresis:
   `65/256 = 0.25390625 EV`;
3. clears the low 7 bits, giving 0.5-EV quantization;
4. can snap to a 22-entry AV table;
5. clamps to configured AV minimum and maximum.

Two invalid/unavailable conditions immediately return:

```text
0x0400 = AV 4.0 EV = f/4
```

as the fallback estimate.

This is strong evidence that the M10-R uses the relation between external and TTL metering to infer the manually selected aperture sufficiently well for full APEX calculations.

It also explains why `EXT` is retained even though final traditional-still BV is TTL-derived.

---

## 11. M9 cross-generation comparison

The independent M9 firmware investigation already established:

```text
EvDiff = 5 + TV - SV - BV + Override
```

and therefore at nominal exposure:

```text
TV = BV + SV - 5 - Override
```

For AUTO sensitivity:

```text
SV_required = 5 + TV + Override - BV
```

M9 facts already recovered:

- Q8.8 exposure domain (`1 EV = 256`);
- normal BV uses scalar TTL meter channel 0;
- fixed ISO uses Leica's exact discrete SV table;
- AUTO ISO walks a discrete permitted-SV table;
- AUTO begins at ISO160;
- `Slowest speed` / lens-dependent TV is the ISO-activation threshold, not a permanent hard shutter floor;
- lens-dependent shutter behavior is approximately reciprocal-focal-length;
- at max ISO, shutter is allowed to become slower than the preference threshold;
- normal scene exposure is not based on RGB / WB / CCT image histogram logic.

### What M10-R adds

M10-R confirms the same Leica design philosophy but makes several elements more explicit:

| Concept | M9 | M10-R |
|---|---|---|
| Exposure domain | Q8.8 APEX | Q8.8 APEX |
| Core scene coordinate | TTL-derived BV | TTL or CMOS BV by mode |
| User exposure comp | Override term | Override term |
| ISO | discrete Leica SV states | discrete/configurable SV table |
| Auto ISO | threshold + SV solve | constraint solver + SV residual |
| Lens-dependent shutter | proven helper | explicit `1/f TV` input |
| Aperture term | largely implicit/reduced in recovered equation | explicit AV |
| Mechanical-lens aperture | not yet reconstructed as separate variable | explicit selected + measured AV, EXT/TTL estimator |
| Meter calibration | per-body BV calibration and fixed terms | separate BV coordinate/calibration offsets |
| Image-histogram backlight classifier | not authentic normal meter path | not the core AE architecture |

The two cameras therefore appear to share a stable Leica exposure philosophy rather than two unrelated implementations.

---

## 12. Consequence for current M9Cam exposure work

The current Android M9Cam LUMA2.4 feedback path is architecturally different from both recovered Leica cameras.

Current behavior is approximately:

```text
preview luma statistics
    -> backlight-starvation score
    -> recommendation 0 .. +0.75 EV only
    -> multiply Photon target exposure energy by 2^EV
```

That approach is useful diagnostically but cannot naturally express:

```text
-1.0 EV
-0.75 EV
-0.5 EV
0 EV
+0.5 EV
+0.75 EV
+1.0 EV
```

as outcomes of one metering model.

The cross-generation evidence suggests a better question:

```text
"What BV would a Leica-like meter assign to this scene?"
```

rather than:

```text
"Does this image look backlit enough to deserve positive EV?"
```

Then signed exposure correction follows from the disagreement between:

```text
Photon/phone scene target
and
Leica-like virtual-meter BV
```

instead of being generated by a one-direction scene classifier.

---

## 13. Recommended parallel experiment for M9

Do not replace the current controller immediately.

Add a **diagnostic-only virtual-BV bridge** alongside LUMA2.4.

Suggested stages:

```text
linear preview / meter proxy
        |
        v
M9-like centre-weighted scalar reading
        |
        v
temporal averaging
        |
        v
virtual raw-meter -> BV calibration (Q8.8)
        |
        +---------------------+
        |                     |
        v                     v
exact M9 APEX solve       Photon current target
        |                     |
        +---------- compare --+
                   |
                   v
             signed delta EV
```

Log at minimum:

```text
virtualBvQ8_8
virtualBvEv
photonEquivalentBvEv
signedMeterDeltaEv
M9SvQ8_8 / selected ISO state
M9TvTargetQ8_8
M9TvThresholdQ8_8
autoIsoActivation
autoIsoBoundHit
finalPredictedTv
finalPredictedSv
currentLuma24RecommendedEv
```

The first build should **not apply** the signed correction. It should collect paired predictions against the existing field examples.

Only after validation should a bounded signed correction be considered.

### Why signed BV error is preferable

A BV-domain error naturally allows:

```text
positive correction:
phone/Photon meter is too dark relative to virtual Leica target

negative correction:
phone/Photon meter is too bright relative to virtual Leica target

near zero:
current allocation is already consistent
```

This directly addresses the observed requirement that different backlit / high-contrast scenes can need opposite corrections.

---

## 14. Important caution

Do not transplant the M10-R's numeric calibration constants into M9.

In particular, do not copy:

```text
59/256 EV BV storage offset
25/256 EV source-switch band
65/256 EV measured-AV hysteresis
M10-R SV/TV/AV default limits
```

into M9Cam merely because they are Leica values.

Their value is architectural:

- meter calibration is separate from user compensation;
- meter source selection is separate from AE solving;
- aperture estimation is separate from BV;
- Auto ISO is a constraint response;
- all exposure decisions live in one signed EV coordinate system.

M9 should continue using its own recovered firmware constants and its own empirical virtual-meter calibration.

---

## 15. Next reverse-engineering targets

### M10-R

1. Trace exact producer/calibration term entering measured-AV estimator.
2. Recover the 22-entry AV table and map all entries to f-numbers.
3. Recover exact `TV ISO` producer from Auto-ISO settings, including focal-length-dependent behavior.
4. Trace EXT-IR's numerical role.
5. Identify meter-mode-specific weighting / source behavior.
6. Recover exact ISO table and any per-SV correction values used by production configuration.
7. Confirm AE-lock timing and which BV source is frozen.
8. Trace whether highlight or clipping information contributes upstream to BV measurement, rather than downstream as an exposure boost.

### M9

1. Preserve the already recovered BODY Q8.8 APEX controller.
2. Stop expanding positive-only LUMA correction as the final exposure architecture.
3. Build a diagnostic virtual TTL -> BV bridge.
4. Re-evaluate existing positive and negative field samples in signed BV space.
5. Keep renderer/color frozen while metering is investigated.
6. Only promote a signed correction after it predicts both positive and negative controls reliably.

---

## 16. Current conclusion

The tandem M9/M10-R investigation is productive.

The M10-R does not show a newer Leica replacing APEX metering with opaque scene AI. Instead it exposes a more elaborate version of the same photographic architecture already recovered from the M9:

```text
meter -> BV
+
camera state -> AV / SV / constraints
+
user Override
=
deterministic APEX exposure solve
```

The largest practical implication for M9Cam is that the unresolved exposure problem should now be framed as **virtual Leica metering / BV calibration**, not as a search for one correct positive backlight EV boost.
