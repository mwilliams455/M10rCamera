# M10-R Y_BLEND BIT15 AUDIT1A — 20 September 2026

## Result

The previously conflated register banks have different owners. The v2.77 handoff's purported correction of Y_BLEND versus WBCLIPLEVEL was itself wrong. Original firmware references prove:

- record 0x0C / D4570 = YC CONVERSION;
- record 0x0D / D4480 = Y BLEND;
- record 0x04 / D42E0 = WBCLIPLEVEL.

The original Thumb programmers passed 10,240 emulated execution checks. Across 61,440 paired-register writes, bit 15 never changed. This verifies software register programming, not imaging-hardware pixel arithmetic.

Gate-C remains unpassed. No renderer/capture changes or new photographic equation are justified by these results.

## Scope and provenance

Repository: mwilliams455/M10rCamera. Isolated branch: m10r-yblend-bit15-audit1a.
Research base: 12e44a4593688289779e2617b282d811181fd8b9.
Audit script commit: 2ea6c0d197b2905410c511606a8cb279e9aa1468.
CI-tested commit: d07ac49550ea92c07880e55983a797fdcefa0366.
CI run: 35496254874, SUCCESS on 20 September 2026.
CI artifact: 10600419812, M10R-YBLEND-BIT15-AUDIT1A-RESULTS.
Artifact SHA256: 9fa6475a1304753a7cbcb499f312cc1987aa6dd2e1bb05ef0a1102905b287571.
Downloaded CI results match the local results exactly; the exact committed script was also rerun locally with identical output.

Frozen photographic baseline remains RENDER1Q + CC1MAP1A + YBLEND1B k=0.35 on m10r-render1q-yblend1b-k035 (recorded SHA a66b73cc339ebcb863d345c7a9ee7ff631fc86f0). Capture branch m10r-capture1b remains untouched (recorded SHA 3b1e86b5055a21b548d56b23bd47f9dc66c57012). The k=0.35 path remains a photographic approximation, not recovered Y BLEND semantics.

## 1. Direct selector identities

Code addresses are raw offsets in IMG-System, NOT virtual addresses. Each guard resolves the actual Thumb ADR string, checks the immediate record ID in r1, checks the lookup BL to 0x1A0FC4, and checks the driver BL. This is not nearest-string labeling.

| Own firmware label | Selector | Record | Driver | MMIO destinations |
|---|---|---|---|---|
| WBCLIPLEVEL | 0x154D5C | 0x04 | 0xD42E0 | 0x20020094/98 |
| Y BLEND | 0x154E18 | 0x0D | 0xD4480 | 0x2002092C/30/34 |
| YC CONVERSION | 0x154ECC | 0x0C | 0xD4570 | matrix 0x20020900..10; pairs 0x20020920/24/28 |
| POST PROCESSING FILTER | 0x15486C | 0x17 | 0xD34F0 | 0x200210C4/C8/CC |

| Label | ADR -> actual string | Lookup call | Driver call |
|---|---|---|---|
| WBCLIPLEVEL | 0x154D82 -> 0x154DBC | 0x154D90 | 0x154DAC -> 0xD42E0 |
| Y BLEND | 0x154E3E -> 0x154E78 | 0x154E4C | 0x154E68 -> 0xD4480 |
| YC CONVERSION | 0x154EF2 -> 0x154F2C | 0x154F00 | 0x154F1C -> 0xD4570 |
| POST PROCESSING FILTER | 0x154894 -> 0x1548CC | 0x1548A2 | 0x1548BE -> 0xD34F0 |

These bindings agree with research/M10R_v094_b2y_selector_inventory.txt on the research base. They supersede the conflicting naming claims in sections 3, 5, 8 and 25 of the uploaded M10R PROJECT HANDOFF v2.77. They do not authorize modifying the frozen renderer.

## 2. Bank reconciliation

### Old 0x20021080 bank: PostFilter

Base 0x20021080 plus offsets 0x44/48/4C reaches 0x200210C4/C8/CC. Its selector explicitly uses record 0x17, POST PROCESSING FILTER. Original driver offset is 0xD34F0; the older v061 virtual address 0x420D34EC used map bias 0x41FFFFFC. Its fallback sets both selected fields of each pair to 0x3FFF, preserving bit 15.

The broad v062 0x3FFF scan also contains shutter-controller functions. Such constant hits are not a B2Y bridge.

### 0x2002078C/90/94: Multi_Axis computed-base connection

SAM7 function 0x4FEDE has its own Im_B2Y_Ctrl_Multi_Axis diagnostic reference at 0x503FC. At 0x50338 it loads r0 from pool 0x505C8, whose value is 0x20020720. At 0x5033A it adds 0x60, producing 0x20020780. Stores at offsets +0x0C/+0x10/+0x14 therefore reach 0x2002078C/90/94.

Parameters are halfwords at structure +0x1C0/+0x1C2, +0x1C4/+0x1C6, +0x1C8/+0x1CA. An exact-literal search for 0x20020780 misses this owner.

The same function programs bit 0 at 0x20020400 from the low bit of its first argument. IMG central setup clears that bit and the separately audited slice 0x155000..0x155052 sets each selected pair to (old & 0x8000) | 0x00003FFF. Later it independently calls YC CONVERSION at 0x15508A and Y BLEND at 0x155094. Configuration order does not establish pixel-processing order.

