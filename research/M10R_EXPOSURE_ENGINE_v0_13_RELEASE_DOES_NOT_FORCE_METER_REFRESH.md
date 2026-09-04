# M10-R Exposure Engine v0.13: Release Does Not Force a Fresh Meter Read

**Date:** 2026-09-04  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Original FW SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## Outcome

This pass closes the remaining shutter-timing question from v0.12.

Neither the first shutter detent nor the second detent has a proven path that forces exposure event mask `1`, calls the final-Bv selector `0x0800D6A8`, or invokes the selector-5 traditional-meter acquisition path.

The production abstraction is therefore:

```text
periodic metering service (~100 ms practical cadence)
    -> fresh traditional measurement / final-Bv selection

first detent
    -> AE lock command
    -> exposure event mask 2
    -> downstream recalculation using frozen allocator Bv cache

second detent / release-control state
    -> release-state command/control path
    -> no special mask-1 meter refresh
```

A phone replica should not perform a fresh meter sample merely because the shutter reaches first or second stage.

## 1. Exposure-event masks are semantically distinct

The exposure event poster is `0x0800DC4A`.

Recovered producers show:

- periodic metering callback `0x0801057E` posts **mask 1**;
- AE-lock receiver `0x080024A6` posts **mask 2**;
- many parameter/settings changes also post mask 2;
- release-request helper `0x08010614` posts a high-bit control event (`0x40000000`), not mask 1.

Within the exposure-event consumer, mask 1 is the path that can invoke `0x0800D6A8` and therefore cause a synchronous fresh traditional-meter acquisition. Mask 2 is the downstream exposure-recalculation path.

This distinction means the known first-detent AE-lock transition asks for recalculation but does not request a new meter/select pass.

## 2. Leica's release simulator uses command 0x0A

Firmware strings:

```text
IMG Simulator: Release 1st stage button
IMG Simulator: Release 2nd stage button
```

both funnel through CTRL helper `0x0800C40C` with different release-state values.

`0x0800C40C` builds a five-byte command object whose command byte is `0x0A`, then passes it to generic dispatcher `0x08016B90`.

It does not itself call:

```text
0x0800DC4A   exposure event post
0x0800D6A8   final-Bv selector
0x080184D8   AE-measure constructor
```

## 3. Command-0x0A dispatch is state copying, not metering

The command-0x0A branch lands at `0x08016F28`.

It switches on the signed release/control state value:

```text
0, 1, 2, ... 8
```

and, for each state, copies an existing global/state word into a corresponding release/control structure slot. Representative cases:

```text
state 0 -> copy source word to structure +0x3C
state 1 -> copy source word to structure +0x40
state 2 -> copy source word to structure +0x44
...
```

The branch contains no call to the exposure-event poster and no call to any meter-selection/acquisition function.

Thus Leica's own simulator route independently confirms that changing release-stage state does not synthesize a fresh traditional-meter pass.

## 4. Release request control event is also not mask 1

The separate firmware diagnostic:

```text
Release request...
```

reaches helper `0x08010614` in one production path.

That helper performs its own control/state operation and posts:

```text
0x40000000
```

to the exposure event object. It does not post mask 1.

This reinforces the separation between shutter/release control events and the periodic fresh-meter event.

## 5. Relationship to AE-lock timing

The combined timing chain is now:

```text
normal metering:
    scheduler callback
        -> mask 1 every ~100 ms practical cadence
        -> final-Bv selector
        -> selector-5 10-sample ADC acquisition
        -> final Bv/update state

first detent:
    IMG AE-lock state transition
        -> CTRL command 0x12 payload 1
        -> global lock byte = 1
        -> mask 2
        -> calculator runs with lock=1
        -> cached allocator Bv is not refreshed

second detent:
    release-control state update
        -> command 0x0A/state-control path
        -> no mask-1 fresh meter request established
```

Therefore the earlier rejected model is now closed from both sides:

```text
first detent -> force fresh unlocked Bv -> lock -> calculate
```

is not the production behavior recovered from the firmware.

## 6. Host implementation rule

Use this deterministic rule:

```text
meter freshness is owned by the periodic metering service

on first detent:
    freeze allocator cache immediately when AE-lock transition is processed
    do not force another meter acquisition

on second detent:
    proceed with capture/release state
    do not force another meter acquisition unless a future independent path proves one
```

The live meter may continue updating upstream while AE lock is active; the held exposure comes from the downstream cached calculation Bv.

## Remaining timing refinement

The only timing refinement still worth pursuing for hardware-exact parity is the exact user-facing identity of the camera states that start/stop periodic callback `0x080104B8`, plus direct confirmation of the inferred 10-ms scheduler base. Neither is required for the current host/oracle architecture.
