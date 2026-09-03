# M10-R Project Handoff v0.04: AE-Lock Trigger Next

## New closed findings

- `0x2001A77C + 0x79 bit 0` is **ambient-light calibration valid**, proven by the diagnostic `Ambient light not calibrated` and the BV/AV0 service-adjustment writers.
- The final-Bv selector uses that bit to decide whether calibrated traditional/rangefinder Bv is eligible. It is not an AE-lock test.
- IMG events `0xAE` and `0xAF` are named `EXT_AE_LOCK` and `EXT_AE_UNLOCK`.
- IMG contains an `AE_LOCK_CONTROL` machine with `ae_lock_enabled` and `ae_lock_disabled` states.
- State-entry callbacks send CTRL command `0x12`, packet size 3, with payload `1` for lock and `0` for unlock.
- CTRL stores the state at `0x2001AD6E` and publishes it as exposure-input `+0x25 bit 1`.
- The calculator at `0x080203B4` implements lock by suppressing refresh of `0x2000012A`, explicitly logged as `BV value for calculation`.
- AE lock is downstream of live Bv acquisition and final-Bv selection, immediately upstream of allocation.

## Stateful oracle insertion

Insert this stage between the existing final-Bv selector and A-mode oracle:

```text
if !AE_lock && bracket_refresh_allowed:
    cached_calculation_Bv = current_final_Bv

allocator_Bv = cached_calculation_Bv
```

On unlock, the next eligible pass naturally relatches the current Bv.

## Reproducible files

- `tools/m10r_ae_lock_inspect.py`
- `tests/test_m10r_ae_lock_inspect.py`
- `research/M10R_EXPOSURE_ENGINE_v0_04_AMBIENT_CAL_AND_AE_LOCK.md`

Verification:

```bash
python tools/m10r_ae_lock_inspect.py \
  firmware/sections/090_CTRL-System.bin \
  firmware/sections/092_IMG-System.bin
python -m unittest discover -s tests -v
```

Expected result: 11 tests pass.

## Next trace

1. Find the non-diagnostic producers that dispatch event IDs `0xAE` and `0xAF`.
2. Connect those producers to the IMG release-button states and remote-control states.
3. Freeze whether lock begins on entry to the first detent, after a metering-ready acknowledgement, or on another transition.
4. Freeze unlock timing relative to button release, exposure start, exposure stop, and continuous drive.
5. Add a stateful lock/unlock sequence test to the A-mode oracle once the event timing is known.

## Hardware parity matrix

Capture at least these sequences in A mode:

| ISO policy | Sequence | Expected discriminator |
|---|---|---|
| fixed ISO | meter scene A → lock → point at scene B | Tv remains based on scene A while locked |
| Auto ISO | meter scene A → lock → point at scene B | allocator target remains scene A; Tv/ISO split follows existing limits |
| fixed ISO | lock on A → move to B → unlock | next eligible cycle adopts scene B |
| Auto ISO | lock during bracket sequence | distinguishes AE-lock gate from bracket refresh phase |
| fixed ISO | remote lock/unlock | tests whether remote and physical paths converge before events `0xAE/0xAF` |

Record timestamps and raw Q8.8 values when available; display-only shutter values are insufficient near step boundaries.

## Research boundary

Continue to keep M9 photographic constants separate from M10-R constants. Photon remains diagnostic-only until capture parity. Do not infer the physical lock trigger from the event names alone.
