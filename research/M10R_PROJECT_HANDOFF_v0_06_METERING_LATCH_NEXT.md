# M10-R Project Handoff v0.06: Metering-to-Lock Timing Next

## Closed in this pass

- `AE_LOCK_CONTROL` uses `ae_lock_disabled` as its initial state.
- `K_Release_1` (`0xD6`, first detent) transitions disabled → enabled.
- The enabled-state entry callback sends CTRL command `0x12`, payload `1`.
- `K_Release_2` (`0xD7`, second detent) has no AE-local transition, so the
  lock remains active during exposure.
- `K_Release_0` (`0xD5`, release) transitions enabled → disabled.
- The disabled-state entry callback sends CTRL command `0x12`, payload `0`.
- The transition entries have neither guards nor intermediary action
  callbacks. The physical lock/unlock contract is no longer provisional.
- The BSTM transition initializers use a separate RAM-VMA/load-image mapping;
  the local inspector now handles it explicitly.

## Next investigation target

Resolve the temporal relationship between first-detent metering and the Bv
value frozen by the lock command. The state edge proves *which* event enables
lock, but not whether the metering pipeline refreshes `0x2000012A` immediately
before command `0x12` becomes visible to the CTRL calculator.

The desired evidence is one of:

1. an IMG event/action chain showing metering-start or metering-ready ordering
   relative to the `K_Release_1` state-entry callback;
2. a CTRL task/message ordering proof showing a final unlocked Bv refresh
   before the lock byte is consumed;
3. a timestamped hardware trace correlating first detent, Bv update, command
   `0x12`, and subsequent exposure calculations.

## Static targets

- Trace all BSTM handling of event `0xD6` above and below `AE_LOCK_CONTROL`,
  because the dispatcher walks the nested state tree before evaluating the
  current state's transition.
- Inspect the event producer/consumer ordering around `0x42186734`,
  `0x421BE2C0`, and BSTM dispatcher `0x420A274C`.
- On CTRL, identify the task/queue boundary between command receiver
  `0x0800248E` and exposure calculator `0x080203B4`.
- Determine whether a Bv refresh and lock write can race within one metering
  cycle; retain the stateful rule but keep exact cycle timing provisional
  until this is resolved.

## Oracle boundary

The oracle may now implement first-detent lock, second-detent hold, and
release unlock as confirmed behavior. It should not yet claim whether the
latched Bv is sampled in the same calculator cycle as the first-detent event
or one cycle earlier/later.

## Reproducible files

- `tools/m10r_ae_lock_inspect.py`
- `tests/test_m10r_ae_lock_inspect.py`
- `research/M10R_EXPOSURE_ENGINE_v0_06_PHYSICAL_AE_LOCK_EDGE.md`
- `research/M10R_PROJECT_HANDOFF_v0_06_METERING_LATCH_NEXT.md`
