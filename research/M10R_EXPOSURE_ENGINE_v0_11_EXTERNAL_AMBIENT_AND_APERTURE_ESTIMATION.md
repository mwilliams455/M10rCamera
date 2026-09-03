# M10-R Exposure Engine v0.11: External Ambient Sensor and Aperture Estimation

**Date:** 2026-09-03  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Original FW SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`  
**Decoded SHA-256:** `859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0`

## 1. Outcome

This pass closes the main role of the M10-R external ambient-light sensor and corrects an important possible modeling mistake.

`BvExt` is **not a second brightness value blended into final exposure Bv**. It belongs primarily to a separate working-aperture estimator. The camera compares the external/front ambient brightness coordinate against the traditional through-lens brightness coordinate and adds a calibrated reference aperture (`AV0`):

```text
estimated_working_Av ~= BvExt - TTL_Bv + AV0
```

That estimate is filtered, quantized, optionally remapped through a calibration threshold table, bounded, and converted to a familiar f-number. It is stored separately from final exposure Bv.

The production exposure calculator receives `AV0` as its Av reference input. It does **not** receive the dynamic BvExt-derived working-aperture estimate through the normal input-build path.

This creates a coherent rangefinder metering model:

```text
through-lens meter coordinate ~= scene_Bv - actual_Av + AV0

exposure allocator:
    Tv ~= TTL_Bv + Sv - AV0

external/front sensor reconstruction:
    actual_Av ~= BvExt - TTL_Bv + AV0
```

The fixed reference therefore cancels correctly in the exposure equation while allowing the camera to estimate the actual diaphragm setting without a mechanical aperture encoder.

## 2. External ambient-light transport

CTRL-System contains a framed external-device receive path with a `0xC3 0x3C` header, length/status handling, payload validation, and checksum processing. A validated frame reaches the message parser around `0x08029158`.

The firmware contains the diagnostic text:

```text
--- External ambient light sensor...
```

Message subtype `9` supplies two big-endian signed 16-bit exposure coordinates in payload bytes `+6..+9`:

```text
+6,+7 -> BvExt
+8,+9 -> BV_IR
```

CTRL does not derive those two values from raw light intensity in this receive path. They arrive already expressed as signed exposure coordinates.

The pair is passed to updater `0x080163A0`. That updater retains the previous pair unless either coordinate moves by more than 50 Q8.8 counts:

```text
50 / 256 = 0.1953125 EV
```

Thus the external sensor path already contains approximately 0.195-EV input hysteresis before the values enter the wider AE state.

## 3. Different roles of `BvExt` and `BV_IR`

The downstream xref survey found substantially more use of `BvExt` than `BV_IR`:

- `BvExt`: 18 accessor consumers in the surveyed CTRL image;
- `BV_IR`: 6 accessor consumers.

`BV_IR` consumers observed in this pass are predominantly state packing, notification, and diagnostic paths. No corresponding numerical path into the production exposure allocator has been established.

`BvExt`, in contrast, enters the aperture-estimation helper directly and also participates in AE change detection.

The already-recovered final-Bv update logic independently requests recomputation if `BvExt` moves outside a +/-25-count band:

```text
25 / 256 = 0.09765625 EV
```

That recomputation trigger does **not** mean `BvExt` is numerically blended into final Bv. It means an external-light change can invalidate downstream state, including the working-aperture estimate, even when selected TTL/CMOS Bv itself has remained inside its own deadband.

## 4. Working-aperture estimator `0x0800F98C`

The production final-Bv/update path calls `0x0800F98C` before committing final Bv. The relevant arguments are:

```text
r0 = selected/TTL Bv
r1 = BvExt
r2 = signed calibration_record[+0x13]  (AV0)
r3 = lower bound
stack = upper bound + mode/override flags
```

Two override flags can bypass the normal subtraction and force:

```text
Av_candidate = 0x0400 = 4.0 EV
```

Otherwise the normal path is:

```text
Av_candidate = BvExt - selected_Bv + AV0
if Av_candidate < 0:
    Av_candidate = 0
