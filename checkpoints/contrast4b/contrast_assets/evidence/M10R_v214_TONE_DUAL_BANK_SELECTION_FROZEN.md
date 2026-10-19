# M10-R v2.14 — TONE DUAL-BANK SELECTION FROZEN

Date: 2026-09-05
Branch: `m10r-color-science-trace`

Status: **FROZEN for first-parity rendering.**

## 1. Question closed

The two uploaded tone tables (`TBL0` at `0x20A00000`, `TBL1` at `0x20A0A000`) are not evidence for two sequential tone transforms.

The low-level selector at `0x420D038C` manipulates a single selection field in tone control register:

```text
0x20020804 bits 4..5
```

This is the same field initially populated from tone descriptor `+0x0C` by the main helper `0x420D3C1C`.

Therefore TBL0/TBL1 are alternate banks of one tone stage.

## 2. Exact selector behavior recovered in v2.13

The routine first verifies the relevant B2Y state, then reads:

```text
0x20020804 bits 0..1
```

These are the already-recovered tone resolution/size code from descriptor `+0x08`.

For the visible cases:

```text
resolutionCode == 0:
    clear bits 4..5 -> selector field 0

resolutionCode == 1:
    if argument == 0x64:
        bits 4..5 = 1
    else:
        bits 4..5 = 0

other visible resolution codes:
    error path in this routine
```

M10-R uses:

```text
resolutionCode = 1
```

The routine is called by the live B2Y programmer `0x42152F8C` with a runtime object field, so bank selection can be changed dynamically after the descriptor helper has initialized the field.

The exact semantic name of the caller's `0x64` threshold/argument is not required for first parity and is not frozen here.

## 3. Why this closes the two-stage ambiguity

A single 2-bit register field is rewritten to choose between table-start/bank states. The mechanism does not invoke one table and then the other as separate pixel operations.

Thus do **not** implement:

```text
pixel -> TBL0 tone transform -> TBL1 tone transform
```

Implement one tone transform with a selectable table bank.

## 4. M10-R-specific simplification

For firmware `30.22.23.34`, the recovered active TBL0 and TBL1 payloads are byte-identical for each contrast profile.

Therefore, for first-parity M10-R rendering:

```text
select TBL0 == select TBL1
```

mathematically.

The runtime bank selector can be omitted from pixel math so long as the selected contrast profile is correct. Preserve bank-selection metadata only if later diagnostics need to emulate register state.

## 5. Remaining nonlinear blocker

This result does **not** resolve the relative pixel order of:

```text
differential gamma
vs.
the single tone stage
```

That remains the high-impact unresolved switch identified by v2.12.

Rounding remains a secondary bit-exact issue; clamp placement is inert over the currently supported scalar candidate domain.
