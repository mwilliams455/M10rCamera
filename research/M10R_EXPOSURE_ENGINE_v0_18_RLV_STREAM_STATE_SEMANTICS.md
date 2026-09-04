# M10-R Exposure Engine v0.18 — RLV Stream-State Semantics

**Date:** 2026-09-04  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Firmware SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Outcome

Command-`0x32` flag bit 5, printed by CTRL as `rlv`, is now behaviorally closed even though the firmware does not expose a literal expansion of the acronym.

The safest implementation name is:

```text
rlv = live-view stream reset / reinitialization flag
```

This is a behavioral identity, not a claim that the literal acronym text means "reset live view".

The IMG flag builder at the `0x42161FA0` cluster reads the current indexed live-view workflow object's state field at `object +0x20C` and constructs the two transition bits as follows:

```text
if workflow_state == 0x0B:
    lf  = 1
    rlv = 0
elif workflow_state == 5:
    lf  = 0
    rlv = 0
else:
    lf  = 0
    rlv = 1
```

CTRL independently proves that:

- `lf` is the **last-frame** bit;
- `rlv=1` clears/reinitializes the twelve-entry LVVideoSync ring;
- either `lf` or `rlv` suppresses the ordinary trailing exposure-event mask-1 post because the receive path posts only when `(flags & 0x30) == 0`.

Therefore `rlv` marks a non-steady stream boundary where historical LV ring state must not be treated as continuous.

## 2. Exact IMG flag construction

The command-`0x32` flag byte is the shared byte at:

```text
0x408F0ECD
```

The owner selects the current workflow object from the table rooted through `0x408CECF0` and the current index held in the `0x408FC238` structure.

Its workflow-state field is addressed as:

```text
object
 + 8
 + 0xFF
 + 0xFF
 + 2
 + 4
 = object + 0x20C
```

At `0x42162010` the field is compared with `0x0B`; if equal, bit `0x10` is set in the outgoing command-`0x32` flags byte.

At `0x42162040` the same field is compared with `5`; if it is not `5`, bit `0x20` is set. The `0x0B` branch has already bypassed this second test, so `lf` and `rlv` are mutually staged by this builder.

## 3. CTRL behavior closes the meaning of the bits

CTRL's command-`0x32` receiver logs the flags as:

```text
vl lf rlv mag vr vs exps
```

### `lf`

Bit 4 drives an explicit firmware diagnostic:

```text
LVVideoSync last frame received
```

and clears the LV/video active latch `0x2001ADAE`.

Thus:

```text
bit 4 = lf = last frame
```

### `rlv`

Bit 5 is tested at `0x08003220..0x0800322E`.

When it is asserted, CTRL enters the same reset branch used by an internal reset latch:

```text
0x2001ADAB = 0
for each of 12 LV ring entries:
    ring[i].word0 = 0
```

The ring is the already-identified twelve-entry `0x24`-byte LVVideoSync history at `0x200190AC`.

This proves that `rlv` is not an exposure value, meter-selection bit, or ordinary live-view mode bit. It is a stream-history invalidation/reinitialization boundary.

## 4. Workflow-state evidence

The firmware contains the following named live-view states in order:

```text
cap_liveview_init
cap_liveview_wait_for_ccpu
cap_liveview_wait_for_img
cap_liveview_wait_for_first_frame
cap_liveview_capture
cap_liveview_stopping
cap_liveview_end_state
```

The direct writers to `object +0x20C` found across the entire IMG image are only:

```text
0x4216AA1E
0x4216ABDC
0x4216E324
```

The capture/setup path at `0x4216E324` writes state value `1`.

The sensor-power/setup family at `0x4216AA1E` and `0x4216ABDC` writes state value `2` or `3` according to the setup condition.

That establishes a real startup progression beginning with values `1/2/3`, not merely a guessed enum order.

Across all exact reads of `object +0x20C`, the firmware repeatedly compares:

```text
1 / 2 / 3     startup group
4 / 5 / 0x0B  live-stream group
```

