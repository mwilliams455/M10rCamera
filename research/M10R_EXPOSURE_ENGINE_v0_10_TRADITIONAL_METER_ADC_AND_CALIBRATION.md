# M10-R Exposure Engine v0.10: Traditional Meter ADC and Calibration Model

## Outcome

The traditional/rangefinder Bv producer is now recovered far enough to model its firmware-defined behavior directly.

This note **supersedes the ownership interpretation in v0.09**. v0.09 correctly identified selector `5` and the 9-byte `AE measure result` receive contract, but its statement that the numerical producer must lie outside CTRL-System was too strong. CTRL-System contains a local selector-5 constructor at `0x080184D8`, and the production exposure selector at `0x0800D6A8` calls that constructor directly with selector `5`.

The normal traditional Bv path is:

```text
ADC selector 5
    -> physical ADC input channel 6
    -> 10-sample average
    -> four-anchor piecewise calibration
    -> signed normal-mode calibration offset
    -> Q8.8 traditional Bv
    -> temperature-dependent meter-validity hysteresis
    -> selector-5 9-byte AE-result packet
    -> CTRL AE-result handler 0x0800E1EC
    -> traditional Bv state +0x14
```

A second ADC input, channel 5, is used to derive the `Tlog` coordinate. Static arithmetic and range boundaries make `Tlog` strongly consistent with temperature in tenths of a degree Celsius.

## 1. Selector-5 packet is constructed locally in CTRL

The generic dispatcher at `0x0801D6DA` uses its first argument as a signed selector. Selector `5` reaches the AE-result handler:

```text
r0 == 5
    -> 0x0801D886
    -> BL 0x0800E1EC
```

The local constructor at `0x080184D8` has a matching case `5`. It builds exactly nine bytes:

| Packet offset | Constructor source |
|---:|---|
| `+0x00` | `0x0802D678(calibration[+0x18])` -> Tlog |
| `+0x02` | `0x0802D6DC(0, cal, cal[+0x14], cal[+0x10], cal[+0x18])` -> traditional Bv |
| `+0x04` | `0x2001AC74 + 0` -> BvExt |
| `+0x06` | `0x2001AC74 + 2` -> BV_IR |
| `+0x08` | `0x0802D7F4()` -> status |

It then calls:

```text
r0 = 5
r1 = &packet
r2 = 9
BL 0x0801D6DA
```

The constructor has multiple direct callers. Most importantly, the final-Bv source selector at `0x0800D6A8` executes `movs r0,#5 ; BL 0x080184D8` on the calibrated traditional-meter path before reading the updated traditional/CMOS state. Therefore this is not merely an isolated debug packet builder.

## 2. Physical ADC path

The hardware getter is `0x08018260`.

In its normal hardware branch it configures the peripheral whose base is `0x40012000`, starts a conversion, polls completion, and finally reads the 16-bit result from peripheral offset `+0x4C`.

The firmware-level selector maps to the hardware ADC input passed to `0x08032238` as follows:

| Firmware selector | ADC input argument |
|---:|---:|
| `1` | `7` |
| `2` | `3` |
| `3` | `4` |
| `4` | `5` |
| `5` | `6` |
| other/default | `4` |

For the traditional meter specifically:

```text
selector 4 -> ADC input 5 -> Tlog path
selector 5 -> ADC input 6 -> traditional light-meter path
```

The getter waits for conversion-complete and returns the peripheral data-register value as an unsigned 16-bit integer.

## 3. Normal traditional-meter sampling

The normal Bv producer is `0x0802D6DC` with mode `0`.

It first derives Tlog from the stored reference at calibration `+0x18`. It then selects the normal analog mode through the `0x40021000` control path, waits three firmware delay units, and samples ADC selector `5` ten times:

```text
sample_sum = ADC6()
repeat 9 times:
    delay(1)
    sample_sum += ADC6()

average = sample_sum // 10
```

The integer division is unsigned and therefore floors the ten-sample average.

A separate calibration helper at `0x0802D790` performs the same analog-mode selection but averages 20 samples. The runtime calibration handler uses that 20-sample helper when capturing calibration points.

## 4. Four-anchor ADC -> Bv linearization

`0x0802D320` receives the averaged ADC value and a calibration pointer. The first four halfwords of that record are four ADC anchors:

