# M10-R Project Handoff v0.07: CTRL Event Latch / Overlap Next

## Closed in this pass

- The CTRL AE-lock receiver at `0x0800248E` commits the received lock value first by calling `0x0800DE18` from `0x080024A0`.
- Only after that store does the receiver call `0x0800DC4A` from `0x080024A6` with update mask `2`.
- `0x0800DC4A` checks the exposure event facility at `0x08011238` and posts the supplied mask through per-task event sender `0x0801CF26`.
- The exposure-control event loop extracts event-word bit 1 at `0x0800DD42..0x0800DD4E`.
- The event-2 branch performs eligibility check `0x08001A38` and then calls exposure-input builder `0x0800D91C` from `0x0800DD58`.
- Builder `0x0800D91C` snapshots CTRL AE-lock byte `0x2001AD6E` into exposure-input `+0x25 bit 1` at `0x0800DA62`.
- The builder directly calls exposure calculator `0x080203B4` from `0x0800DB78`.
- The previously recovered calculator rule therefore means the calculation scheduled by the lock update sees lock `1` and cannot refresh cached calculation Bv `0x2000012A`.
- No synchronous “one final unlocked meter calculation” exists between the receiver's lock store and the update event post.
- The BSTM dispatcher is child-first: `0x420A274C` calls child wrapper `0x420A2840`, which recursively re-enters the dispatcher.
- Independent IMG evidence: external exposure-start action `0x421BE6EC` emits `K_Release_1 (0xD6)` through `0x421BC9E8` before calling later exposure preparation `0x421BF23C`.

## Refined latch model

The first-detent lock is a cache freeze, not an explicit lock-time meter sample.

Confirmed sequence:

```text
K_Release_1
  -> AE_LOCK_CONTROL enters enabled
  -> IMG sends CTRL 0x12 payload 1
  -> CTRL stores AE_lock = 1
  -> CTRL posts exposure event mask 2
  -> event bit 1 is consumed
  -> exposure input is built with lock bit 1
  -> calculator runs with lock bit 1
  -> cached Bv refresh is suppressed
```

The lock-triggered calculation itself therefore cannot provide a new unlocked Bv sample.

## Remaining timing uncertainty

A previous unlocked builder/calculator pass may already be in flight when the receiver commits `AE_lock=1`.

If that earlier pass already snapshotted lock `0` at `0x0800DA62`, it can potentially complete the unlocked cached-Bv write even though the command receiver has since stored lock `1`. The following event-2 calculation will then freeze that result.

Static evidence has not yet shown whether the command receiver and exposure-control calculation are mutually exclusive or how scheduler priority/preemption resolves this overlap.

Therefore keep both exact-cycle models provisional:

1. freeze the most recently **completed** unlocked Bv calculation; or
2. allow an already **in-flight** unlocked calculation to finish and freeze its result.

## Next investigation target

Resolve the scheduling/serialization boundary between the command-receiver task and the exposure-control task.

Priorities:

1. identify the task descriptor used by `0x0800DC4A` / `0x0801CF26` and the task containing the event loop around `0x0800DCC6`;
2. identify the task/queue that invokes command receiver `0x0800248E` and recover its priority;
3. recover RTOS task priorities and preemption behavior for those two tasks;
4. inspect for mutex/critical-section/scheduler-lock coverage around `0x0800DA62` and the cached-Bv write in `0x080203B4`;
5. if static ordering cannot exclude overlap, design a timestamped hardware trace for first detent, Bv update, CTRL command `0x12`, and calculation entry/exit.

## Secondary IMG target

A broad scan finds multiple `0xD6` transition records in the BSTM transition load-image block. Map those records to their owner states and identify which are actually on the active state ancestry/child tree surrounding `AE_LOCK_CONTROL`. Do not treat the global records as a flat dispatch sequence.

## Oracle boundary

The oracle may now claim that the lock-triggered CTRL calculation is performed with lock already asserted and cannot refresh cached Bv.

It should still not claim which unlocked calculator cycle supplied the final frozen Bv until the cross-task overlap question is resolved.

## Reproducible files

- `tools/m10r_ae_lock_inspect.py`
- `tools/m10r_metering_latch_inspect.py`
- `tests/test_m10r_ae_lock_inspect.py`
- `tests/test_m10r_metering_latch_inspect.py`
- `research/M10R_EXPOSURE_ENGINE_v0_07_METERING_LATCH_ORDER.md`
- `research/M10R_PROJECT_HANDOFF_v0_07_CTRL_EVENT_LATCH_OVERLAP_NEXT.md`
