# M10-R Exposure Engine v0.17: Live-View Source Transition and AE-Lock Pipeline

**Date:** 2026-09-04  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Firmware SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Outcome

This pass closes the major runtime semantics around the M10-R's traditional-vs-CMOS Bv source transition and its interaction with physical AE lock.

The two previously anonymous source-forcing bytes can now be described conservatively but usefully:

```text
0x2001ADBB = shutter-open lifecycle/request latch
0x2001ADAE = live-view/video session-active (prepared-active) latch
```

The `ADAE` identity is established by its lifecycle:

```text
Prepare for live view / video
    -> ADAE = 1

LVVideoSync ... lf=1
    -> firmware logs "LVVideoSync last frame received"
    -> ADAE = 0
```

`lf` is therefore **last frame**, not "live finder".

The final-Bv source rule can now be frozen as:

```text
if shutter_open_lifecycle_latch || lv_video_session_active:
    selected_source = BvCMOS
elif ambient_light_calibration_valid && !negative_Bv_delay:
    selected_source = traditional_Bv
else:
    selected_source = previous_final_Bv
```

The existing ±25-count final-Bv/BvExt deadband remains downstream of this source choice.

## 2. Source states

### 2.1 Shutter-open latch `0x2001ADBB`

The ShutterMirror state machine sets `0x2001ADBB` immediately before the routine at `0x08019104`.

That routine contains the explicit diagnostic:

```text
Shutter: Open shutter not possible! (shutter status %i)
```

The paired routine at `0x0801917C` is the close-shutter path. The paired ShutterMirror event handler clears `0x2001ADBB` after the close sequence.

Therefore `ADBB` is not a generic exposure flag; it denotes the shutter-open lifecycle during which the final selector must use CMOS metering.

### 2.2 Live-view/video latch `0x2001ADAE`

The handler beginning at `0x08002EE8` logs:

```text
Prepare for live view / video received (...)
```

then performs:

```text
0x08002F4A  r0 = 1
0x08002F4C  r1 = &0x2001ADAE
0x08002F50  *r1 = 1
```

The LVVideoSync receiver at `0x08003068` decodes request flag bit 4 as `lf`.

When bit 4 is set it follows the firmware's explicit:

```text
LVVideoSync last frame received (... Flags vl %i lf %i ...)
```

path and executes:

```text
0x08003166  r0 = 0
0x08003168  r1 = &0x2001ADAE
0x0800316C  *r1 = 0
```

Thus `ADAE` spans the prepared/active LV-video session and is released by the last-frame boundary.

## 3. LVVideoSync update order

The ordering inside each command-0x32 receive is important.

After the incoming packet has updated CTRL state/ring data, `0x0800344E` calls `0x0800E186`.

`0x0800E186` is exactly:

```text
BL 0x0800D91C   ; build exposure input / run calculator
BL 0x0800DC40
```

and `0x0800DC40` is:

```text
r0 = 1
BL 0x0800F228   ; update BvCMOS from current LV/CMOS candidate
```

Therefore the per-sync order is:

```text
1. consume new LVVideoSync packet
2. run exposure builder/calculator using the already-selected final Bv
3. update BvCMOS from this packet's newly received CMOS meter values
4. optionally post exposure event mask 1
```

The new CMOS Bv from a frame is **not** fed into the calculator earlier in the same synchronous call.

## 4. Normal LV frame: selector update without immediate second calculation

At the end of the LVVideoSync handler:

```text
flags & 0x30 == 0
    -> post_exposure_event(mask=1)
```

Bit 4 is `lf`; bit 5 is the still-unresolved `rlv` flag. Ordinary frames with neither bit set therefore post event bit 0.

The exposure-event consumer at `0x0800DCC6` handles bit 0 by calling the final-Bv selector at `0x0800D6A8` (unless the service-calibration suppression guard is set).

If the selector reports that the final Bv/update state changed, the consumer promotes that into event bit 1.

However, the bit-1 calculation path contains this explicit gate:

```text
if ADAE != 0:
    skip BL 0x0800D91C
else:
    BL 0x0800D91C
```

Consequently, during an active LV/video session:

```text
frame N arrives
    -> calculator runs with previously selected final Bv
    -> frame N updates BvCMOS
    -> event bit 0 selects that BvCMOS as new final Bv
    -> immediate second calculator pass is suppressed because ADAE=1

later builder invocation (normally the next LVVideoSync)
    -> calculator can consume the newly selected final Bv
```