```text
c0 = cal[+0x00]
c1 = cal[+0x02]
c2 = cal[+0x04]
c3 = cal[+0x06]
```

For non-degenerate anchors, the mapping is:

```text
if adc < c1:
    mapped = (adc - c1) * 0x0200 / (c1 - c0)
elif adc < c2:
    mapped = (adc - c1) * 0x0300 / (c2 - c1)
else:
    mapped = (adc - c2) * 0x0700 / (c3 - c2) + 0x0300
```

The result is sign-extended to 16 bits.

The existing exposure research established that these coordinates are Q8.8 EV. Therefore the calibration anchors have exact semantic target coordinates:

| ADC anchor | Q8.8 result | EV |
|---|---:|---:|
| `c0` | `-0x0200` | `-2 EV` |
| `c1` | `0x0000` | `0 EV` |
| `c2` | `0x0300` | `+3 EV` |
| `c3` | `0x0A00` | `+10 EV` |

The third segment adds `0x0300` after scaling by `0x0700`, so `c3` lands at `0x0A00` exactly.

The routine extrapolates outside the outer anchors rather than applying a hard clamp. It also contains denominator-zero fallbacks; production calibration should normally make the anchors distinct.

This is a significant Leica metering result: the raw analog light sensor is not treated as a single global linear slope. It is linearized in three calibrated regions covering `-2 -> 0`, `0 -> +3`, and `+3 -> +10 EV`.

## 5. Normal-mode Bv offset

The selector-5 constructor calls:

```text
0x0802D6DC(
    mode = 0,
    calibration = 0x2001A9D8,
    normal_offset = signed cal[+0x14],
    alternate_offset = signed cal[+0x10],
    tlog_reference = unsigned cal[+0x18]
)
```

For mode `0`, after the piecewise ADC mapping:

```text
traditional_Bv = mapped_Bv + signed(cal[+0x14])
```

For the alternate mode, the same mapper is used but `cal[+0x10]` is subtracted instead. The production selector-5 constructor uses mode `0`.

Thus exact body parity depends on runtime calibration values as well as firmware policy.

## 6. Tlog arithmetic

`0x0802D678` receives the calibration halfword at `+0x18` and reads ADC selector `4`, which maps to ADC input 5.

The recovered floating-point helper sequence is equivalent to:

```text
delta = reference_adc - ADC5()
t = ((double(delta * 100) / 142.74) + 200.0)
Tlog = signed_integer_conversion(t)
Tlog = clamp(Tlog, -400, +800)
```

The constants are embedded as IEEE-754 doubles:

```text
0x4061D7AE147AE148 = 142.74
0x4069000000000000 = 200.0
```

`0x0801EF7C` is the signed-int to double conversion path, `0x0801EFAC` performs the double division, `0x0801F818` performs the double addition, and `0x0801F900` converts the double result back to signed integer.

### Physical interpretation

The firmware does not provide a nearby string explicitly expanding `Tlog`, so the following is labeled as a **strong static inference**, not a recovered symbol name:

- the `+200.0` reference point;
- the clamp `-400..+800`;
- and downstream thresholds `-80`, `+20`, `+280`, `+350`

are all naturally interpreted as temperature in tenths of a degree Celsius:

```text
+200 -> +20.0 C reference
-400 -> -40.0 C clamp
+800 -> +80.0 C clamp
-80  -> -8.0 C
+20  -> +2.0 C
+280 -> +28.0 C
+350 -> +35.0 C
```

This also fits the use of a dedicated analog ADC channel and a stored per-body reference ADC value.

Until a naming xref is found, the oracle should preserve the firmware name `Tlog` while documenting `temperature_x10_C` as the strongest interpretation.

## 7. Temperature-dependent low-light validity hysteresis

`0x0802D3D0` does not alter the numerical Bv returned by the normal path. It updates the global selector-5 status byte at `0x2001ADFA`.

It chooses a Bv lower threshold according to Tlog:

| Tlog range | Threshold Q8.8 | EV |
|---|---:|---:|
| `< -80` | `-128` | `-0.5 EV` |
| `-80 .. 19` | `-256` | `-1.0 EV` |
| `20 .. 279` | `-512` | `-2.0 EV` |
| `280 .. 349` | `-128` | `-0.5 EV` |
| `>= 350` | `0` | `0 EV` |

State update:

