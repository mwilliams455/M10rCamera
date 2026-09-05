# M10-R PROJECT HANDOFF v1.25 — B2Y DEFAULT MEDIUM + REPRODUCIBLE ASSETS / STAGE ORDER NEXT

Date: 2026-09-05
Repository: `mwilliams455/M10rCamera`
Current active branch: `m10r-color-science-trace`
Current branch head before this handoff: `746d82b87f2d0e3d3f92332b7437561f5ddc4237`
Latest branch commit before handoff: `research: validate v2.07 B2Y asset extractor`
Firmware: `M10-R-30.22.23.34-Customer.FW`
Firmware SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`
Canonical firmware URL: `https://reddotforum.com/Firmware_files/M10-R/M10-R-30.22.23.34-Customer.FW`
Primary IMG binary: `092_IMG-System.bin`
CA9 binary: `099_IMG-CA9_System.bin`

---

## 1. PROJECT GOAL

Reverse-engineer enough Leica M10-R behavior to build a practical M10-R camera/rendering implementation on the PhotonCamera branch family used by the M9 project.

The target remains:

```text
Xiaomi 15 Ultra main camera
    ↓
M10-R metering / exposure behavior
    ↓
M10-R WB / color-management behavior
    ↓
M10-R B2Y rendered color / tone pipeline
    ↓
high-quality JPEG + DNG
    ↓
PhotonCamera-based sample APK
```

The goal is photographic parity, not a full hardware emulator. Preserve visible image quality. Do not trade away JPEG quality for speed without explicit agreement.

---

## 2. CURRENT CHECKPOINT

The investigation has moved from discovery into implementation preparation.

The most important newly closed result is:

> **Leica M10-R factory/default still contrast is firmware-proven MEDIUM.**

The second major milestone is:

> **The currently recovered B2Y tone and differential-gamma assets can now be extracted deterministically from canonical firmware using `tools/m10r_b2y_assets.py`.**

Therefore asset discovery is no longer the primary blocker.

The immediate unresolved implementation boundary is now:

```text
actual B2Y pixel-stage ordering
+
exact live-domain tone arithmetic / normalization / rounding
```

Do **not** infer pipeline order merely from register-programming order.

---

# 3. DO-NOT-REGRESS CORRECTIONS

These corrections are important because several earlier hypotheses were disproved.

## 3.1 TF remapping is NOT proven to remap ASN

Withdrawn claim:

```text
TF remapping table remaps ASN R/G/B
```

The opcode `0x40` CA9 CM core copies input ASN doubles into local working storage and returns them unchanged at output `+0xB8/+0xC0/+0xC8`.

Therefore:

```text
TF-remap ≠ ASN-remap
```

The TF file format and serialization are exact, but its true semantic consumer is not established as photographic tone/gamma or ASN remapping.

Authoritative freeze/correction:

- `research/M10R_v171_TF_REMAPPING_INERT_ON_PROVEN_PATH_FROZEN.md`

## 3.2 There IS a separate direct RGB gain path

Do not regress to the earlier “no separate direct RGB gain path” interpretation.

The same raw WB gains feed two parallel paths:

```text
raw R/G/B gains
   ├──> direct 11-bit B2Y/front-end gain registers
   └──> clamp [1,2000]
         ↓
       ASN = 256.0 / gain
         ↓
       CA9 color management
         ↓
       rendered CC0 / CC1
         ↓
       B2Y matrix banks
```

Direct gain packing is firmware-proven:

```text
reg 0x2002008C = ((B & 0x7FF) << 16) | (R & 0x7FF)
reg 0x20020090 = ((G & 0x7FF) << 16) | (G & 0x7FF)
```

## 3.3 DNG and rendered matrix layouts are different objects

Do not conflate the DNG logical matrix layout with the rendered CC record.

DNG logical matrix:

```c
struct M10RDngMatrixFixed {
    int32_t coeff[9];
    int32_t denominator;
}; // 0x28
```

Rendered CC record:

```c
struct M10RRenderedCCRecord {
    int32_t coeff[9];
    uint16_t scaleCode;    // +0x24
    uint16_t unknown26;
    int32_t kelvin;        // +0x28
}; // 0x2C
```

Rendered matrix denominator:

```text
1 << (9 - scaleCode)
```

---

# 4. METERING STATUS — CLOSED / FROZEN

Metering remains closed for implementation purposes unless APK testing reveals a genuine missing semantic.

