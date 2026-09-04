# M10-R Exposure Engine v0.12: Traditional-Meter Cadence and Low-Light Gate

**Date:** 2026-09-04  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Original FW SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`  
**Decoded SHA-256:** `859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0`

## 1. Outcome

This pass closes the normal temporal relationship between traditional-meter acquisition, final-Bv selection, and first-detent AE lock.

The production CTRL architecture is event-driven:

```text
10 ms periodic timer callback
        |
        | every 10 callbacks
        v
AE event bit 0  (100 ms / 10 Hz)
        |
        v
registered AE event consumer 0x0800DCC6
        |
        v
final-Bv selector 0x0800D6A8
        |
        +-- eligible normal traditional path --> selector 5
        |                                     --> synchronous 10-sample ADC6 measurement
        |                                     --> calibrated traditional Bv
        |
        +-- final-Bv/BvExt change policy
        |
        v
optional downstream recalculation
```

First-detent AE lock is different:

```text
K_Release_1 / AE-lock command
        |
        v
CTRL stores AE_lock = 1
        |
        v
posts AE event bit 1 (0x02)
        |
        v
recalculation path only
```

It does **not** post bit 0 and therefore does **not** request a fresh traditional-meter sample.

Consequently, the Bv held by AE lock is the last eligible/accepted calculation Bv maintained by the ordinary metering/update cadence. There is no dedicated synchronous "meter once more at half press" operation.

## 2. One direct caller of the final-Bv selector

A complete direct-call survey of `0x0800D6A8` found one caller:

```text
0x0800DD28 -> 0x0800D6A8
```

That call lies inside the registered event consumer beginning at `0x0800DCC6`.

The event consumer waits for an event mask. When bit 0 is present and the local gate permits it, it invokes the final-Bv selector. Other event bits can wake the same consumer without causing a new meter acquisition.

This is important because the exposure system is not a set of independent polling loops calling `0x0800D6A8`; fresh-meter work is centralized behind this event bit.

## 3. Event-consumer registration

`0x0800DCC6` has no normal direct caller. Its Thumb pointer `0x0800DCC7` is present in the initialized callback table at `0x080397BC` and is registered during CTRL initialization.

The registration site around `0x08038DD2` installs it for the corresponding CTRL event/controller entry. The exact generic callback-API naming remains firmware-private, but the functional ownership is static: `0x0800DCC6` is an event callback/consumer, not a periodically called leaf function.

## 4. Normal 10-Hz fresh-meter cadence

The recurring fresh-meter producer is the callback beginning at `0x080104B8`.

Its Thumb pointer `0x080104B9` is stored at `0x08039A78` and referenced by the initialization code at `0x0803965C`.

Immediately before timer creation the initializer loads:

```text
r1 = 0x0A = 10
r0 = 0x080104B9
bl 0x0801CF60
```

Thus this timer is created with a 10-unit interval for callback `0x080104B8`. The same timer subsystem is used elsewhere with millisecond quantities (including the independently proven 300-ms low-light timer), and the callback's internal arithmetic confirms the unit as milliseconds.

The callback maintains a 16-bit counter. For the meter branch it performs the equivalent of:

```text
elapsed_units = tick_count * 10
if elapsed_units % 100 == 0:
    post_ae_event(0x01)