This is a deliberate staged pipeline. The practical host abstraction should treat a newly received CMOS Bv as becoming calculator-visible on a subsequent LV exposure-build cycle, not retroactively within the same packet callback.

Exact task scheduling can alter wall-clock latency, but not this instruction ordering.

## 5. Live-view entry behavior

The `Prepare for live view / video` handler sets `ADAE=1` but does not itself call the final-Bv selector or `0x0800F228` BvCMOS updater.

Therefore entering LV is staged:

```text
prepare command
    -> mark LV/video active
    -> no immediate new CMOS Bv calculation in this CTRL handler

first LVVideoSync
    -> exposure builder initially still sees the previously selected final Bv
    -> current packet then updates BvCMOS
    -> posted event selects BvCMOS as final source
    -> immediate recalculation is suppressed while ADAE=1

subsequent LV exposure-build cycle
    -> selected CMOS Bv becomes calculator-visible
```

This answers the earlier question "does entering live view immediately force one BvCMOS calculation?": **not at the prepare-command boundary**. The CMOS value is seeded by the LVVideoSync stream and enters the calculator through the staged per-frame pipeline.

## 6. Last-frame / LV-exit behavior

On `lf=1`, the LVVideoSync receiver clears `ADAE` before the common `0x0800E186` helper.

The common helper still runs:

```text
builder/calculator
then
BvCMOS update
```

but the handler's trailing event-post gate is:

```text
if flags & 0x30 == 0:
    post mask 1
```

Since `lf` is bit 4, the last-frame packet suppresses this mask-1 post.

Thus the last frame itself does **not** force the final-Bv selector to switch back to traditional Bv. The state transition is:

```text
last frame
    -> ADAE = 0
    -> common exposure/BvCMOS helper still runs
    -> no normal mask-1 selector event from that packet

next eligible exposure event
    -> final selector now sees ADAE=0
    -> if ambient calibration is valid and negative-Bv delay is clear,
       traditional Bv becomes eligible again
```

The existing periodic exposure event provides a natural next selector opportunity while the periodic AE/meter service is enabled.

## 7. Traditional meter activity during LV

Existing v0.12 work established a periodic mask-1 exposure update at approximately 100 ms while the AE/meter service is enabled.

The v0.62 lifecycle trace found no LV-specific stop call in either:

```text
0x08002EE8 Prepare for live view / video
0x08003068 LVVideoSync receive
```

Known stop/start callers instead belong to broader update/I/O/control transitions (for example the explicitly logged `I/O timer started/stopped` path) and other larger control lifecycles.

More importantly, when the periodic final-Bv selector executes while a CMOS-forcing state is active, the selector still performs its synchronous selector-5 measurement transaction before reading BvCMOS.

So the evidence supports this production abstraction:

```text
live view does not replace the traditional meter loop with an inactive stub;
traditional acquisition/update machinery can continue upstream,
while source selection chooses BvCMOS for the actual final Bv.
```

A future hardware trace could still refine exactly which larger camera states suspend the common periodic service, but there is no evidence that LV preparation itself stops it.

## 8. AE lock interaction

Physical AE lock remains downstream of source selection.

The lock receiver commits:

```text
AE_lock byte = 0x2001AD6E
```

then posts exposure event mask `0x02`.

The exposure builder snapshots that byte into exposure-input `+0x25 bit 1`.

The calculator at `0x080203B4` updates cached calculation Bv `0x2000012A` only when the lock bit permits it (subject to the already-known separate bracket/refresh condition). While locked, upstream final Bv and BvCMOS may continue to change, but the allocator continues from the cached calculation Bv.

### 8.1 Lock/unlock while LV is active

Mask `0x02` reaches the event consumer's bit-1 path. That path explicitly checks `ADAE` before invoking the builder:

```text
if ADAE != 0:
    do not run the event-triggered builder
```

Therefore a physical lock or unlock received during active LV does not force an immediate standalone exposure calculation from the event consumer.

Instead, the next synchronous LVVideoSync builder pass snapshots the new global lock state and applies it at the LV frame boundary.

Practical rule:

```text
LV active + half-press lock
    -> lock state is committed immediately
    -> allocator cache behavior takes effect on the next LV exposure-build cycle

LV active + unlock
    -> unlock state is committed immediately
    -> cache can refresh on the next LV exposure-build cycle
```

