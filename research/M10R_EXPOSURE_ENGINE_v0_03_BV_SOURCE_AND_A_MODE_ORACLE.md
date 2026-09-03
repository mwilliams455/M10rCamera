# M10-R EXPOSURE ENGINE v0.03
## TRADITIONAL BV SOURCE, FINAL-BV SELECTOR, PRODUCTION SV CONTROL, AND A-MODE ORACLE

**Date:** 2026-09-03  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Original FW SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`  
**Decoded SHA-256:** `859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0`  
**CTRL-System SHA-256:** `487482096f748d742c082469d5606bf40da3a430bb276f4fdf18c03485e1e77c`

## 1. Milestone

This pass closes three handoff targets:

1. `state +0x14` is the traditional/rangefinder `Bv` delivered in the nine-byte **AE measure result** message.
2. The final-BV selector is frozen at instruction level, including the CMOS/traditional/hold branches and both ±25-count update tests.
3. The production aperture-priority Auto-ISO path is implemented as an executable offline oracle in `tools/m10r_ae_oracle.py`.

It also corrects the load-address convention used in earlier exploratory work and realigns the ISO, SV, and correction tables.

## 2. CTRL-System address correction

`090_CTRL-System.bin` includes a four-byte section prefix before its load image:

```text
file +0x0000  section prefix = 0x00011498
file +0x0004  initial SP     = 0x20002208
file +0x0008  reset vector   = 0x0804B03D
```

The mapping is therefore:

```text
VA = 0x08000000 + file_offset - 4
file_offset = 4 + VA - 0x08000000
```

Any earlier instruction label obtained by treating file offset zero as VA `0x08000000` is four bytes too high. Absolute pointers embedded in the code were already meaningful; applying the correct mapping makes them land on the first real table element instead of on four bytes of preceding data.

The guard/tool for this convention is `tools/m10r_ctrl_inspect.py`.

## 3. AE state map

The relevant state base remains `0x2001A918`.

| Offset | Identity | Corrected accessor addresses |
|---:|---|---|
| `+0x0E` | stored final Bv coordinate | setter `0x08011CF0`, getter `0x08011D08` |
| `+0x10` | BvExt | setter `0x08011D18`, getter `0x08011D2E` |
| `+0x12` | BV_IR | setter `0x08011D36`, getter `0x08011D4C` |
| `+0x14` | traditional/rangefinder Bv | setter `0x08011D54`, getter `0x08011D7A` |
| `+0x16` | BvCMOS | setter `0x08011D82`, getter `0x08011DA8` |
| `+0x30` | Tlog | setter `0x08011DB0`, getter `0x08011DB6` |

The final-BV setter still performs:

```text
stored = incoming - 59
```

and the public getter performs:

```text
returned = stored + 59
```

This remains a coordinate/storage seam, not user exposure compensation.

## 4. `state +0x14` producer closed

The handler at `0x0800E1EC` accepts exactly nine bytes. Its failure diagnostic is:

```text
Wrong size of AE measure result (%i != %i)
```

The message is decoded as:

| Message offset | Destination |
|---:|---|
| `+0x00` | Tlog (`state +0x30`) |
| `+0x02` | traditional/rangefinder Bv (`state +0x14`) |
| `+0x04` | BvExt (`state +0x10`) |
| `+0x06` | BV_IR (`state +0x12`) |
| `+0x08` | status bit copied to controller state |

The `+0x02` field is accepted only while `0x2001AD72` is nonzero. The final-BV selector sets that flag immediately before choosing the traditional path. This closes the state identity:

```text
state +0x14 = Bv from the traditional/rangefinder AE measure-result path
```

The controller-side identity is now firm. The upstream optical/electrical conversion from raw TTL channels into this message field is still outside this section and remains a separate target.

## 5. Exact final-BV source selector

The selector starts at `0x0800D6A8`.

Inputs/predicates:

```text
camera state +0x79 bit 0
0x2001ADAE  live-view/video preparation state
0x2001ADBB  sensor/exposure-process response state
0x2001AD76  negative-traditional-Bv delay latch
```

Selection behavior:

```text
if sensor/exposure-process state OR live-view/video state:
    selected = BvCMOS
    traditional-result acceptance = off