```

Therefore:

```text
base timer period          = 10 ms
fresh-meter event period   = 100 ms
traditional-meter cadence  = 10 Hz
```

The same callback multiplexes additional housekeeping at 20, 30, 250 and 1000 ms, strongly confirming it is a shared 10-ms periodic system callback rather than a meter-specific 100-ms one-shot.

At the end of the callback, the timer handle is started/re-armed again, making the cycle recurring while active.

## 5. Immediate bit-0 producers also exist

The event-post wrapper `0x0800DC4A` has several callers. Most pass event bit 1 (`0x02`) for recalculation/update only, but static tracing also found explicit bit-0 (`0x01`) producers, including:

```text
0x080020DC
0x08003558
0x0801013C
0x0801057E   <- periodic 100-ms producer inside the 10-ms callback
```

The non-periodic producers appear in configuration/state-change paths and can request an immediate fresh-meter pass. They do not change the normal periodic cadence established above.

## 6. Meter timer active state

The 10-ms timer is not simply left active for the entire lifetime of CTRL.

Two callbacks control it:

```text
0x08010440 -> stop timer via 0x080105E4
0x0801048C -> start timer via 0x080105F0
```

Their Thumb pointers are installed into the same CTRL state-machine slot during initialization:

```text
0x08010441 -> callback-table/reference at 0x08039864
0x0801048D -> callback-table/reference at 0x0803986C
```

Both belong to controller 0 / state 4 through the generic callback-registration triplet. The exact human-readable state name is not present in the recovered static path, so this document does not invent one. Functionally, entering/leaving that state controls the periodic metering timer.

The start wrapper sets its active flag and starts the timer handle. The stop wrapper stops the timer handle. Additional call sites can also start/stop the same timer during broader camera-state transitions.

For an implementation oracle, the safe abstraction is therefore:

```text
meter_timer_active = state-machine controlled
if active:
    10-ms base callbacks
    bit-0 fresh-meter request every 100 ms
```

not "meter every 100 ms forever."

## 7. Synchronous measurement once bit 0 is consumed

When the normal non-live-view traditional path is eligible, `0x0800D6A8` enables traditional-result acceptance and calls selector 5.

The selector-5 constructor at `0x080184D8` performs the traditional measurement synchronously. The already recovered normal path includes:

1. analog-source setup;
2. settling delay;
3. ten ADC6 samples with the firmware's sample delays;
4. integer average;
5. body-specific piecewise calibration;
6. low-light/status handling;
7. local nine-byte AE-result dispatch;
8. readback of the resulting traditional Bv.

Thus the 10-Hz event cadence is the **request cadence**; each eligible request contains a synchronous 10-sample acquisition before the selector completes.

## 8. 300-ms negative-Bv gate

The negative-Bv latch is byte:

```text
0x2001AD76
```

Its setter is the tiny function at `0x0800E166`.

The arm routine at `0x0800E16C` is equivalent to:

```text
traditional_Bv = get_traditional_Bv()
if traditional_Bv < 0:
    negative_bv_latch = 1
    start_negative_bv_timer(300 ms)
```

The exact immediate passed to the timer wrapper is:

```text
0x12C = 300
```

This arm routine is called from two exposure/state actions (`0x0801424C` and `0x080142B2`) after those actions synchronize on their surrounding event state. It is **not** called from every 100-ms periodic bit-0 pass, so a negative scene does not continuously restart the 300-ms timer on each periodic measurement.

## 9. The 300-ms timer is non-blocking

The timer wrapper at `0x0801077E` programs/starts a timer object. It is not a sleep or blocking delay.

A separate callback at `0x08010774` executes on expiry:

```text
r0 = 0
bl 0x0800E166
```

which clears the latch.

The callback is statically registered during initialization. Its Thumb pointer `0x08010775` is supplied to the timer-creation API. Therefore the low-light sequence is:

```text
state transition checks traditional Bv
        |
        | Bv < 0
        v
negative_bv_latch = 1
start 300-ms one-shot timer
        |
        | camera/task continues running
        v