Primary freeze:

- `research/M10R_v118_METERING_BOUNDARY_FROZEN.md`

Key implementation contract:

```text
M10-R statistics block
    root/header
    +0x80 → 22 × 16 statistics payload
```

Geometry:

- 22 horizontal blocks
- 16 vertical blocks
- 352 cells total

Hardware block-count registers:

- `0x2000401C` = 22
- `0x20004018` = 16

The Photon implementation can synthesize the software statistics block and feed the recovered evaluator. Physical Leica Prepro/PW transport does not need to be emulated.

Do not reopen metering while the active blocker is B2Y color/tone.

---

# 5. WB / COLOR-MANAGEMENT FROZEN STATE

## 5.1 DNG CM provenance

DNG CM root:

```text
cm_root = *(source_state + 0x24)
```

Fields:

```text
T1 double  = cm_root + 0x38
CM1        = cm_root + 0x40
T2 double  = cm_root + 0x68
CM2        = cm_root + 0x70
```

Primary freeze:

- `research/M10R_v126_DNG_CM_LAYOUT_FROZEN.md`

## 5.2 Rendered CC0 / CC1

Returned rendered records:

```text
CC0 source +0x28
Kelvin0    +0x50
CC1 source +0x54
Kelvin1    +0x7C
```

Other known fields:

```text
flags       +0x80 / +0x81
tints       +0x84 / +0x9C
white x num +0x86
white x den +0x88
white y num +0x8A
white y den +0x8C
ASN outputs +0xB8 / +0xC0 / +0xC8 as three doubles
```

Primary freeze:

- `research/M10R_v128_RENDERED_CC0_CC1_LAYOUT_FROZEN.md`
- `research/M10R_v132_WB_OUTPUT_FIELDS_FROZEN.md`

## 5.3 CA9 WB/color helpers

Known helpers:

- `Temperature_FromXYCoord` `0x400049E8`
- binary search `0x40004D00`
- `Temperature_ToXYCoord` `0x400051E0`
- `ColorSpec_MapWhiteMatrix` `0x400058B8`
- MatrixInterpolate-related `0x40005C5C / 0x40005D80`
- `ColorSpec_SetWhiteXY` `0x40005E94`
- `ColorSpec_NeutralToXY` `0x400060F0`
- rendered fixed-matrix quantizer `0x400038B0`

Concrete path:

```text
0x40003CD4 -> NeutralToXY
0x40003CF4 -> SetWhiteXY
SetWhiteXY -> MapWhiteMatrix at 0x40005FA8
```

CA9 CM core begins around:

- `0x40003AF4`

## 5.4 WB mode/preset semantics

Top-level selector:

- `[r4 + 0x14]`

14-entry table around:

- `0x4000B178`

Firmware-proven labels only:

```text
top-level mode 3 = Preset mode
preset 1         = Daylight
```

Fallback “set WB to Daylight” writes mode 3 / preset 1.

Do not assign names to other modes/presets without direct firmware proof.

---

# 6. CA9 CM CROSS-CORE TRANSPORT — CLOSED

`ca9_StartColorManagement` builds a nine-word request:

```text
word0 = 0x40
word1 = callback 0x420A3639
word2 = shared block pointer 0x43705760
...
```

The CA9 queue dispatcher at `0x40006320` has exact opcode cases including:

```text
1, 0x10, 0x20, 0x30, 0x40, 0x50, 0x70
```

Opcode `0x40` branch:

- `0x400063B0 -> 0x40004050`

Bridge:

```text
0x40004050:
    ldr r0, [r0,#8]   ; request.word2
    b   0x40003AF4    ; real CA9 CM core
```

This transport boundary should be treated as closed.

---

# 7. OPCODE 0x20 STATIC CONFIG/PRESET PATH

CA9 dispatcher:

```text
opcode 0x20 -> 0x4000B59C
```

`0x4000B59C` performs a configuration/preset calculation transform on a structure at least `0x328` bytes long.

Behavior:

1. source pointer = request `+8`
2. working base = `0x40026F24`
3. copy source `[0x000..0x05B]` to working
4. copy source `+0x2E0`, length `0x48`, to working `+0x2E0`
5. zero working `+0x5C..+0x2DF`
6. call `0x4000B13C(working)`
7. copy computed `+0x5C`, length `0x284`, back to source
8. copy working `+0x2E0`, length `0x48`, back

