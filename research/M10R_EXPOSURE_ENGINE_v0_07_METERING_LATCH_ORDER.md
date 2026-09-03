# M10-R Exposure Engine v0.07: Metering-to-Lock Ordering Boundary

## Outcome

The first-detent AE-lock investigation now has a static CTRL task/message-ordering proof. The exact identity of the final Bv sample remains deliberately provisional, but the uncertainty has been reduced to one narrow cross-task overlap window.

The important new result is that the lock command does **not** synchronously request one final unlocked meter calculation. Instead:

1. the CTRL command receiver commits the AE-lock byte;
2. only after that store does it post exposure update mask `0x02`;
3. the exposure-control event loop consumes bit 1 of that event word;
4. that branch invokes the normal exposure-input builder;
5. the builder snapshots the already-committed lock byte into exposure-input `+0x25 bit 1`;
6. the builder directly invokes the exposure calculator;
7. with lock bit 1, the calculator skips refresh of cached calculation Bv at `0x2000012A`.

Therefore the calculation *scheduled by the lock command itself* cannot be the calculation that performs a final unlocked Bv refresh.

## CTRL receiver ordering

The AE-lock command receiver remains at `0x0800248E`. Its relevant calls are now resolved explicitly:

| Order | Call site | Target | Effect |
|---|---:|---:|---|
| 1 | `0x080024A0` | `0x0800DE18` | write the received lock value to the CTRL AE-lock byte (`0x2001AD6E`) |
| 2 | `0x080024A6` | `0x0800DC4A` | post exposure update mask `2` |

There is no intervening meter/Bv-refresh call between these two operations.

`0x0800DC4A` is an exposure-update helper. It first calls `0x08011238` to check the event facility, then forwards the caller's mask through the per-task event sender at `0x0801CF26`. For AE lock the caller supplies `2`, i.e. event-word bit 1.

This closes the receiver-local ordering as:

```text
CTRL command 0x12 payload 1
    -> store AE_lock = 1
    -> post exposure event mask 0x02
```

## Exposure-control event consumer

The exposure-control event loop extracts bit 1 from its received event word at `0x0800DD42..0x0800DD4E`. When that bit is set, the normal eligibility check at `0x08001A38` is performed; if accepted, the branch at `0x0800DD58` calls the exposure-input builder at `0x0800D91C`.

So the lock update crosses a real task/event boundary rather than falling straight through from the command receiver into the calculator.

## Builder-to-calculator ordering

Inside `0x0800D91C`, the lock byte is snapshotted at `0x0800DA62` into exposure-input `+0x25 bit 1`.

The recovered call graph has one direct call to the exposure calculator `0x080203B4`, at `0x0800DB78`, from this builder. Thus the relevant sequence is:

```text
event bit 1 consumed
    -> build exposure input
    -> snapshot AE_lock into +0x25 bit 1
    -> call calculator 0x080203B4
```

The previously recovered calculator gate remains unchanged: lock `0` permits a refresh of cached calculation Bv at `0x2000012A`; lock `1` suppresses that write and reuses the cached value.

### Consequence

The calculation caused by receipt of AE-lock payload `1` necessarily sees the committed lock state and therefore cannot perform a final unlocked refresh of `0x2000012A`.

This rules out the simple model:

```text
first detent -> force one last unlocked Bv refresh -> set lock -> calculate
```

The firmware instead implements a stateful cache freeze driven by the lock bit.

## Remaining race boundary

One timing question is still not closed statically.

The command receiver and exposure-control calculation are separated by a task/event boundary. A calculation that began **before** the receiver committed `AE_lock=1` may already have snapshotted `AE_lock=0` at `0x0800DA62`. If that earlier calculation can remain in flight while the receiver task stores the new lock state, it can still pass the unlocked Bv-refresh gate and update `0x2000012A` before it finishes.

The subsequent event-2 calculation will then see lock `1` and freeze whatever value is in the cache at that point.