```text
if traditional_Bv < threshold:
    status = 1
elif traditional_Bv > threshold + 128:
    status = 0
else:
    status is retained
```

`128` Q8.8 counts is `0.5 EV`, so the validity transition has a 0.5-EV hysteresis band.

If the Tlog-as-temperature interpretation is correct, the camera permits the traditional meter to operate down to roughly `-2 EV` through its normal temperature band, but raises the low-light cutoff in colder and hotter ranges.

## 8. Runtime calibration block and service capture

Runtime meter calibration lives at `0x2001A9D8` and is 0x1C bytes long.

The handler at `0x0801838C` has these recovered operations:

```text
subcommand 0:
    memcpy(0x2001A9D8, supplied_pointer, 0x1C)

subcommand 1:
    supplied[0] = 20-sample average in analog mode 0
    supplied[2] = 20-sample average in analog mode 1

subcommand 2:
    supplied[0] = ADC selector 4 sample

subcommand 3:
    additional service/calibration action not yet semantically frozen
```

The handler has one direct caller at `0x080186C0`. That caller belongs to a routed command function beginning at `0x0801865C`; outer command case `5` invokes the calibration handler only when its sub-selector is also `5`.

This establishes the block as explicitly provisioned calibration/service data rather than compile-time constants.

Known fields are therefore:

| Offset | Current identity |
|---:|---|
| `+0x00` | ADC anchor for `-2 EV` |
| `+0x02` | ADC anchor for `0 EV` |
| `+0x04` | ADC anchor for `+3 EV` |
| `+0x06` | ADC anchor for `+10 EV` |
| `+0x10` | signed alternate-mode Bv offset |
| `+0x14` | signed normal-mode Bv offset |
| `+0x18` | ADC selector-4 / Tlog reference |
| other bytes | not yet frozen |

## 9. Corrected traditional-meter model

For the production mode used by selector 5:

```text
Tlog = clamp(
    int(((cal.tlog_ref - ADC5) * 100 / 142.74) + 200.0),
    -400,
    +800
)

ADC6_avg = floor(sum(10 ADC6 readings) / 10)

raw_Bv = piecewise_map(
    ADC6_avg,
    anchors=[c0,c1,c2,c3],
    targets_Q8_8=[-512,0,768,2560]
)

traditional_Bv = int16(raw_Bv + cal.normal_offset)
status = temperature_dependent_hysteresis(Tlog, traditional_Bv, prior_status)
```

This value becomes packet `+0x02`, is accepted into traditional Bv state `+0x14` when the ambient-light calibration-valid gate permits it, and then participates in the already-recovered final-Bv selector, AE-lock cache, and Tv/ISO allocator.

## 10. Implication for the M10-R app

The Leica behavior separates naturally into two layers:

### Firmware-defined and portable

- 10-sample temporal averaging;
- three-segment meter linearization shape;
- target Bv anchors `-2/0/+3/+10 EV`;
- normal-mode signed calibration offset;
- temperature-dependent low-light validity thresholds;
- 0.5-EV validity hysteresis;
- downstream final-Bv selection, AE-lock caching, and Tv/ISO allocation already recovered.

### Body/sensor-specific

- the four raw ADC calibration anchors;
- normal/alternate offsets;
- the Tlog reference ADC;
- analog front-end/gain behavior behind the `0x40021000` mode bit.

A phone implementation should therefore reproduce the firmware-defined coordinate behavior while fitting equivalent input anchors to the phone's scene/meter signal. Copying literal M10-R ADC counts would not be meaningful on a different sensor.

## 11. Next investigation targets

Highest value next steps:

1. trace the provenance/persistence source of the 28-byte calibration record supplied to subcommand 0;
2. resolve the `0x40021000` bit-`0x8000` analog mode switch and determine what changes between normal and alternate meter mode;
3. trace `BvExt` and `BV_IR` production at `0x2001AC74` to understand whether they are secondary photodiode/IR compensation coordinates feeding meter validity or scene adaptation;
4. add an executable traditional-meter oracle with parameterized calibration anchors once the remaining signed/rounding edge cases are machine-checked.

## Research provenance

All addresses and constants in this note come from checksum-verified static analysis of `M10-R-30.22.23.34-Customer.FW` on the temporary `m10r-metering-latch-trace` branch. Firmware binaries are not committed to the repository.