State values `5` and `0x0B` are each compared thirteen times in the recovered read map.

The dense frame-processing cluster at `0x421578C0..0x421580C0` treats states `4` and `5` as active-frame states and sends them through common frame-processing code. State `0x0B` follows a distinct special/terminal branch.

The same region contains the explicit diagnostic:

```text
IMG: LIVE/VIDEO E_IMG_LV_NO_USE_FRAME_WB0
```

so these comparisons are firmly inside live/video frame-state handling.

## 5. State-5 interpretation

The evidence strongly supports:

```text
workflow state 5 ≈ steady cap_liveview_capture state
```

because:

1. the named state sequence places `cap_liveview_capture` after the init/wait states;
2. direct writes prove values `1/2/3` occur during capture/sensor initialization;
3. states `4` and `5` are handled as active-frame states;
4. state `5` is uniquely the state in which neither `lf` nor `rlv` is asserted;
5. that is exactly the behavior expected for the steady continuous LV stream.

This mapping is strong enough for a host behavioral model, but the firmware does not print a direct `state 5 = cap_liveview_capture` symbolic assignment. Preserve that distinction in documentation.

## 6. State-0x0B interpretation

State `0x0B` is the source of `lf=1` and enters a distinct live/video terminal/special branch in the frame-state logic.

CTRL independently interprets the resulting flag as "last frame" and clears the LV/video session-active latch.

Therefore the useful behavioral identity is:

```text
workflow state 0x0B = explicit last-frame / terminal live-view state
```

Again, the numeric enum name itself is not printed by the firmware, so avoid inventing a stronger symbolic label.

## 7. Final RLV rule for the replica

A host implementation does not need the literal expansion of `rlv`; it needs the production behavior:

```text
if last_frame_state:
    lf = true
    rlv = false
elif steady_live_capture_state:
    lf = false
    rlv = false
else:
    lf = false
    rlv = true
```

On CTRL/host receive:

```text
if rlv:
    invalidate/reset LV history ring
    do not post the ordinary continuity-driven meter update for this packet

if lf:
    end the active LV/video source-forcing interval
    do not post the ordinary continuity-driven meter update for this packet
```

The important semantic is continuity: only steady capture frames extend the normal LV stream history.

## 8. Closed / open status

### Closed

- bit 4 = `lf` = last frame
- bit 5 `rlv` invalidates/reinitializes LV stream history
- state `5` is the unique steady-stream state for flag construction
- state `0x0B` is the explicit last-frame/terminal state for flag construction
- `rlv` and `lf` both suppress the ordinary trailing mask-1 exposure event

### Strong but not literal-symbol proof

- state `5` corresponds to the named `cap_liveview_capture` state
- the most natural acronym expansion is "reset live view"

For implementation and future notes, prefer the behavioral name **LV stream reset/reinitialization flag** unless a literal symbol table later proves the acronym expansion.

## 9. Research provenance

Primary artifacts:

```text
research/M10R_v058d_img_command32_flags_exact_accesses.txt
research/M10R_v059_lf_flag_owner.txt
research/M10R_v063_rlv_semantic.txt
research/M10R_v064_workflow_state5_owner.txt
research/M10R_v065_state5_setter_callers.txt
research/M10R_v066_workflow_state_writers.txt
research/M10R_v067_object_field_write_slice.txt
research/M10R_v068_global_object20c_signature.txt
research/M10R_v068b_object20c_access_classifier.txt
research/M10R_v069_object20c_writer_owners.txt
research/M10R_v070_liveview_event_xrefs.txt
research/M10R_v071_object20c_read_comparisons.txt
research/M10R_v072_state4_5_0b_semantics.txt
```

Supporting transition model:

```text
research/M10R_EXPOSURE_ENGINE_v0_17_LV_TRANSITION_AE_LOCK_PIPELINE.md
```

Firmware bytes were reconstructed only transiently in CI and are not committed to the repository.