`0x4000B13C` uses the top-level WB selector and preset dispatch table.

This is a configuration/preset calculation path, not the per-frame opcode `0x40` CM calculation.

---

# 8. B2Y STATIC CONFIG FILES

Known IMG loaders:

- `B2Y_CC0_CA9_CM.bin` loader `0x420A4628`, exact payload `0x84`
- `B2Y_TF_REMAPPING_CA9_CM.bin` loader `0x420A4884`, exact payload `0x100`

Larger config builder:

- `0x420A4AAC`

Shared B2Y baseline destination:

- `0x43705830`

Related config/global:

- `0x43705950`

Static/setup path:

```text
0x420A78EA
  -> 0x420A5DE4
  -> 0x420A4AAC
```

This path is separate from per-frame:

```text
0x420A78C4
  -> ca9_StartColorManagement 0x420A2EB0
```

The `0x420A5DE4` path logs that the color-correction preset was calculated.

---

# 9. TF FILE FORMAT — EXACT FORMAT, LIMITED SEMANTICS

Exact TF file format:

```c
struct M10RTfRemapFile {
    uint32_t enable;
    uint32_t entry_count;   // <= 31
    struct {
        uint32_t x;
        uint32_t y;
    } entry[31];
}; // 0x100
```

Serializer:

```text
config +0x128 = enable != 0
config +0x12C = count
config +0x134..+0x22B = 0xF8-byte pair area
```

Safe statement only:

> This is definitely a B2Y/CA9 CM configuration table of enable/count/31 `(x,y)` pairs.

Do NOT currently call it:

- photographic tone curve
- gamma curve
- ASN remapper

The known opcode `0x40` path does not use it to mutate ASN.

---

# 10. RENDERED MATRIX BANKS — PARALLEL, NOT ALTERNATIVES

`ColorManagementFinished` copies:

```text
CC0 -> 0x408FE130, 0x2C bytes
CC1 -> 0x408FE15C, 0x2C bytes
```

Both programmers `0x42152F8C` and `0x421536BC` program both banks.

CC0 hardware area:

```text
0x20020120
0x20020124
0x20020128
0x2002012C
0x20020130
control/scale bits in 0x20020100
```

CC1 hardware area:

```text
0x200208A0
0x200208A4
0x200208A8
0x200208AC
0x200208B0
scale bits in 0x20020880
```

These are parallel matrix banks, not an either/or selection.

Primary freeze:

- `research/M10R_v185_CA9_RENDERED_CC_TO_B2Y_FROZEN.md`

---

# 11. DIFFERENTIAL GAMMA — ENCODING FROZEN

Primary freeze:

- `research/M10R_v189_DIFFERENTIAL_GAMMA_ENCODING_FROZEN.md`

The calibration data has now been reproducibly converted into an exact expanded curve by the new extractor.

Expanded curve properties from v2.07 validation:

```text
entries = 32768
minimum = 0
maximum = 16383
```

First 32 values:

```text
0, 9, 19, 29, 39, 48, 58, 68,
78, 87, 97, 107, 117, 126, 136, 146,
156, 165, 175, 185, 195, 204, 214, 224,
234, 243, 253, 263, 273, 282, 292, 302
```

The high end saturates at `16383`.

Exact expanded DG SHA256:

```text
9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d
```

---

# 12. TONE TABLE MODEL — FROZEN AS Q15 GAIN TABLES

Primary freeze:

- `research/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md`

Recovered tone assets are 4096-entry Q15 gain tables.

Known profiles:

```text
LOW
MEDIUM
HIGH
```

Important properties from v2.07 validation:

### LOW

```text
sha256 136b69127e73cc43c28c0aa7b511f1f3e9b29be139f4d491422f2eb574a49fb0
min 32768
max 32768
unique 1
```

LOW is therefore unity gain across all 4096 entries.

### MEDIUM

```text
sha256 2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00
min 19431
max 35130
unique 2664
```

### HIGH

```text
sha256 0a764cf29d35cd4a4eb7f816e5d128bccaef81b4d5eca991d9b80ab207bd0101
min 16190
max 37812
unique 4063
```

The remaining implementation question is not table identity. It is the exact live arithmetic:

```text
input-domain normalization
indexing
Q15 multiply
rounding
clamping
interaction/order with other B2Y stages
```

---

# 13. CONTRAST ENUM → TONE SELECTION — CLOSED

Primary freeze:

