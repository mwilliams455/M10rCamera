# M10-R v2.18 — DEFAULT STILL NONLINEAR ACTIVE SET FROZEN

Date: 2026-09-05
Branch: `m10r-color-science-trace`

Status: **FROZEN for the recovered default STILL B2Y nonlinear controls.**

## 1. Why this matters

The earlier stage-order investigation treated de-knee, differential gamma, interpolation gamma, and tone as potentially active nonlinear transforms. The v2.17 control proof now shows that this is too broad for the factory-default STILL path.

For the default STILL calibration records recovered from `B2Y.bin`:

```text
de-knee             DISABLED
interpolation gamma DISABLED
differential gamma  ENABLED
tone                 ENABLED
```

Therefore the dominant unresolved scalar nonlinear ordering question for default STILL is reduced to:

```text
differential gamma  <->  tone
```

This is a much cleaner empirical target.

## 2. De-knee disabled

Calibration selector ID `0x01`:

```text
size          = 0x60 bytes
all_zero      = true
nonzero_count = 0
```

The low-level de-knee helper at `0x420D1170` maps record byte `+0x00` bit 0 directly to:

```text
0x20020040 bit 0
```

The default record supplies zero, so the de-knee enable bit is clear.

## 3. Interpolation gamma disabled

Calibration selector ID `0x09`:

```text
size          = 0x18 bytes
all_zero      = true
nonzero_count = 0
```

The low-level helper at `0x420D25A4` maps:

```text
record +0x00 bit 0 -> 0x20020800 bit 16
record +0x04 bit 0 -> 0x20020800 bit 17
```

Both fields are zero in the default record. When the helper is called in disable mode it also explicitly clears the same two bits.

Thus interpolation-gamma control is off in the recovered default STILL configuration.

## 4. Differential gamma enabled

Calibration selector ID `0x0B`:

```text
size   = 0x08
u32 +0 = 1
u32 +4 = 1
```

The exact helper at `0x420D15E8` maps:

```text
record +0x00 bit 0 -> 0x20020800 bit 24
record +0x04 bit 0 -> 0x20020800 bit 25
```

Both are therefore enabled in default STILL.

The transfer encoding and expanded 32,768-entry curve remain frozen separately in v1.89.

## 5. Tone enabled

Tone descriptor ID `0x08` begins:

```text
+0x00 = 1
+0x04 = 0
+0x08 = 1   // M10-R resolutionCode
+0x0C = 1   // initial tone bank selection field
```

The tone helper maps descriptor `+0x00` to `0x20020800 bit 0`, so the main tone stage is enabled.

The tone Q15 gain interpretation and 10,240 active-entry geometry remain frozen separately in v1.92 / v2.11.

## 6. One tone stage, not two

v2.14 already froze TBL0/TBL1 as alternate banks of a single tone stage. For this M10-R firmware the two banks are byte-identical for each contrast profile, so runtime bank switching is mathematically neutral for first parity.

## 7. What remains outside this freeze

This note does **not** claim that every B2Y module between matrix input and JPEG output is bypassed. In particular, interpolation/resampling, edge/detail processing, offset/shift, WB clipping, Y blend, YC conversion, and JPEG encoding remain distinct hardware functions.

It freezes only the recovered nonlinear curve controls relevant to the current scalar tonal-order problem.

## 8. First-parity implication

For flat/neutral, low-texture patches on a factory-default STILL JPEG, the nonlinear scalar oracle can now legitimately focus first on these two candidates:

```text
A: differential gamma -> tone
B: tone -> differential gamma
```

with Q15 rounding retained as a secondary switch.

Because v2.12 found order differences on ~14.6k/20.48k candidate coordinates with peak deltas around 1.23k codes, while rounding is much smaller, camera JPEG/DNG reference pairs should prioritize order discrimination before bit-exact rounding.
