# M10-R Y_BLEND D4480 PRODUCER1A — NORMAL FIELD PRODUCER PROVENANCE

Date: 2026-09-25

Repository: `mwilliams455/M10rCamera`

Research branch: `m10r-yblend-d4480-producer1a`

Successful validation run: `36174030540`

Validated source commit: `8ad49c0664f28195e4f973bc5bcba440614c439c`

## Scope

This research pass closes a software-provenance gap around the actual M10-R Y BLEND control.

It does **not** recover ISP pixel arithmetic and does not claim photographic parity.

No renderer, exposure, WB, MFM, JPEG, tone, or production/capture code is modified by this branch.

## Independently re-extracted normal record 0x0D

Verified firmware:
- firmware SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`
- decoded firmware SHA256: `859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0`
- IMG-System SHA256: `53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4`
- B2Y calibration SHA256: `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b`

Record 0x0D:
- count: 1
- record index: 146
- payload offset: `0x131874`
- payload size: 24 bytes
- payload SHA256: `cab40e527bfbe6b8a5cd0450a668f46d5d6569ee8405e89fdf7e1455f1492b50`
- raw bytes: `0000000020000000ff3f0000ff3f0000ff3f0000ff3f0000`
- little-endian U32 values: `[0, 32, 16383, 16383, 16383, 16383]`

The retained v086 extractor independently reproduced the same record and the SAM7 compact layout:
- compact U8 at +0x1E/+0x1F = `0,32`
- compact halfwords at +0x20/+0x22/+0x24/+0x26 = `0x3FFF,0x3FFF,0x3FFF,0x3FFF`

## Selector dataflow is now source-anchored

Sequential Thumb decoding of IMG selector `0x154E18` proves:

- `0x154E20: movs r6,#0`
- `0x154E48: movs r1,#0x0D`
- `0x154E4C: bl 0x1A0FC4` — calibration record lookup
- `0x154E50: movs r4,r0` — preserve lookup-returned record pointer
- on lookup failure, `r6` becomes 1
- `0x154E64: movs r1,r6` — fallback flag
- `0x154E66: movs r0,r4` — same record pointer
- `0x154E68: bl 0xD4480` — Y BLEND register programmer

No write to `r4` occurs between preservation of the lookup result and passing it into D4480.

Therefore, on the normal path, the selector does **not** synthesize or transform the six Y BLEND fields. The calibration-record pointer is passed directly into D4480.

On lookup failure, the selector passes the fallback flag and D4480 substitutes its internal fallback constants.

A direct Thumb-BL encoding census found the canonical `0x154E68 -> 0xD4480` site. This is a direct-call census only; it does not exclude indirect calls elsewhere.

## Original D4480 executed with exact record

Using the original IMG-System Thumb instructions under Unicorn with RAM-backed MMIO:

Normal record 0x0D writes:
- `0x2002092C = 0x00002000`
- `0x20020930 = 0x3FFF3FFF`
- `0x20020934 = 0x3FFF3FFF`

Fallback writes:
- `0x2002092C = 0x00000000`
- `0x20020930 = 0x80007FFF`
- `0x20020934 = 0x80007FFF`

No bit-15 mutation was observed in the paired-register RMW path.

## Independent field-influence test

One-field perturbations through the **original D4480 code** establish:

- p0 -> six-bit low field of `0x2002092C`
- p1 -> six-bit field at bits 8..13 of `0x2002092C`
- p2/p3 -> low/high halves of `0x20020930`
- p4/p5 -> low/high halves of `0x20020934`

Each perturbed field changed only its expected destination register.

## New constraint

The normal Y BLEND configuration is a direct, fixed calibration payload on the tested still path.

The selector itself is not where a scene-dependent or tone-dependent blend coefficient is calculated.

That narrows the remaining problem: the unresolved semantics are downstream in the hardware interpretation of the programmed fields, not a missing software calculation between B2Y record lookup and D4480.

## Still unresolved

Do **not** infer the following from the numeric values alone:

- what two pixel-domain quantities Y BLEND combines;
- whether p1=32 means 0.5 in any fixed-point domain;
- whether the paired 0x3FFF values are min/max, thresholds, scales, clamps, or something else;
- the hardware denominator, sign interpretation, rounding, clipping, or stage order;
- exact per-pixel Y BLEND arithmetic.

The v2.78 discipline remains correct: do not promote another arbitrary global k as firmware truth.

## Next research

Continue from the hardware-facing side:

1. Find any additional producer/alias path for `0x2002092C/30/34`, including indirect/computed-address writes.
2. Trace the SAM7 YCC control structure users beyond the programmer to look for semantic field names or mode-dependent construction.
3. Search firmware/calibration metadata for alternate record-0x0D payloads or mode variants with discriminating values.
4. Use any discovered alternate values to constrain the hardware function before changing the photographic renderer.

## Validation

Successful Actions run `36174030540` passed all assertions.

Artifact from the earlier equivalent successful run `36173893128`:
`M10R-YBLEND-D4480-PRODUCER1A-RESULTS`, artifact ID `10880974526`.

The faster direct-BL census implementation in the current branch reproduces the same constraints.
