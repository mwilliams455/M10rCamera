# M10-R PROJECT HANDOFF v0.03
## A-MODE ORACLE COMPLETE; PARITY VECTORS NEXT

**Date:** 2026-09-03  
**Repository:** `mwilliams455/M10rCamera`  
**Predecessor:** `research/M10R_PROJECT_HANDOFF_v0_02_EXPOSURE_TVISO_SV_BV_AE_ORACLE_NEXT.md`

## Completed in this pass

- Corrected CTRL-System load mapping: the extracted section has a four-byte prefix before VA `0x08000000`.
- Closed `state +0x14` as the traditional/rangefinder Bv field from the nine-byte AE measure-result message.
- Froze the final-BV selector between previous final Bv, traditional Bv, and BvCMOS.
- Confirmed both selected Bv and BvExt use ±25-count update thresholds.
- Identified `0x2001AD76` as a negative-Bv delay latch, not an established AE-lock flag.
- Realigned the 52 ISO, SV, and per-SV correction entries.
- Identified the 29-state production table slice as ISO 100 through 64,000.
- Corrected a key architectural assumption: production control type 0 uses the `0x55` fixed-step Auto-ISO helper; table walking is reserved for control types 1 and 3.
- Recovered the exact A-mode Auto-ISO loop and final `dEV` formula.
- Added executable oracle and tests:

```text
tools/m10r_ae_oracle.py
tools/m10r_ctrl_inspect.py
tests/test_m10r_ae_oracle.py
tests/test_m10r_ctrl_inspect.py
```

Validation status:

```text
9 unit tests passing
CTRL-System prefix/vector validation passing
offline A-mode example vector passing
```

## Frozen production A-mode behavior

```text
target = Bv + SV_min - Override - ExposureCorrection - correction(SV_min)
requested_TV = target - fixed_AV

while requested_TV < TV_ISO and another full SV step fits:
    SV += 0x55
    TV += 0x55
    requested_TV += 0x55
    round SV on the production Q8.8 step lattice
```

The helper does not take a partial last step. Final `dEV` is recomputed using the correction at final SV, so small nonzero residuals are valid.

## Important address convention

For `090_CTRL-System.bin`:

```text
VA = 0x08000000 + file_offset - 4
```

Historical instruction labels derived directly from file offsets are four bytes high. Use `tools/m10r_ctrl_inspect.py` before relying on any CTRL-System absolute address.

## Next investigation

1. Build an independent A-mode parity matrix from camera/emulator diagnostics:
   - bright scene, no Auto ISO movement;
   - one-step boundary crossing;
   - several-step allocation;
   - ISO 160-style exact-table versus fixed-step rounding;
   - SV maximum before TV ISO;
   - TV minimum and maximum clamps;
   - nonzero Override and exposure correction.
2. Freeze `camera state +0x79 bit 0` and real AE-lock transition behavior without guessing from eligibility alone.
3. Trace the subsystem upstream of the AE measure-result message's traditional Bv field.
4. Expand the oracle to T/P/M only after A-mode parity is independently confirmed.
5. Keep Photon integration diagnostic-only after parity; do not yet mutate real exposure.

## Photon gate

The offline executable gate is met for A mode, but hardware parity is not. `M10R-PHOTON0A` can be planned now; `M10R-AE1A` should remain a diagnostic comparison until parity vectors are available.

**HANDOFF STATUS:** READY  
**IMPLEMENTATION STATUS:** A-mode oracle v0.1, 9 tests passing  
**NEXT:** independent A-mode parity matrix  
**DO NOT ASSUME:** table-walk allocation in production control type 0, ISO 64,000 UI reachability, or AE-lock identity for `state +0x79 bit 0`