```

### Persistent raw deadband

The raw candidate is compared against persistent signed halfword state `0x2001AD24`.

The retained value updates only if:

```text
candidate > previous + 0x41
or
candidate < previous - 0x41
```

where:

```text
0x41 / 256 = 0.25390625 EV
```

Equality at exactly `previous +/- 65` retains the previous value.

### Half-stop floor

After temporal filtering, the firmware performs:

```text
value &= ~0x7F
```

The estimator is nonnegative at this point, so this floors the retained value to a 0.5-EV grid.

### Optional threshold remap

When the estimator's remap-mode flag is enabled, the half-stop-quantized value is compared with a threshold array rooted at RAM `0x20000040`.

Indexes `0..19` are the actual 20 runtime-configurable signed Q8.8 thresholds. The populated compiled default calibration block is 40 bytes and contains:

| Index | Q8.8 | EV |
|---:|---:|---:|
| 0 | 192 | 0.750000 |
| 1 | 320 | 1.250000 |
| 2 | 448 | 1.750000 |
| 3 | 524 | 2.046875 |
| 4 | 627 | 2.449219 |
| 5 | 729 | 2.847656 |
| 6 | 844 | 3.296875 |
| 7 | 960 | 3.750000 |
| 8 | 1100 | 4.296875 |
| 9 | 1203 | 4.699219 |
| 10 | 1331 | 5.199219 |
| 11 | 1459 | 5.699219 |
| 12 | 1587 | 6.199219 |
| 13 | 1740 | 6.796875 |
| 14 | 1843 | 7.199219 |
| 15 | 1958 | 7.648438 |
| 16 | 2073 | 8.097656 |
| 17 | 2227 | 8.699219 |
| 18 | 2355 | 9.199219 |
| 19 | 2483 | 9.699219 |

The source block resides at `0x08045714`. Initializer `0x0800E198` copies exactly `0x28` bytes into RAM `0x20000040`. If the incoming control object begins with bytes `1,0`, it instead copies 40 bytes supplied at object `+2`; otherwise it uses the compiled default source.

The consumer loop is slightly unusual. It reads sequential halfwords and returns:

```text
first index whose read_value >= candidate:
    remapped_Av = index * 0x80

or when index reaches 21:
    remapped_Av = 21 * 0x80
