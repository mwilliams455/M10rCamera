# M10-R v1.92 — Tone-control Q15 gain model FROZEN

Status: **FROZEN for first-parity functional rendering**, with explicitly listed hardware-arithmetic caveats.

Canonical firmware: `M10-R-30.22.23.34-Customer.FW`

SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Selector contract

Tone selector around `0x42154BB4` resolves:

```text
ID 0x08 -> tone descriptor
ID 0x19 -> TBL0
ID 0x1A -> TBL1, conditionally
```

It calls ARM helper `0x420D3C1C` with:

```text
r0 = ID 0x08 descriptor
r1 = ID 0x19 TBL0
r2 = ID 0x1A TBL1
r3 = lookup/failure flag
```

Contrast-keyed records exist for:

```text
LOW
MEDIUM
HIGH
```

and the same contrast record is aliased by STILL/STILLLINK/SLIVE/SMAGNI mode keys.

## 2. Descriptor and LUT-length selection

ID 0x08 is a 0xB0-byte hardware descriptor.

Relevant proven fields:

```text
+0x00 = 1       -> bit 0 of B2Y 0x20020800-family control
+0x04 = 0       -> bit 1 control
+0x08 = 1       -> LUT resolution/size code
+0x0C = 1       -> hardware mode field and part of TBL1-load condition
+0x14 = 0       -> hardware mode bit and part of TBL1-load condition
```

The ARM helper maps `+0x08` to active entry count:

```text
code 0 -> 0x5000 entries = 20480
code 1 -> 0x2800 entries = 10240
other  -> 0x1400 entries =  5120
```

These are exactly:

```text
0x5000 >> 0 = 0x5000
0x5000 >> 1 = 0x2800
0x5000 >> 2 = 0x1400
```

M10-R uses code `1`, therefore:

```text
10240 entries
4 bytes / entry
0xA000 active bytes per bank
```

TBL0 is copied to:

```text
0x20A00000
```

TBL1 is copied to:

```text
0x20A0A000
```

when:

```text
descriptor +0x14 == 0
and descriptor +0x0C == 1
```

The M10-R descriptor satisfies both conditions, so both banks are active.

## 3. TBL0 and TBL1 are functionally redundant in this firmware

For each contrast setting, the active TBL0 and TBL1 regions are byte-identical:

```text
LOW    TBL0 == TBL1
MEDIUM TBL0 == TBL1
HIGH   TBL0 == TBL1
```

Therefore a first-parity software renderer does not need two distinct tone curves for M10-R firmware 30.22.23.34. Preserve two-bank structure in the ABI if desired, but one shared curve produces the same calibrated values.

## 4. Q15 multiplicative-gain interpretation

All active table values fit in unsigned 16 bits despite being stored as 32-bit words.

Neutral value:

```text
0x8000 = 32768
```

LOW is exactly `0x8000` at all 10240 active entries.

If interpreted as Q15 gain:

```text
gain = table[index] / 32768.0
```

LOW becomes exactly unity gain.

This is not merely a visual coincidence: interpreting LOW as a direct-output curve would produce a constant `32768` output for all inputs, which is not a meaningful tone transform. Interpreting it as multiplicative gain produces exact identity.

Measured active gain ranges:

```text
LOW:     1.000000 .. 1.000000
MEDIUM:  0.592987 .. 1.072083
HIGH:    0.494080 .. 1.153931
```

Thus the calibrated hierarchy is exactly consistent with:

```text
LOW    = no additional contrast gain
MEDIUM = moderate S-shaped contrast gain
HIGH   = stronger S-shaped contrast gain
```

## 5. Resolution/index model

Because active entry count is exactly `0x5000 >> resolutionCode`, the first-parity table-index model is:

```text
index = x >> resolutionCode
```

For the M10-R descriptor:

```text
resolutionCode = 1
index = x >> 1
```

with a candidate hardware-coordinate domain of:

```text
x = 0 .. 0x4FFF
```

giving exactly 10240 indices.

This model is strongly supported by the helper's copy-size arithmetic and functional behavior. The exact nomenclature of the hardware input coordinate is not yet recovered, so do not call it raw sensor code or final JPEG luma without further evidence.

## 6. First-parity functional formula

For a B2Y tone-coordinate `x`, the calibrated functional model is:

```text
idx  = x >> 1
gain = tone[idx] / 32768.0
y    = x * gain
```

Integer candidate:

```text
y ~= (x * tone[idx]) >> 15
```

or, if hardware rounds rather than truncates:

```text
y ~= (x * tone[idx] + 0x4000) >> 15
```

The exact multiply rounding mode is **not frozen** yet.

Under either candidate arithmetic:

```text
LOW    -> exact identity
MEDIUM -> monotonic contrast S-curve
HIGH   -> monotonic stronger S-curve
```

For truncating arithmetic over the 0x5000 candidate domain:

```text
MEDIUM output-input range: -168 .. +206
HIGH   output-input range: -336 .. +431
```

Both return to unity in the high range.

## 7. Output-limit evidence

The descriptor contains repeated `0x3FFF` values at offsets `+0x78..+0x94`, which the helper programs into B2Y registers around `0x2002086C..0x20020878`.

This is consistent with 14-bit upper-limit/clamp fields and with the differential-gamma output range `0..0x3FFF`.

However, the exact semantic name of each clamp register is not frozen.

## 8. Important caveats

Frozen for functional first parity:
- table values are Q15-style multiplicative gain with unity `0x8000`;
- LOW/MEDIUM/HIGH are increasing contrast-strength curves;
- active resolution code is 1;
- active bank length is 10240 entries / 0xA000 bytes;
- TBL0 and TBL1 are identical in this firmware;
- `x >> 1` is the supported table-index model for the 0x5000 coordinate capacity.

Still open at hardware-cycle precision:
- exact input signal name and normalization feeding tone control;
- exact integer multiply rounding/truncation;
- exact clamp order;
- exact reason for two hardware banks when M10-R calibrates them identically.

These open points should not block first visual-parity rendering.

## 9. Next boundary

For reproducing the default Leica M10-R JPEG look, determine which contrast key is selected by the camera's default JPEG settings and map the upstream contrast parameter to LOW/MEDIUM/HIGH. After that, the core WB/matrix + differential-gamma + tone pipeline is sufficiently specified to build a first offline render oracle.