- `research/M10R_v198_CONTRAST_ENUM_TONE_SELECTION_FROZEN.md`

Exact numeric contrast mapping:

```text
1 = LOW
2 = MEDIUM
3 = HIGH
4 = VIDEOLOW
5 = VIDEOMEDIUM
6 = VIDEOHIGH
```

`0` and values `>=7` route to the error/default-invalid path in the recovered switch logic.

The switch uses the firmware's inline byte-table helper: the byte immediately before LR is the case count, the numeric enum indexes a byte offset table, and the selected branch is `LR + 2*offset`.

This mapping is direct firmware evidence, not inferred from string ordering.

---

# 14. FACTORY/DEFAULT STILL CONTRAST = MEDIUM — NEWLY FROZEN

Primary freeze:

- `research/M10R_v206_DEFAULT_STILL_CONTRAST_MEDIUM_FROZEN.md`

This is the key result from v1.95 through v2.05.

## 14.1 Object field

The B2Y owner path reads contrast directly from:

```text
object + 0xAC
```

## 14.2 Object acquisition

`0x42160D40` does not create the object. It returns an existing full object pointer from:

```text
context + 0x1D50 + 4*slot
```

The slot comes from the low five bits of state and is selected through the 25-entry descriptor subsystem.

## 14.3 Descriptor layout clue

The slot-manager descriptor stride is:

```text
0x12C bytes
```

and:

```text
0x12C * 25 + 4 = 0x1D50
```

So `context+0x1D50` begins immediately after the 25-entry descriptor array and is a companion per-slot object-pointer table.

## 14.4 Proven default initialization

At `0x4216F8E6`, firmware loads numeric value:

```text
2
```

and writes it to:

```text
object +0xA8
object +0xAC
object +0xB0
```

The object is the still-path global object rooted at:

```text
0x408FE188
```

## 14.5 Proven registration

Immediately afterward firmware calls:

- `0x421599A0(object, context)`

At `0x421599E4`, that function stores the exact object pointer into:

```text
context + 0x1D50 + 4*slot
```

This is the same table later read by `0x42160D40`.

Therefore the complete provenance is:

```text
object +0xAC initialized to 2
        ↓
object registered into active slot table
        ↓
0x42160D40 returns that same object
        ↓
B2Y contrast selector reads +0xAC
        ↓
enum 2
        ↓
_CONTRAST:MEDIUM
        ↓
MEDIUM Q15 tone table
```

Conclusion:

> **Factory/default still-photo contrast = MEDIUM is firmware-proven and closed.**

Do not weaken this back to “likely MEDIUM.”

---

# 15. REPRODUCIBLE B2Y ASSET EXTRACTOR — NEW IMPLEMENTATION ARTIFACT

Tool:

- `tools/m10r_b2y_assets.py`

Validation workflow:

- `.github/workflows/m10r-v207-b2y-asset-extractor-validation.yml`

Validation result:

- `research/M10R_v207_b2y_asset_extractor_validation.txt`

Validation run:

- GitHub Actions run `33948595807`
- job `101259040493`
- conclusion `success`

Validation commit / current pre-handoff branch head:

- `746d82b87f2d0e3d3f92332b7437561f5ddc4237`

v2.07 result status:

```text
PASS
```

The extractor emits:

```text
manifest.json
tone_low_q15.u32le
tone_medium_q15.u32le
tone_high_q15.u32le
dg_main_u8.bin
dg_fl_u16le.bin
dg_expanded_u16le.bin
```

Source calibration SHA256:

```text
ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b
```

DG hashes:

```text
dg_main     1678c7f99ab1fac958ffb068d20a0c24ab1677adf20a916335d0b2947fc8a1a1
dg_fl       e1a997633d1be1d82c89feac40f4feccfa058fad4b3d87cadf08d385f83953e6
dg_expanded 9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d
```

This should now be the canonical implementation input rather than repeatedly re-parsing calibration blobs inside ad hoc research scripts.

---

# 16. CURRENT PRACTICAL IMPLEMENTATION MODEL

The renderer can now treat the following as strong/reproducible inputs:

```text
RAW / linear RGB
    ↓
raw WB gain triplet
    ├── direct 11-bit B2Y gain path
    └── ASN = 256/gain
           ↓
       CA9 color management
           ↓
       rendered CC0 / CC1
           ↓
       parallel B2Y matrix banks

plus:

factory still contrast enum = 2
    ↓
MEDIUM Q15 tone table

plus:

exact differential-gamma calibration
    ↓
32768-entry expanded DG transfer curve
```