As with the earlier v0.08 scheduler boundary, an already in-flight calculation may retain its preexisting input snapshot; the deterministic host model should apply lock changes at the next model update boundary rather than inventing a special synchronous meter read.

### 8.2 Crossing LV exit while AE lock remains held

Because AE lock freezes the calculator cache rather than the upstream meter producers, an LV exit may change the **source-selected final Bv** without changing the **locked calculation Bv**.

The correct layered model is:

```text
CMOS/traditional source selection continues upstream
    -> final Bv can transition after ADAE clears

AE lock held
    -> cached calculation Bv remains frozen
    -> exposure allocation remains locked

unlock
    -> next eligible builder/calculator refreshes cached calculation Bv
       from the then-current final Bv
```

This preserves exposure lock across a source transition without freezing the sensor/rangefinder metering machinery itself.

## 9. Implementation-ready state machine

A host-side model can now separate the layers as follows:

```text
traditional_meter_loop (~100 ms while service enabled)
CMOS_LVVideoSync_stream(frame/event driven)

source_select():
    if shutter_open_lifecycle || lv_video_active:
        candidate = BvCMOS
    elif ambient_cal_valid && !negative_bv_delay:
        candidate = traditional_Bv
    else:
        candidate = previous_final_Bv

    apply Leica ±25-count final-Bv/BvExt deadband

calculator_update():
    build input from current final_Bv and lock state

    if !AE_lock && bracket_refresh_allowed:
        cached_calculation_Bv = input.final_Bv

    allocate exposure from cached_calculation_Bv
```

For LV specifically:

```text
PREPARE:
    lv_video_active = true

EACH NORMAL LV SYNC:
    calculator_update()                 # prior selected final Bv
    update_BvCMOS(current_frame)
    source_select() via event bit 0     # immediate builder suppressed in LV

LAST LV FRAME:
    lv_video_active = false
    calculator_update()
    update_BvCMOS(last_frame)
    no normal mask-1 selector post from this frame

NEXT ELIGIBLE EXPOSURE EVENT:
    source_select()                     # traditional path can become active
    calculator_update() if source/update changed and downstream gates permit
```

## 10. What remains open

The following are refinements rather than blockers for the two-source exposure oracle:

- exact wall-clock CA9/LVVideoSync frame cadence;
- exact scheduler ordering if a command receiver/event consumer preempts an in-flight calculator;
- semantic identity of command-0x32 flag bit 5 (`rlv`), which also suppresses the trailing mask-1 post;
- exact user-facing names of every broader control state that starts/stops the common periodic I/O/AE callback;
- pixel/statistical formulas for CA9 Spot / Integral / MFM / AV-field estimators.

The traditional-vs-CMOS source transition and AE-lock layering are now closed enough for implementation.

## 11. Research provenance

Primary trace artifacts:

```text
research/M10R_v051_command32_request_response_close.txt
research/M10R_v052_secondary_state_owners.txt
research/M10R_v054_ae14_ae16_callers.txt
research/M10R_v055_adbb_state_machine_callers.txt
research/M10R_v056_bv_source_switch_shuttermirror.txt
research/M10R_v057_camera_state79_bit0.txt
research/M10R_v058d_img_command32_flags_exact_accesses.txt
research/M10R_v059_lf_flag_owner.txt
research/M10R_v061_lv_transition_aelock.txt
research/M10R_v062_meter_service_lifecycle.txt
```

Supporting durable notes:

```text
M10R_EXPOSURE_ENGINE_v0_03_BV_SOURCE_AND_A_MODE_ORACLE.md
M10R_EXPOSURE_ENGINE_v0_06_PHYSICAL_AE_LOCK_EDGE.md
M10R_EXPOSURE_ENGINE_v0_08_AE_LOCK_SCHEDULER_BOUNDARY.md
M10R_EXPOSURE_ENGINE_v0_12_TRADITIONAL_METER_CADENCE_AND_NEGATIVE_BV_DELAY.md
M10R_EXPOSURE_ENGINE_v0_15_BVCMOS_PRODUCER_BOUNDARY.md
M10R_EXPOSURE_ENGINE_v0_16_METERING_MODE_ENUM_AND_CMOS_BV_FIELDS.md
```

Firmware bytes were reconstructed only transiently in CI. No firmware bytes are committed to the repository.