```

Index 20 is **not part of the configurable threshold table**. Address `0x20000068` is an adjacent 32-bit state used by another control path. Its recovered producer writes either integer `15` or `29` according to a separate mode bit.

Because a candidate reaches index 20 only after exceeding threshold 19 (`2483`, approximately 9.699 EV), the low halfword `15` or `29` at index 20 can never satisfy the comparison in the recovered production/default state. The loop therefore advances to index 21, where the explicit `index >= 21` test forces exit regardless of the halfword read there.

The effective production/default remap is therefore:

```text
20 configurable thresholds -> half-stop outputs 0.0 .. 9.5 EV
value above threshold[19]   -> terminal 10.5 EV output
```

A 10.0-EV remap output is skipped in the recovered normal state. It could occur only if the unrelated adjacent index-20 state were artificially large enough to satisfy the comparison, which its observed `15/29` values are not.

This tail behavior is now explicitly modeled in the executable oracle rather than represented as two fictitious threshold entries.

### Output bounds

The helper finally clamps the remapped/unmapped Av to caller-supplied limits.

The default initializer at `0x08010F1E` establishes:

```text
minimum = 0x0000 = 0 EV
maximum = 0x0C00 = 12 EV
```

## 5. Estimated aperture state is separate from final Bv

The aperture-estimation result is passed to setter `0x08011CCC`.

That setter stores:

```text
raw/estimated Av Q8.8 -> AE state +0x0C
```

and immediately invokes converter `0x0801CBFC`, storing its transformed result at:

```text
AE state +0x2E
```

Final Bv is committed separately through the final-Bv setter `0x08011CF0`.

This is direct instruction-level evidence that BvExt drives a distinct aperture state rather than being arithmetically merged into final Bv.

## 6. `AV0` is a factory calibration reference

The calibration record returned by `0x0801124C` contains a field at offset `+0x13` used by both the aperture-estimation path and the exposure-input builder.

The service routine associated with the firmware diagnostic:

```text
Adjust AV0 done.
```

writes this field.

The command accepts a signed value only when:

```text
0 <= supplied_AV0 <= 0x0C00
```

Otherwise it writes the default:

```text
AV0 = 0x0500 = 5.0 EV
```

It then sets the ambient-light calibration-validity bit and persists the calibration record.

Photographically:

```text
N = 2^(Av/2)
Av = 5.0 -> N ~= 5.65685
```

so the default is the canonical f/5.6 reference. This is consistent with AV0 being the optical zero/reference used to normalize the working-aperture TTL meter rather than the current physical diaphragm setting.

## 7. Exact production exposure-input identity

The AE input builder at `0x0800D91C` fetches the calibration-record pointer, then copies `record +0x13` into calculator input offset `+0x02`.

At calculator entry `0x080203B4`, the first coordinates are normalized by three distinct helpers:

| Input offset | Helper | Config limits | Identity |
|---:|---|---|---|
| `+0x00` | `0x0802159C` | TV min/max `+0x70/+0x6E` | Tv |
| `+0x02` | `0x0802164C` | AV min/max `+0x76/+0x74` | Av; production builder supplies AV0 |
| `+0x04` | `0x080215D6` | SV min/max `+0x6C/+0x6A` | Sv |
| `+0x06` | calculation-Bv path | — | final/cached Bv |

The dynamic aperture-estimate getter is **not called in this input-build sequence before `0x080203B4`**.

Within the same outer routine it is fetched only after the central exposure calculator returns, where it is copied into output/change-notification state.

Therefore the normal production exposure allocator uses the calibrated AV0 reference, not the dynamic front-sensor working-aperture estimate.

## 8. Why this equation works

Let:

```text
S = scene brightness in Bv-like coordinates
A = actual working aperture Av
A0 = calibrated AV0 reference
```

The working-aperture TTL meter can be represented as:

```text
TTL_Bv ~= S - A + A0
```

The APEX exposure relation is:

```text
Tv = S + Sv - A
```

Substituting the TTL coordinate gives:

```text
Tv ~= TTL_Bv + Sv - A0
```

which is exactly the form expected when the calculator receives TTL/final Bv together with fixed AV0.

The external sensor measures scene/ambient brightness without the taking lens attenuation, so working aperture can be reconstructed as:

```text
A ~= BvExt - TTL_Bv + A0
```

This explains the apparently unusual architecture without requiring the M10-R to know the mechanical aperture-ring position electronically.

## 9. Av -> f-number conversion `0x0801CBFC`

The converter explicitly:

1. converts signed Q8.8 Av to floating point;
2. divides by `512.0`, which is `(Av_Q8.8 / 256) / 2`;
3. loads the double constant `2.0`;
4. calls the firmware power helper.

Thus the mathematical conversion is:

```text
f_number = 2^(Av / 2)
```

For exact half-stop Av values (`Av % 0x80 == 0`) the firmware does not use the raw power result. It indexes a canonical Q8.8 f-number table at `0x0803D310`.

The recovered 25-entry table corresponds to:

```text
Av 0.0  -> f/1.0
Av 0.5  -> f/1.2
Av 1.0  -> f/1.4
Av 1.5  -> f/1.7
Av 2.0  -> f/2.0
Av 2.5  -> f/2.4
Av 3.0  -> f/2.8
Av 3.5  -> f/3.4
Av 4.0  -> f/4.0
Av 4.5  -> f/4.8
Av 5.0  -> f/5.6
Av 5.5  -> f/6.8
Av 6.0  -> f/8.0
Av 6.5  -> f/9.5
Av 7.0  -> f/11
Av 7.5  -> f/13
Av 8.0  -> f/16
Av 8.5  -> f/19
Av 9.0  -> f/22
Av 9.5  -> f/27
Av 10.0 -> f/32
Av 10.5 -> f/38
Av 11.0 -> f/45
Av 11.5 -> f/54
Av 12.0 -> f/64
```

The corresponding raw Q8.8 table is:

```text
0x0100, 0x0133, 0x0166, 0x01B3, 0x0200,
0x0266, 0x02CD, 0x0366, 0x0400, 0x04CD,
0x059A, 0x06CD, 0x0800, 0x0980, 0x0B00,
0x0D00, 0x1000, 0x1300, 0x1600, 0x1B00,
0x2000, 0x2600, 0x2D00, 0x3600, 0x4000
```

For non-half-stop Av, the power result is converted to Q8.8. The transformed path subsequently scales the human f-number representation and rounds it to familiar integer values such as:

```text
1400, 2800, 5600, 11000, 16000, ...
```

The stored `+0x2E` state is therefore a human/metadata-oriented aperture representation derived from the raw Av estimate.

## 10. External corroboration versus firmware proof

The conclusions above are based on static firmware analysis. They are independently consistent with Leica M10-series documentation/reviews describing the camera's method as comparing through-lens brightness with measured ambient/front-sensor brightness to estimate the aperture used for EXIF/lens-related processing.

That external description is corroboration, not the basis for the recovered equations or addresses.

## 11. Executable oracle

This pass adds:

```text
tools/m10r_aperture_estimator.py
tests/test_m10r_aperture_estimator.py
```

The oracle models:

- `BvExt - TTL_Bv + AV0` arithmetic;
- nonnegative clamp;
- forced Av=4 override;
- exact +/-65-count persistent raw deadband;
- 0.5-EV floor;
- the 20 recovered configurable remap thresholds;
- the adjacent index-20 read and index-21 terminal behavior;
- 0..12 EV default bounds;
- canonical half-stop f-number lookup;
- `2^(Av/2)` intermediate conversion;
- human/metadata f-number rounding.

The estimator tests pass as part of the full repository research suite.

## 12. Implication for the phone implementation

Do **not** treat the M10-R front ambient sensor as a second exposure meter to be blended with the phone's scene meter.

For M10-R exposure parity, the portable behavior of interest is primarily:

1. the working-aperture TTL/traditional meter coordinate and its AV0 reference;
2. the final-Bv selector/deadbands;
3. AE-lock cache behavior;
4. Tv/ISO allocation.

The external ambient path is valuable if the phone implementation needs to reproduce Leica-style estimated aperture metadata or lens-dependent behavior. It is not required as an extra exposure-weighting term merely because `BvExt` participates in recomputation triggers.

## 13. Next investigation target

With the external ambient path separated from exposure allocation, the highest-value remaining exposure target is the **traditional meter acquisition dynamics**:

- what event/cadence invokes selector-5 sampling;
- how the 10 ADC samples are timed relative to release-button states and AE calculation;
- whether the negative-Bv 300-ms latch changes acquisition cadence or only source acceptance;
- where temporal smoothing exists beyond the 10-sample average and the already-recovered deadbands;
- when a fresh traditional Bv is considered valid for the exposure allocator.

That timing/state behavior is more directly portable to a phone metering implementation than the external aperture-estimation subsystem.