300-ms timer callback
negative_bv_latch = 0
```

The expiry callback itself does **not** post event bit 0 and does not call the final-Bv selector.

## 10. What the latch suppresses

A necessary nuance is that "non-blocking timer" does not mean the normal traditional ADC acquisition continues through the latch.

In the normal non-live-view branch of `0x0800D6A8`, the selector checks `0x2001AD76`. When the latch is set it follows the hold path and skips the normal selector-5 traditional measurement/acceptance for that pass.

Therefore, during the 300-ms window:

- the CTRL task and periodic timer continue running;
- 100-ms bit-0 events can still occur;
- but the normal traditional branch holds previous final Bv and suppresses its selector-5 refresh while the latch is set.

On timer expiry, the latch becomes clear. Because expiry itself does not request a measurement, acquisition resumes on the **next** eligible bit-0 event.

With the normal 100-ms periodic cadence, that means the next ordinary traditional sample is expected within approximately:

```text
0..100 ms after the 300-ms latch expiry
```

subject to event/task scheduling and any simultaneous non-periodic bit-0 request.

So the static production behavior is better represented as a 300-ms hold followed by the next event-driven retry, rather than as a blocking 300-ms measurement delay.

## 11. First-detent lock does not sample

The previously recovered AE-lock receiver stores the lock byte and then invokes `0x0800DC4A` with:

```text
event mask = 0x02
```

The event consumer tests bit 0 for fresh-meter work. Therefore the lock-generated event does not call `0x0800D6A8` merely because the shutter reaches first detent.

The sequence is:

```text
ordinary meter tick / state event
    -> bit 0
    -> final-Bv selector
    -> possibly fresh synchronous traditional measurement
    -> accepted final Bv
    -> unlocked calculation may refresh cached calculation Bv

later: K_Release_1
    -> AE_lock = 1
    -> bit 1 only
    -> exposure recalculation/input processing
    -> cached calculation Bv refresh is suppressed by lock
```

This closes the earlier one-cycle ambiguity in the normal path: firmware does not intentionally obtain a new traditional-meter sample at first detent before locking. It holds the already maintained calculation coordinate.

A separate scheduler-level edge remains theoretically possible only for work that was already in flight before the lock store, as documented in v0.08; v0.12 does not alter that narrow concurrency boundary.

## 12. What "last Bv" means precisely

The held value is not necessarily the most recent raw ADC average.

Before reaching the calculation cache, the value passes through multiple production policies:

1. 100-ms fresh-meter request cadence;
2. synchronous ten-sample ADC average;
3. body-specific ADC->Bv calibration;
4. traditional-result validity/low-light gating;
5. final-Bv source selection;
6. final-Bv / BvExt change thresholds;
7. unlocked calculator cache-refresh rule.

Therefore the most precise implementation statement is:

> First-detent AE lock freezes the last **eligible accepted calculation Bv** maintained by the ordinary meter/final-Bv/calculator pipeline. It does not freeze a specially sampled half-press reading.

## 13. Executable cadence oracle

This pass adds:

```text
tools/m10r_meter_cadence.py
tests/test_m10r_meter_cadence.py
```

The state model covers:

- 10-ms active timer base;
- bit-0 fresh-meter event every 100 ms;
- first-detent event mask `0x02` only;
- 300-ms negative-Bv one-shot latch;
- non-blocking latch expiry;
- no synthetic meter event on expiry;
- resumed traditional eligibility on the next bit-0 event.

The model intentionally leaves camera-state naming abstract because the firmware provides functional callback ownership but not a trustworthy human-readable label for controller 0 / state 4.

## 14. Phone implementation implication

A faithful phone-side exposure controller should not perform a synchronous scene-meter read in the shutter-button half-press handler.

A better architecture is:

```text
meter-active state:
    periodically refresh M10-R meter model at about 10 Hz
    apply final-Bv eligibility/change policy
    while unlocked, allow accepted Bv to refresh calculation cache

first detent:
    set AE lock immediately
    reuse cached calculation Bv

negative-Bv transition:
    hold normal traditional refresh for 300 ms
    clear hold asynchronously
    retry on next meter event
```

The phone implementation may use a sensor-derived brightness proxy rather than Leica ADC6, but cadence, source gating, acceptance and lock placement should remain separate layers.

## 15. Remaining work

The highest-value remaining cadence questions are narrower:

1. assign a defensible semantic name to controller 0 / state 4 by tracing its outer state/event source;
2. determine whether any production state changes the normal 100-ms meter period rather than merely starting/stopping the timer;
3. measure the synchronous ten-sample selector-5 execution time on hardware if exact sub-100-ms lock latency parity is required;
4. validate low-light re-entry timing on a real M10-R around the negative-Bv boundary.

These are refinements. The core production cadence, first-detent sampling behavior, and 300-ms negative-Bv gate are now statically resolved.