else if camera-state bit is set AND negative-Bv delay latch is clear:
    traditional-result acceptance = on
    selected = traditional/rangefinder Bv

else:
    traditional-result acceptance = off when the state bit is clear
    selected = previous final Bv
```

`0x2001AD76` should not be named AE lock. Its observed producer checks whether traditional Bv is negative, sets the latch, and starts a 300 ms timer. The conservative identity is a negative-Bv acquisition/delay latch.

The exact user-facing meaning of `camera state +0x79 bit 0` is not frozen. It gates eligibility for the traditional path, but calling it “AE lock” would overstate the current evidence.

### Update hysteresis

The selected value is committed if any of these conditions is true:

```text
selected_Bv >= previous_final_Bv + 25
selected_Bv <= previous_final_Bv - 25
current_BvExt >= previous_BvExt + 25
current_BvExt <= previous_BvExt - 25
```

Otherwise the previous final Bv is retained, except for a separate one-shot recalculation latch at `0x2001AD79` that can refresh downstream state without overwriting final Bv.

Thus both selected Bv and BvExt can independently force a recomputation outside the ±25-count (`±0.09765625 EV`) band.

## 6. Production configuration recovered

The initializer at `0x0800D91C` builds the 0x84-byte AE configuration copied to `0x2001A6F8`.

| Config offset | Production value |
|---:|---|
| `+0x00..+0x67` | 52 signed per-SV corrections from `0x0803B65C` |
| `+0x68` | SV step `0x0055` = `0.33203125 EV` |
| `+0x6A` | dynamic SV maximum |
| `+0x6C` | dynamic SV minimum |
| `+0x6E` | TV maximum `0x0C00` |
| `+0x70` | dynamic TV minimum |
| `+0x72` | AV step `0x0080` = `0.5 EV` |
| `+0x74` | AV maximum `0x0C00` |
| `+0x76` | AV minimum `0x0000` |
| `+0x78` | SV table pointer `0x20000000` |
| `+0x7C` | AV table pointer `0` |
| `+0x80` | SV table size `29` |
| `+0x81` | AV table size `0` |
| `+0x82` | AE control type `0` |
| `+0x83` | debug `0` |

The dynamic SV minimum and maximum originate in camera settings as ISO values, then pass through the firmware ISO-to-SV ceiling lookup.

## 7. Production SV subset and the important branch distinction

The corrected table pointers are:

```text
ISO labels       0x0803A3B8, 52 x uint32
SV states        0x0803B8CC, 52 x int16 Q8.8
SV corrections   0x0803B65C, 52 x int16 Q8.8
```

The 29-state table slice is engineering indexes 15 through 43 inclusive:

```text
ISO 100 / SV 5.000
through
ISO 64000 / SV 14.332
```

The normal M10-R maximum is still imposed dynamically; the presence of ISO 64,000 as the 29th table state is headroom and does not prove that it is a user-selectable still-photo setting.

Most importantly, the production configuration sets **AE control type 0**. The Auto-ISO dispatcher at `0x080217F6` uses:

```text
control type 1 or 3 -> table-walk helper at 0x080218A8
all other types     -> fixed-step helper at 0x0802182C
```

Therefore the normal production path uses the `0x55` SV step helper. The 29-entry table exists and is usable by alternate control types, but it is not the active allocator for control type 0.

The fixed-step helper creates the cycle:

```text
... 0x0500, 0x0555, 0x05AA, 0x0600, ...
```

Its third move is rounded across `0x05FF` to `0x0600`. This differs slightly from the exact label table's `0x05AE` state, although the later SV-to-ISO conversion still maps the nearby fixed-step value to the expected standard ISO label.

## 8. Exact A-mode Auto-ISO path

The central AE routine starts at `0x080203B4`; A mode enters at `0x08020AD4`.

For production control type 0:

```text
initial_SV = AutoISO ? configured_SV_min : selected_SV
initial_correction = correction[index(initial_SV)]

EV_target =
      Bv
    + initial_SV
    - Override
    - ExposureCorrection
    - initial_correction

requested_TV = EV_target - AV
```

When Auto ISO is enabled, the helper receives:

```text
+0x00 requested TV
+0x02 resolved TV ISO boundary
+0x04 TV seed
+0x06 AV seed
+0x08 SV seed
+0x0A SV step
+0x0C SV maximum
+0x0E move residual into TV flag (0 in A mode)
+0x0F move residual into AV flag (1 in A mode)
```

The production loop is:

```text
SV = round_to_step(SV_seed, 0x55)

