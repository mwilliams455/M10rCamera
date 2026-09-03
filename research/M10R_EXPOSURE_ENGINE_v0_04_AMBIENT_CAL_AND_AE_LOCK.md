# M10-R Exposure Engine v0.04: Ambient-Light Calibration and AE Lock

## Outcome

This pass closes two previously separate unknowns:

1. The persisted structure at `0x2001A77C`, byte `+0x79`, is a calibration-validity bitfield. Bit 0 means **ambient-light calibration valid**. It is not AE lock.
2. Real AE lock is a cross-CPU state transition. `IMG-System` sends CTRL command `0x12` with payload `1` or `0`; CTRL copies that state into exposure-input byte `+0x25`, bit 1. In the exposure calculator, a set lock bit prevents refresh of the cached **BV value for calculation** at `0x2000012A`.

The important modeling consequence is that AE lock does not need to stop metering or the upstream final-Bv selector. It holds the Bv consumed by the exposure allocator.

## Corrected image mappings

Both relevant section files have a four-byte prefix:

| Image | Mapping | Prefix evidence |
|---|---|---|
| `090_CTRL-System.bin` | `VA = 0x08000000 + file_offset - 4` | vector table begins at file `+4` |
| `092_IMG-System.bin` code/strings | `VA = 0x42000000 + file_offset - 4` | file word 0 is `0x12345678`; callable Thumb pointers align only after subtracting the prefix |

The IMG image also contains initialized data addressed in the `0x40xxxxxx` region. The `0x42xxxxxx` mapping above is the code/string alias used in this trace.

## `+0x79` bit 0 is ambient-light calibration validity

The structure getter at `0x0801124C` returns `0x2001A77C`. Service/calibration commands modify its fields and set or clear bits in byte `+0x79`:

| Evidence | Meaning |
|---|---|
| `Adjust AV0 done.` and the BV anchor adjustments set bit 0 | ambient-light/BV calibration group becomes valid |
| `Clear BV adjust done.` clears bit 0 | calibration group becomes invalid |
| diagnostic at `0x08046AF0` says `Ambient light not calibrated` when bit 0 is clear | direct user-facing identity |
| other bits produce separate diagnostics for temperature, shutter, focus position, lens detection, accelerometer, and rotation wheel | confirms that `+0x79` is a validity bitmap rather than live camera state |

The final-Bv selector at `0x0800D6A8` therefore reads this bit as permission to use calibrated traditional/rangefinder Bv. The previous v0.03 label “camera state `+0x79` bit 0” is superseded by:

```text
calibration_record + 0x79 bit 0 = ambient-light calibration valid
```

## AE-lock chain

| Stage | Address/value | Evidence |
|---|---|---|
| IMG external event | `0xAE` | string `EXT_AE_LOCK` |
| IMG external event | `0xAF` | string `EXT_AE_UNLOCK` |
| IMG control machine | — | string `AE_LOCK_CONTROL` |
| IMG states | — | strings `ae_lock_enabled`, `ae_lock_disabled` |
| IMG enabled callback | Thumb pointer `0x421BD5D5` | calls `0x420AB2F8` |
| IMG disabled callback | Thumb pointer `0x421BD5E5` | calls `0x420AB326` |
| IMG lock sender | `0x420AB2F8` | builds command `0x12`, three-byte packet, payload `1` |
| IMG unlock sender | `0x420AB326` | builds command `0x12`, three-byte packet, payload `0` |
| CTRL receiver | `0x0800248E` | logs `AE lock %i received`, stores byte, posts an update event |
| CTRL lock byte | `0x2001AD6E` | set by `0x0800DE18`, read by message builder |
| Exposure input | `+0x25 bit 1` | populated at `0x0800DA62..0x0800DA70` |
| Exposure calculator | `0x080203B4` | reads the lock bit at `0x0802049C` |
| Latched calculation Bv | `0x2000012A` | diagnostic string names it `BV value for calculation` |

The CTRL hidden command `<AELock X>` invokes the same receiver at `0x0800248E`; it is a simulator entry into the production lock path, not a second lock implementation.

## Exact hold behavior

In the normal calculator path, the relevant block at `0x0802049C..0x080204DC` is equivalent to:

```text
if AE_lock == 0:
    if bracketing == 0 or bracket_phase == 1:
        cached_Bv_for_calculation = input_Bv_at_plus_0x06

Bv_for_this_calculation = cached_Bv_for_calculation
```

There is also a diagnostic/override path that can force the cache write. It should not be included in the production oracle without evidence that it is active in normal camera operation.

Consequences:

- Lock freezes the allocator's Bv coordinate, not necessarily the live meter readings.
- The upstream traditional/CMOS selection and ±25-count deadband can continue to update internal final Bv while locked.
- Unlock does not require a separate restore value. The next eligible calculator pass overwrites the cache with the current input Bv.
- Bracketing already has a separate cache-refresh rule; AE lock is an additional gate on that write.
- In A mode, the held Bv freezes the exposure target presented to Tv/ISO allocation. Whether Tv, ISO, or both remain unchanged depends on the active ISO policy and limits.

## Oracle delta

The offline oracle needs one persistent state value and one input bit:

```text
state.cached_calculation_Bv
input.AE_lock
```

Production update rule:

```text
if not input.AE_lock and bracket_refresh_is_allowed:
    state.cached_calculation_Bv = input.final_Bv

allocator_Bv = state.cached_calculation_Bv
```

This state must sit between the v0.03 final-Bv selector and the A-mode allocator. Treating lock as a switch inside the final-Bv selector would place it at the wrong layer.

## Reproducibility

Run:

```bash
python tools/m10r_ae_lock_inspect.py \
  firmware/sections/090_CTRL-System.bin \
  firmware/sections/092_IMG-System.bin

python -m unittest discover -s tests -v
```

The inspector validates the image prefixes, evidence strings, callback pointers, IPC payload signatures, CTRL lock-byte address, and cached-Bv address. The full suite currently contains 11 passing tests.

## Still open

The firmware names and cross-CPU behavior are closed, but the physical producer of `EXT_AE_LOCK`/`EXT_AE_UNLOCK` is not yet frozen. Do not yet state that a particular shutter-button detent is the sole source. The next trace should connect the release-button state machine and any remote-control path to event IDs `0xAE` and `0xAF`, then validate the timing on hardware.