What is **not** yet safe is to impose a final pixel-processing order among these recovered stages.

---

# 17. ACTIVE UNRESOLVED QUESTION — TRUE B2Y PIXEL-STAGE ORDER

This is the next investigation.

Need to distinguish:

```text
register programming sequence
```

from:

```text
actual hardware pixel dataflow sequence
```

Do not assume that because firmware writes one block first, pixels flow through it first.

The specific order that must be resolved includes at least:

- direct R/G/B gain block
- rendered CC0 / CC1 matrix banks
- differential gamma
- tone/Q15 gain stage
- any de-knee/gamma stage already identified in v1.75/v1.76 traces
- B2Y RGB→Y/YCbCr conversion / output mapping

The recovered LINK/routing registers and block-enable/control bits are the preferred evidence source.

---

# 18. EXACT NEXT RESEARCH ACTION — v2.08

Do this first in the next chat.

## 18.1 Re-open existing B2Y routing/programmer evidence before writing a new broad scan

Prioritize these existing artifacts:

- `research/M10R_v172_b2y_live_data_plane.txt`
- `research/M10R_v173_b2y_programmer_context.txt`
- `research/M10R_v173b_b2y_context_fast.txt`
- `research/M10R_v175_b2y_selector_gamma_deknee.txt`
- `research/M10R_v176_b2y_tone_gamma_apply.txt`
- `research/M10R_v176b_arm_deknee_tone.txt`
- `research/M10R_v186_differential_gamma_hardware_abi.txt`
- `research/M10R_v186b_dg_control_exact.txt`
- `research/M10R_v190_tone_hardware_abi.txt`

Search specifically for:

```text
LINK
link
route
routing
select
source
input
output
bypass
enable
0x20020xxx control registers
```

Goal: recover actual block interconnect or selector semantics, not merely function call order.

## 18.2 If existing traces are insufficient, create a bounded v2.08 workflow

Suggested workflow name:

```text
.github/workflows/m10r-v208-b2y-stage-order-routing.yml
```

Suggested result:

```text
research/M10R_v208_b2y_stage_order_routing.txt
```

Keep it narrow. Do NOT perform another whole-IMG Capstone scan.

Recommended targets:

1. the known B2Y programmer routines around `0x42152F8C` and `0x421536BC`;
2. DG programmer/control paths from v1.86;
3. tone programmer/control paths from v1.90;
4. any shared `0x20020xxx` control registers touched by more than one stage;
5. explicit mux/source/link fields.

Output should include:

- exact MMIO address
- writer instruction
- written bit mask/value
- nearby branch/state condition
- inferred block edge only when bit semantics are directly supported

## 18.3 Freeze stage order only if evidence is direct

If routing bits expose a concrete graph, create:

```text
research/M10R_v209_B2Y_STAGE_ORDER_FROZEN.md
```

If not, leave ordering partially unresolved and implement the renderer with explicit stage-order switches for testing rather than silently choosing one.

---

# 19. SECOND NEXT ACTION — EXACT TONE ARITHMETIC

Once stage order is constrained, trace exact tone arithmetic.

Need to establish:

```text
live sample bit depth / domain
4096-table index derivation
Q15 multiply expression
rounding bias
right shift amount
saturation/clamp behavior
whether index is taken pre- or post-DG / matrix
```

The table itself is no longer uncertain.

A useful implementation test should compare candidate integer formulas against firmware register/table geometry and known unity behavior of LOW (`32768 == 1.0 Q15`).

Do not use floating-point approximations as the canonical model until integer firmware behavior is resolved.

---

# 20. THIRD NEXT ACTION — OFFLINE FIRST-PARITY RENDERER

After stage order and tone arithmetic are sufficiently constrained, build the first offline M10-R parity renderer using the extracted assets.

Minimum first version should use:

- canonical MEDIUM tone table
- exact expanded DG curve
- dual WB path model
- rendered CC matrix ABI
- DNG CM calibration where relevant
- no invented local HDR / highlight recovery
- no generic phone-camera tone lift

The first renderer should be diagnostic and switchable so stage-order candidates can be compared without changing assets.

Only after offline behavior is stable should it move into PhotonCamera live JPEG rendering.

---

# 21. IMPORTANT WORKFLOW / ACTIONS OPERATING RULES