while requested_TV < TV_ISO and SV <= SV_max - 0x55:
    SV += 0x55
    TV += 0x55
    requested_TV += 0x55
    SV = round_to_step(SV, 0x55)
```

Consequences:

- Auto ISO advances only in full configured steps.
- It can overshoot the TV ISO boundary by less than one step.
- It never takes a partial final SV step merely to land exactly on TV ISO.
- It stops before a full step would exceed the configured SV maximum.
- A-mode AV remains fixed.
- Bracketing adjustment is subtracted from the solved TV after the Auto-ISO allocation and before TV clamping.

Final residual is recalculated using the correction indexed by final SV:

```text
dEV =
      Bv
    + final_SV
    - final_TV
    - AV
    - Override
    - ExposureCorrection
    - correction[index(final_SV)]
```

Because the target used the initial-SV correction while `dEV` uses the final-SV correction, a nonzero small residual can remain after Auto ISO changes sensitivity. This is observed in the oracle vectors and should not be normalized away.

## 9. Per-SV correction curve

The four-byte address correction removes the previous bogus leading value. All 52 entries now align with the ordered ISO/SV engineering tables.

In the production ISO 100–64,000 slice, corrections in Q8.8 counts are:

```text
100:27   125:37   160:39   200:29   250:31   320:39
400:47   500:28   640:40   800:42  1000:29  1250:32
1600:37 2000:36  2500:31  3200:44  4000:39  5000:33
6400:31 8000:24 10000:15 12500:6  16000:0  20000:6
25000:39 32000:48 40000:39 50000:39 64000:48
```

The curve is definitely an SV-indexed AE calibration/linearization term: it is subtracted in both target construction and final residual calculation. The binary does not yet establish whether its physical origin is meter calibration, sensitivity calibration, sensor-gain correction, or a mixture, so no narrower name is justified.

## 10. Offline oracle

`tools/m10r_ae_oracle.py` provides:

- exact ISO/SV/correction constants;
- ISO-to-SV ceiling lookup;
- SV-to-ISO index conversion using the firmware's `0.333` divisor;
- the instruction-faithful Q8.8 step-rounding helper;
- production A-mode target construction;
- fixed-step Auto-ISO allocation;
- TV limit handling;
- final `dEV`, ISO, shutter time, and constraint diagnostics;
- a JSON command-line interface.

Example:

```bash
python3 tools/m10r_ae_oracle.py \
  --bv 0 --av 4 --tv-iso 6 \
  --sv-min-iso 100 --sv-max-iso 50000
```

This vector returns 16 Auto-ISO moves, final SV `0x0A55` (ISO 4000), TV `0x0635` (6.207 EV), and `dEV = -7/256 EV`.

Nine unit tests cover table alignment, the four-byte VA mapping, step rounding, no-activation, active Auto ISO, and SV-max exhaustion.

## 11. Current boundary

The oracle is an instruction-derived offline reference for the normal control-type-0 A-mode branch. It is not yet hardware-parity certified.

Still open:

1. Capture diagnostic vectors from a real body or emulator and compare them against the oracle.
2. Freeze the user-facing identity of `camera state +0x79 bit 0` and any AE-lock transition semantics.
3. Trace the upstream traditional meter subsystem that produces the AE message's `+0x02` Bv field.
4. Port T, P, M, and Bulb branches only after A-mode vectors are stable.
5. Confirm the exact dynamic SV min/max choices exposed by the M10-R UI and whether the 64,000 table endpoint is ever reachable on this body.
6. Keep Photon integration diagnostic-only until independent A-mode parity exists.

## 12. Conclusion

The handoff's first implementation gate is now met in a narrow, testable form:

```text
traditional Bv state closed
final-Bv selector frozen
production step-vs-table branch corrected
per-SV table realigned
A-mode Auto-ISO oracle executable
```

The next best experiment is not more speculative decompilation. It is a small parity matrix spanning bright/no-Auto-ISO, boundary crossing, high-ISO correction changes, SV-max exhaustion, and TV clamp cases.
