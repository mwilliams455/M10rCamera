# M10-R v2.11 — TONE HARDWARE ARITHMETIC BOUNDARY

Date: 2026-09-05
Branch: `m10r-color-science-trace`

Status: **FROZEN boundary**, not a freeze of the unknown hardware rounding mode.

## 1. What v2.10 established

The canonical tone helper is the ARM function at `0x420D3C1C..0x420D4290`.

It performs only:

1. descriptor-field -> B2Y register programming,
2. TBL0/TBL1 upload,
3. enable/error handling.

A bounded exact-ARM scan of the low-level B2Y driver region `0x420D0000..0x420D5000` found no accesses to the tone register page `0x20020800..0x2002087C` outside this helper.

Therefore the firmware code recovered here does **not** contain a software implementation of the live tone lookup/multiply. The pixel arithmetic executes inside B2Y hardware.

This is the important boundary result: static firmware instructions can recover configuration and calibrated tables exactly, but do not expose the hardware multiplier's rounding rule.

## 2. Exact active tone geometry

The latest authoritative hardware ABI is:

```text
resolutionCode = 1
active entries = 0x2800 = 10,240
bytes/entry    = 4
active bytes   = 0xA000 per bank
TBL0 address   = 0x20A00000
TBL1 address   = 0x20A0A000
```

For M10-R firmware 30.22.23.34, TBL0 and TBL1 are byte-identical for each LOW/MEDIUM/HIGH contrast profile.

**Correction to historical handoff wording:** any v1.25 prose referring to the recovered tone assets as “4096-entry” tables is stale. `M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md`, the extractor, and v2.07 validation agree on **10,240 active entries**.

## 3. Frozen functional model

The table representation remains frozen as Q15 multiplicative gain:

```text
unity = 0x8000
idx   = x >> 1
gain  = tone[idx] / 32768
```

LOW is exactly unity at every active entry.

The supported first-parity coordinate capacity is:

```text
x = 0 .. 0x4FFF
idx = 0 .. 0x27FF
```

## 4. Hardware-cycle arithmetic remains unresolved

The two bounded integer candidates remain:

```text
truncate:
    y = (x * tone[x >> 1]) >> 15

round-nearest candidate:
    y = (x * tone[x >> 1] + 0x4000) >> 15
```

For the factory-default MEDIUM table over all 20,480 candidate input coordinates:

```text
both outputs monotonic = true
both output range       = 0 .. 20479
candidate differences   = 8,442 / 20,480 inputs
maximum candidate delta = 1 code value
```

Thus the choice matters for bit-exact reproduction, but it is only a one-code difference and cannot be selected from monotonicity, identity behavior, or table plausibility.

Do not freeze either candidate as the Leica hardware rule without new evidence.

## 5. Descriptor/register map facts relevant to implementation

The 0xB0 descriptor is copied into a dense hardware register set beginning at `0x20020800`.

Control fields:

```text
+0x00 -> 0x20020800 bit 0
+0x04 -> 0x20020800 bit 1
+0x08 -> 0x20020804 bits 0..1
+0x0C -> 0x20020804 bits 4..5
+0x10 -> 0x20020804 bits 8..9
+0x14 -> 0x20020804 bit 16
+0x18 -> 0x20020804 bits 24..29
```

Remaining descriptor fields populate the tone parameter page from `0x20020808` through `0x20020878`.

Notable M10-R values include:

```text
+0x1C = 0x0400
+0x20 = 0x0A65
+0x24 = 0x019A
+0x2C = 0x8000
+0x38 = 0x5000
+0x3C = 0x2CA0
+0x40 = 0x2CA0
+0x4C = low16 0x8000
+0x60 = 0x5000
+0x74 = low16 0x8000
+0x78..+0x94 = 0x3FFF
```

The repeated `0x3FFF` fields are packed into `0x2002086C..0x20020878` and remain consistent with 14-bit limit/clamp fields. Their exact semantic names and clamp sequencing are not proven.

## 6. Differential-gamma domain compatibility does not close stage order

The frozen differential-gamma transfer has output range:

```text
0 .. 0x3FFF
```

If that output directly addressed the tone model using `idx=x>>1`, only tone indices:

```text
0 .. 8191
```

would be used, leaving 2048 of the 10,240 active tone entries unused.

This is **not** evidence against DG -> tone; unused entries may simply provide hardware headroom. It is domain compatibility evidence only and must not be converted into a stage-order claim.

## 7. Implementation consequence

First-parity software should expose both unresolved switches explicitly:

```text
stage order: configurable
Q15 rounding: truncate | nearest
```

The default implementation may choose one documented candidate for convenience, but validation tooling must retain the alternate candidate until camera-output evidence or a hardware specification resolves it.

## 8. Next action

Build a scalar nonlinear B2Y oracle around the exact extracted assets:

- exact expanded differential-gamma curve,
- default MEDIUM tone table,
- switchable relative DG/tone order,
- switchable Q15 rounding,
- explicit coordinate clamps,
- deterministic output/hashes for candidate comparison.

This advances first-parity testing without inventing either missing hardware fact.
