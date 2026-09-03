# M10-R Exposure Engine v0.08: AE-Lock Scheduler Boundary

## Outcome

The remaining first-detent uncertainty is now reduced to a scheduler-priority question. The firmware does not implement a synchronous final meter sample at half press, and the lock-triggered exposure calculation cannot refresh the calculation-Bv cache. The only remaining candidate for a post-detent cache write is an exposure calculation that had already snapshotted `AE_lock=0` before the lock receiver stored `AE_lock=1`.

This pass additionally proves that the event-post critical section does not span the exposure builder/calculator and that the calculator does not re-read the global lock byte after the builder snapshot.

## Receiver -> event ordering

The CTRL AE-lock receiver at `0x0800248E` executes:

```text
0x0800249E  load payload byte
0x080024A0  BL 0x0800DE18   ; commit global AE-lock byte
0x080024A4  mov r0,#2
0x080024A6  BL 0x0800DC4A   ; post exposure update mask 0x02
```

The exposure-update helper at `0x0800DC4A` forwards the mask through `0x0801CF26`. That wrapper maps the exposure event index to a 0x30-byte RTOS event object and calls `0x08032DC0`.

## RTOS event critical section is local to event posting

`0x08032DC0` enters the RTOS scheduler/critical primitive at `0x080327E8`, ORs the requested event mask into the event object's pending word, conditionally wakes a waiter through `0x08032A7A`, and leaves through `0x080327DC`.

The critical section therefore protects event-object mutation/wakeup only. It is not held across the exposure event consumer, exposure-input builder, or exposure calculator.

No call to `0x080327E8`, `0x080327DC`, or `0x08032A7A` occurs in the recovered builder/calculator path `0x0800D91C -> 0x080203B4`.

## Event consumer -> calculator is synchronous within the exposure path

The exposure consumer at `0x0800DCC6` waits/reads the event object through `0x0801CF40`. For event bit 1 it reaches:

```text
0x0800DD42..0x0800DD4E  extract/test bit 1
0x0800DD50              eligibility check
0x0800DD58              BL 0x0800D91C
```

The builder then snapshots the already-committed global lock byte at `0x0800DA62..0x0800DA70` into exposure-input `+0x25 bit 1` and directly invokes the exposure calculator:

```text
0x0800DB6E  input/config preparation
0x0800DB78  BL 0x080203B4
```

Thus the lock-triggered event pass sees `lock=1` and cannot refresh `0x2000012A`.

## No late global-lock recheck in calculator

The only literal reference to global AE-lock byte `0x2001AD6E` in CTRL-System is the existing literal at `0x0800E508`, used by the lock-state access path. The calculator itself consumes the lock bit copied into its input structure; it does not re-read `0x2001AD6E` after entry.

Therefore an invocation that entered with an input snapshot containing `lock=0` will continue according to that snapshot even if another task stores the global lock byte while the invocation is in progress.

## Remaining scheduler boundary

The static control-flow proof now leaves exactly one unresolved condition:

```text
exposure task builds input with lock=0
    -> exposure calculator begins
       [can CTRL command-receiver task preempt here?]
    -> first-detent lock receiver stores global lock=1
    -> old calculator later reaches cache-refresh gate
```

There is no shared critical section spanning the old calculator and the lock receiver that would forbid this overlap. However, this pass does not yet recover a reliable task-priority/preemption ordering for the command-receiver task versus the exposure-control task.

Consequently two outcomes remain possible:

1. **completed-cycle latch** — if the command receiver cannot preempt the exposure calculation, the running unlocked pass completes before the lock store, and first detent freezes the most recently completed eligible Bv;
2. **in-flight-cycle latch** — if the receiver can preempt that path, the old input retains `lock=0`, may finish after the store, refresh `0x2000012A`, and that value is then frozen by the subsequent lock-triggered pass.

This is now strictly a scheduler/preemption issue. It is no longer a metering-order, event-order, lock-store, builder-snapshot, or calculator-global-read uncertainty.

## Oracle rule

The production oracle should continue to implement the deterministic logical rule:

```text
if not input.AE_lock and bracket_refresh_allowed:
    cached_calculation_Bv = input.final_Bv
allocator_Bv = cached_calculation_Bv
```

First detent sets lock state; it does not request a fresh meter sample. Do not synthesize a special half-press Bv read.

For ordinary host-side oracle use, freezing the current cache at first detent is the correct deterministic abstraction. Exact same-instant preemption behavior should remain a hardware/scheduler parity detail unless task-priority evidence closes it.

## Next photographic target

Further lock-scheduler work now has diminishing photographic value. The higher-value reverse-engineering target is the upstream producer of the 9-byte `AE measure result` consumed at `0x0800E1EC`:

```text
+0x00  Tlog
+0x02  traditional/rangefinder Bv
+0x04  BvExt
+0x06  BV_IR
+0x08  status
```

Recover the producer, raw meter-domain inputs, calibration/linearization, and exact transformation into the traditional Bv field used by the final-Bv selector.

## Research provenance

This note was produced from the checksum-verified `M10-R-30.22.23.34-Customer.FW` static trace on the temporary `m10r-metering-latch-trace` branch. Firmware bytes are not committed to the repository.