Static evidence in this pass does not yet establish a scheduler/priority rule, critical section, mutex, or other mutual exclusion that forbids that overlap. Therefore these two possibilities remain open:

1. **completed-cycle latch:** first detent freezes the most recently completed unlocked Bv calculation;
2. **in-flight-cycle latch:** an unlocked calculation already in progress at the detent is allowed to complete, and its Bv becomes the frozen cache value.

The uncertainty is now specifically this cross-task overlap; there is no longer uncertainty about the ordering of the lock-triggered calculation itself.

## IMG ordering evidence

### BSTM is child-first

The BSTM dispatcher at `0x420A274C` calls the child-state wrapper at `0x420A2840` from `0x420A2768`. The wrapper recursively calls the same dispatcher from `0x420A2852`.

This confirms the framework rule needed by the v0.06 handoff: nested state machines are evaluated before the current state's own transition table.

A broad scan of the BSTM transition load-image block finds multiple `0xD6` transition records across the IMG state tree. Those records must not be treated as one flat sequence; only records belonging to the active ancestry/children of the current state participate in a given dispatch. Mapping every global `0xD6` record to its owning state is therefore useful follow-up work, but it is no longer required to establish the CTRL lock-to-calculator ordering above.

### External exposure-start probe

An independent IMG path provides a useful temporal constraint. The external exposure-start action at `0x421BE6EC` does:

```text
mov r0, #0xD6
BL  0x421BC9E8   ; emit K_Release_1
BL  0x421BF23C   ; later exposure preparation
```

So this path synthesizes first detent **before** its later exposure-preparation call. It does not meter/prepare first and then assert AE lock.

This does not by itself prove the physical-key cycle timing, but it is consistent with AE lock freezing a continuously maintained exposure/Bv state rather than requesting a special final sample at first detent.

## Oracle boundary after v0.07

The oracle may now model all of the following as confirmed:

- `K_Release_1` transitions `ae_lock_disabled -> ae_lock_enabled`;
- the enabled-state entry callback sends CTRL command `0x12`, payload `1`;
- CTRL commits the lock byte before posting exposure update mask `2`;
- event bit 1 drives the normal exposure-input builder;
- that builder snapshots the committed lock state before calling the calculator;
- the lock-triggered calculator pass cannot refresh cached calculation Bv;
- `K_Release_2` leaves lock enabled;
- `K_Release_0` transitions back to disabled and sends payload `0`.

The oracle should still **not** claim whether the frozen Bv is the most recently completed unlocked cycle or the completion of an unlocked cycle already in flight at the exact instant of first detent.

## Next investigation target

Resolve whether an unlocked builder/calculator invocation can overlap the CTRL AE-lock command receiver.

Highest-value static targets:

1. identify the task descriptors and priorities for the command-receiver task and the exposure-control event task;
2. inspect scheduler/preemption policy around the receiver store at `0x0800DE18` and builder/calculator path `0x0800D91C -> 0x080203B4`;
3. search for any shared mutex, critical section, scheduler lock, or event-handling serialization that spans the lock snapshot/cache-refresh region;
4. if static scheduling proof remains ambiguous, use a timestamped hardware trace of first detent, Bv/cache update, command `0x12`, and exposure calculation.

A secondary IMG task is to map the other `0xD6` transition records in the BSTM initializer block to their owner states and identify which lie on the active exposure-control ancestry around `AE_LOCK_CONTROL`.

## Reproducibility

```bash
python tools/m10r_metering_latch_inspect.py \
  firmware/sections/090_CTRL-System.bin \
  firmware/sections/092_IMG-System.bin
python -m unittest discover -s tests -v
```

The v0.07 inspector decodes and verifies the relevant Thumb `BL` targets rather than relying only on prose disassembly, so the receiver, event-post, event-consumer, builder, calculator, BSTM-recursion, and IMG exposure-start orderings are machine-checked against the recovered firmware sections.