## 3. Exact register programming

For all examined paired-word writes:

```python
new = (old & 0x00008000) | (low & 0x00007FFF) | ((high & 0xFFFF) << 16)
```

The code uses separate low15 and high16 read-modify-write stores. Bit 15 survives every intermediate write. The pattern occurs in YC CONVERSION, Y BLEND, PostFilter and Multi_Axis, so it is not a unique Y BLEND mechanism.

The assertion that some other software path MUST own bit 15 is withdrawn. Preservation establishes only that these routines leave it alone. Reserved-bit handling, hardware reset state, an unobserved writer and other meanings remain possible. Do not infer an enable flag, signed endpoint ordering or clipping equation.

### Actual Y BLEND controls

D4480 programs record 0x0D as:

```python
reg_2092c = (old_2092c & ~0x00003F3F) | (p0 & 63) | ((p1 & 63) << 8)
reg_20930 = pair(old_20930, p2, p3)
reg_20934 = pair(old_20934, p4, p5)
```

Retained v086 calibration evidence records normal payload [0,32,0x3FFF,0x3FFF,0x3FFF,0x3FFF]. Thus the normal six-bit fields contribute 0x2000 while unrelated bits remain preserved.

Fallback clears BOTH six-bit controls to zero (stores 0xD4514 and 0xD4522), then programs low 0x7FFF/high 0x8000 for both pairs, preserving bit 15. Normal controls (0,32) must not be substituted for fallback (0,0).

The normal payload is sourced from research/M10R_v086_ycc_calib_compact.txt; this audit re-executed the original programmers but did not independently re-extract the main B2Y calibration payload. The value 32 does not establish a denominator, unity weight, source signal or relationship to the photographic k=0.35.

## 4. SAM7 compact ABI

The complete SAM7 function 0x51DA6 has its own Im_B2Y_Ctrl_Yc_Convert diagnostic at 0x51F0C. Its 40-byte structure is <15H2B4H>: nine YC coefficients plus six YC paired-field halfwords, two Y BLEND control bytes, then four Y BLEND paired-field halfwords.

Executing this original function agrees with the combined IMG YC CONVERSION + Y BLEND packing model for 1,024 parameter sets. Original SAM7 PostFilter 0x522D8 likewise agrees with the IMG PostFilter model.

Do not describe all neighboring DG/WB functions as part of this one adaptive initializer. The bounded function programs these combined controls; no per-pixel mixing equation is established.

## 5. Executed validation

Tool: tools/m10r_yblend_bit15_audit1a.py. Capstone 5.0.3 and Unicorn 2.1.3; ARM Thumb; RAM-backed MMIO. Section hashes and selector identities are asserted. Python -O is rejected. Seed 0xB2152026 generates 1,024 deterministic register/parameter sets, including seven YC boundary patterns and randomized register state.

| Check | Executions |
|---|---:|
| Original IMG YC CONVERSION/Y BLEND/PostFilter, normal and fallback | 6144 |
| Original SAM7 YC/Y BLEND and PostFilter cross-core checks | 2048 |
| Original bounded IMG central initialization slice | 1024 |
| Complete original SAM7 Multi_Axis, selected three pairs | 1024 |
| Total | 10240 |

All assertions passed. Observed paired-register writes: 61440. Bit15 mutations: 0. Distinct paired-register write sites: 60 (38 IMG, 22 SAM7).

IMG and cross-core checks compare the entire modeled 0x4000-byte register window. Multi_Axis assertions cover only its three selected pairs, not its full ABI. Only SAM7 clock-management helpers 0x4D1B4/0x4D118 are stubbed; the actual Multi_Axis table-copy helper executes.

This does NOT simulate sensor, ISP, hardware reset side effects, clock gating or photographic parity.

## 6. Bounded scan and unresolved semantics

A mixed Thumb/ARM literal-seeded propagation scan examined 1164 B2Y pointer candidates and found 66 distinct stores to watched registers: the 60 paired-word sites plus six stores to the six-bit control word. No independent bit15-changing writer or software per-pixel consumer was established.

This is NOT a completeness proof: three SAM7 seed traversals hit a 2000-state limit; other paths stopped on provenance loss, range limits or returns. Arbitrary indirect copying, other pointer constructions, other firmware sections and hardware side effects remain outside the result.

Next semantics target is actual record 0x0D / D4480 / 0x2002092C/30/34. Keep YC CONVERSION, Multi_Axis and PostFilter distinct. A candidate must explain both six-bit fields, both paired words and normal/fallback differences. Source signals, arithmetic scaling, rounding, clipping and internal pixel-processing order are not closed. Image-coordinate distributions may test candidates but cannot alone prove an ASIC equation.

## 7. Reproduction and hashes

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_bit15_audit1a.py /path/to/sections --cases 1024 --out results.json
```

Firmware M10-R-30.22.23.34-Customer.FW SHA256:
ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498

Unpacked SHA256:
859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0

092_IMG-System.bin SHA256:
53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4

100_IMG-SAM7.bin SHA256:
c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae

The isolated CI workflow verifies original and unpacked hashes before extraction and executes the same audit. Firmware binaries are not committed.
