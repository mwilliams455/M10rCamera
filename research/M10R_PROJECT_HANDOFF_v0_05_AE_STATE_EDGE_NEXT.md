# M10-R Project Handoff v0.05: Recover the AE State Edge

## Closed in this pass

- The physical `K_Release` descriptor is record 13 of the 28-byte table at
  `0x427F8EC4`.
- Physical raw state `1` emits `K_Release_1` (`0xD6`), raw state `3` emits
  `K_Release_2` (`0xD7`), and raw state `2` emits `K_Release_0` (`0xD5`).
- `K_Release_3` (`0xD8`) is present in metadata but is not a fourth physical
  detent in the production type-1 translator branch.
- External exposure commands synthesize `K_Release_1/2/0`; external AE lock
  and unlock instead invoke dedicated command-`0x12` actions.
- The switch at `0x42134D50` is an enum/string-option mapper, not an event
  producer. Its apparent `0xAE/0xAF` cases are a false lead.

## Still open

Recover the generated state-machine edges that enter the two AE states whose
entry callbacks are `0x421BD5D4` (lock) and `0x421BD5E4` (unlock). The desired
evidence is one of:

1. a metadata record explicitly connecting `K_Release_1`/`K_Release_0` to
   `ae_lock_enabled`/`ae_lock_disabled`;
2. an indirect state-transition caller resolved through the BSTM runtime;
3. a timestamped hardware trace showing release events and CTRL command
   `0x12` in order.

## Next static targets

- Reverse the BSTM constructor around `0x421C73A4`, where `AE_LOCK_CONTROL` is
  created with two states and its runtime state array.
- Decode the metadata records adjacent to strings `ae_lock_enabled` and
  `ae_lock_disabled` rather than treating adjacent pointers as a flat table.
- Trace indirect invocations of the two state-entry callbacks through the BSTM
  engine; direct-call scanning is already exhausted.
- Keep the external `EXT_AE_*` path separate from physical-key transitions.

## Oracle boundary

The v0.04 cached-Bv hold rule is closed and unchanged. Only the timing/source
of the `AE_lock` input remains provisional. Until the state edge is recovered,
tests may inject lock/unlock explicitly but must not infer them from shutter
detents.

## Reproducible files

- `tools/m10r_ae_lock_inspect.py`
- `tests/test_m10r_ae_lock_inspect.py`
- `research/M10R_EXPOSURE_ENGINE_v0_04_AMBIENT_CAL_AND_AE_LOCK.md`
- `research/M10R_EXPOSURE_ENGINE_v0_05_RELEASE_TRIGGER_BOUNDARY.md`

Run the inspector and the complete unit-test discovery command shown in the
v0.05 research note before continuing.