Keep these operational lessons from the investigation:

1. Avoid broad whole-image Capstone scans. They repeatedly hit the Actions runner shutdown/time ceiling.
2. Prefer bounded disassembly and literal-reference provenance.
3. Capstone SKIPDATA pseudo-instructions can throw `CS_ERR_DETAIL` if `.operands` is accessed. Use a safe `ops(i)` helper / ignore data pseudo-instructions.
4. Do not push another workflow while a previous pushed workflow is still running unless cancellation is acceptable; newer pushes can cancel older runs.
5. One narrow pushed workflow at a time is the preferred pattern.
6. Preserve exact proven vs inferred labels in research notes.

---

# 22. KEY CURRENT FILES

Frozen/reference notes:

- `research/M10R_v118_METERING_BOUNDARY_FROZEN.md`
- `research/M10R_v126_DNG_CM_LAYOUT_FROZEN.md`
- `research/M10R_v128_RENDERED_CC0_CC1_LAYOUT_FROZEN.md`
- `research/M10R_v132_WB_OUTPUT_FIELDS_FROZEN.md`
- `research/M10R_v145_WB_ASN_B2Y_BASELINE_FROZEN.md` — useful but partially superseded by later dual-path/ASN corrections
- `research/M10R_v171_TF_REMAPPING_INERT_ON_PROVEN_PATH_FROZEN.md`
- `research/M10R_v185_CA9_RENDERED_CC_TO_B2Y_FROZEN.md`
- `research/M10R_v189_DIFFERENTIAL_GAMMA_ENCODING_FROZEN.md`
- `research/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md`
- `research/M10R_v198_CONTRAST_ENUM_TONE_SELECTION_FROZEN.md`
- `research/M10R_v206_DEFAULT_STILL_CONTRAST_MEDIUM_FROZEN.md`

Latest implementation artifact:

- `tools/m10r_b2y_assets.py`

Latest validation:

- `.github/workflows/m10r-v207-b2y-asset-extractor-validation.yml`
- `research/M10R_v207_b2y_asset_extractor_validation.txt`

Latest Actions validation:

- run `33948595807`
- job `101259040493`
- success

---

# 23. CONCISE STATE FOR NEXT CHAT

If only one paragraph is read, use this:

> M10-R metering is frozen. WB/color management is substantially mapped, including the proven dual WB path: raw gains feed direct 11-bit B2Y gain registers and also ASN=`256/gain` into CA9 CM, which produces rendered CC0/CC1 parallel matrix banks. The old TF→ASN-remap interpretation is withdrawn; TF semantics remain limited. Differential-gamma encoding is frozen and the exact 32768-entry expanded curve is reproducibly extractable. Tone tables are proven 4096-entry Q15 gain tables. Contrast enum mapping is exact: 1 LOW, 2 MEDIUM, 3 HIGH, 4–6 video variants. The factory/default still object at `0x408FE188` is initialized with `+0xAC=2`, registered into the same `context+0x1D50+4*slot` table consumed by B2Y, so **default still contrast = MEDIUM is firmware-proven**. `tools/m10r_b2y_assets.py` plus v2.07 validation now provide deterministic tone/DG assets. The immediate next task is **true B2Y pixel-stage ordering**, using existing routing/LINK/control evidence first and a bounded v2.08 routing workflow only if needed; after that resolve exact integer tone arithmetic and build the first offline parity renderer.

---

# 24. DO NOT DO NEXT

Do not:

- reopen metering;
- claim TF remaps ASN;
- claim TF is tone/gamma;
- remove the direct WB hardware gain path;
- describe default still contrast as merely “likely MEDIUM”;
- replace recovered Leica tone/DG assets with fitted curves;
- assume register-write order equals pixel-stage order;
- run another unconstrained whole-IMG disassembly scan;
- move straight to a live APK before the B2Y stage-order / integer arithmetic boundary is sufficiently understood.

---

# 25. RECOMMENDED FIRST PROMPT IN NEXT CHAT

```text
Continue the M10-R investigation from this handoff. Start by opening the existing v172/v173/v175/v176/v186/v190 B2Y traces and determine whether LINK/routing/control registers prove the actual pixel-stage ordering among direct WB gains, CC0/CC1, differential gamma, tone, and B2Y output conversion. Do not infer stage order from register-programming order. If the existing traces are insufficient, create only a bounded v2.08 B2Y stage-order routing workflow.
```
