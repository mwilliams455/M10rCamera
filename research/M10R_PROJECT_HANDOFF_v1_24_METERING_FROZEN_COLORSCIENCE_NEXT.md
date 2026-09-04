# M10-R PROJECT HANDOFF v1.24 — METERING FROZEN / COLOR SCIENCE NEXT

Date: 2026-09-04
Repository: `mwilliams455/M10rCamera`
Current active branch: `m10r-color-science-trace`
Current branch head before this handoff: `fdb90c3c3ab04d7edf312e5adec771e9c9db0eb1`
Firmware: `M10-R-30.22.23.34-Customer.FW`
Firmware SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`
Primary IMG binary: `092_IMG-System.bin`
CA9 binary: `099_IMG-CA9_System.bin`

---

## 1. PROJECT GOAL

Reverse-engineer enough Leica M10-R firmware behavior to build a working M10-R-inspired camera implementation on the same PhotonCamera branch family used by the M9 project.

The intended implementation target is deliberately practical rather than a complete hardware emulator:

```text
Xiaomi 15 Ultra main camera
    ↓
M10-R metering / exposure behavior
    ↓
M10-R RAW / DNG color calibration
    ↓
M10-R rendered color / tone pipeline
    ↓
high-quality JPEG + DNG
    ↓
PhotonCamera-based sample APK
```

The long-term architecture should share Photon infrastructure with the M9 project while keeping M10-R photographic behavior separate.

---

# 2. METERING STATUS — IMPLEMENTATION BOUNDARY FROZEN

The metering investigation should now be treated as CLOSED for implementation purposes unless APK testing exposes a genuinely missing semantic.

Authoritative freeze document:

- `research/M10R_v118_METERING_BOUNDARY_FROZEN.md`

## 2.1 Frozen geometry

AFAEAWB / CA9 metering geometry is:

- 22 horizontal blocks
- 16 vertical blocks
- 352 total metering cells

The same geometry is independently present in:

1. the named AFAEAWB mode object;
2. live Prepro AEAWB window configuration;
3. hardware block-count MMIO;
4. the CA9 `row * 22 + col` indexing logic.

Hardware mapping:

- `0x2000401C` = horizontal AEAWB block count = 22
- `0x20004018` = vertical AEAWB block count = 16

## 2.2 Producer data-plane identity

AFAEAWB allocation is owned through the Prepro subsystem.

Prepro write channel 6 is programmed with:

```text
PWSA = AFAEAWB allocation base + 0x80
```

The setter is `drv_prepro_driver_pwch_setPWSA` at `0x420E0850`.

Therefore the hardware AEAWB statistics payload destination is provably `producer-root + 0x80`.

## 2.3 PW channel 6 completion

Successful PW channel 6 completion reaches:

- `drv_prepro_manager_PWChannelInterrupt` at `0x420E607C`

The interrupt distinguishes channel 6 and error state.

A debug/optional callback path through `0x420DAADC` can pass exact `base+0x80`, but normal production AFAEAWB configuration leaves those optional callbacks NULL. Production synchronization instead uses aggregate PW completion / frame lifecycle state.

Do not reopen the debug callback path as if it were the normal data bridge.

## 2.4 CA9 consumer contract

The CA9 workflow object is persisted at `0x408187EC` and passed to the image-processing parameter builder.

For the relevant image-processing mode, CA9 selects:

```text
workflow + 0x480
```

The object referenced there is treated as a statistics-block ROOT, not a pointer directly to cell bytes.

CA9 then accesses the actual statistics payload at:

```text
statistics-block root + 0x80
```

This mirrors the Prepro producer payload convention exactly.

## 2.5 Frozen implementation ABI

The software implementation may therefore reproduce the Leica metering contract as:

```text
M10-R statistics block
    root/header
    +0x80 → 22 × 16 statistics payload
```

It is NOT necessary to emulate Leica's physical Prepro/PW channel hardware transport in PhotonCamera.

The APK can generate a software 22×16 statistics object and feed the recovered CA9-equivalent evaluator.

## 2.6 Explicitly unresolved but no longer blocking

Still not proved:

```text
workflow+0x480 == physical Prepro allocation base
```

The exact dynamically linked / cross-module assignment of the runtime pointer was not recovered.

This MUST remain labelled unresolved. Do not silently promote it to fact.

It is no longer blocking because the producer and consumer independently expose the same root/+0x80 ABI.

---

# 3. IMPORTANT PWLSIZE CORRECTION

Do NOT reuse the old `7040 / 352 = 20 bytes/cell` idea.

Correct ARM-mode decoding showed:

- mode `0x11` writes `0x408F0410 = 7040`
- PW channel 6 takes the ordinary `pw_init` branch
- ordinary branch doubles descriptor `+8`
- resulting `PWLSIZE = 14080`

The earlier 20-byte/cell and 40-byte/cell interpretations were false leads.

Neither value is frozen as a per-cell statistics record size.

---

# 4. BRANCH SPLIT

The metering research checkpoint remains on:

- `m10r-metering-latch-trace`

The active color-science work is now on:

- `m10r-color-science-trace`

The color branch was created from the post-metering state so metering closure can remain stable.

---

# 5. COLOR SCIENCE — CURRENT STATUS

Color-science investigation has begun and is now the primary research track.

Key firmware architecture already recovered:

```text
DNG ColorMatrix1 / ColorMatrix2
        ↓
illuminant / Kelvin handling
        ↓
3×3 matrix interpolation
        ↓
WB / color correction matrices
        ↓
B2Y color processing
        ↓
gamma
        ↓
tone-control tables
        ↓
JPEG/output color space
```

This is important: the M10-R firmware clearly contains a staged color pipeline. The goal should be to reproduce those stages, not fit one giant visual LUT.

---

# 6. v1.20 — IMG COLOR MANAGEMENT PARAMETER BLOCK

Artifact:

- `research/M10R_v120_color_management_parameter_map.txt`

Workflow:

- `.github/workflows/m10r-v120-color-management-parameter-map.yml`

Bot result commit:

- `4b354032350b1f2bee095c030a5585089e1267ae`

Main function:

- `ca9_cm_fill_parameter` at `0x420A591C`

Helper:

- `0x420A5F1C`

Important correction:

`0x420A5F1C` is NOT a Leica look/profile selector. It clears / initializes a `0xD0`-byte color-management parameter block rooted at:

```text
0x43705760
```

`ca9_cm_fill_parameter` then populates that block.

Three signed workflow fields are clamped to `1..2000`:

- workflow `+0xF4`
- workflow `+0xF6`
- workflow `+0xF8`

They are converted to double precision and stored at color-management block:

- `+0x08`
- `+0x10`
- `+0x18`

An optional override path can replace those values from:

```text
0x408F0E48
```

Further parameter fields include mode/state bytes and a pointer at block `+0x24`.

Do not yet assign photographic semantics to `+0xF4/+0xF6/+0xF8`; they are known scalar inputs but not yet named.

---

# 7. COLOR-MANAGEMENT STRING / FUNCTION SURVEY

The firmware exposes named CA9 color functions including:

- `get_kelvin_table_count`
- `ca9_cm_Temperature_FromXYCoord`
- `ca9_cm_Temperature_FromXYCoord_binarySearch`
- `ca9_cm_Temperature_ToXYCoord`
- `ca9_cm_ColorSpec_MapWhiteMatrix`
- `ca9_cm_ColorSpec_SetWhiteXY`
- `ca9_cm_ColorSpec_NeutralToXY`
- `ca9_cm_ColorSpec_MatrixInterpolate`

The IMG firmware also logs:

- DNG CM1 rows 0..2
- DNG CM2 rows 0..2
- Color Temperature CM1
- input color space
- output CC0 default-data flag
- output CC0 temperature / tint
- output CC0 matrix rows
- output CC1 default-data flag
- output CC1 temperature / tint
- output CC1 matrix rows
- `Color Management finished`

The B2Y subsystem exposes separate APIs for:

- WB gain
- CC matrices
- gamma
- RGB→YC matrix
- YC→RGB matrix
- tone-control table
- chroma suppression / color NR

Embedded output profile data includes at least:

- Adobe RGB (1998)
- sRGB IEC61966-2.1
- eciRGB v2

This strongly supports keeping RAW/DNG calibration separate from rendered JPEG/output-space processing.

---

# 8. v1.21 — KELVIN / MATRIX CORE

Artifact:

- `research/M10R_v121_dng_matrix_kelvin_core.txt`

Workflow:

- `.github/workflows/m10r-v121-dng-matrix-kelvin-core.yml`

The CA9 `MatrixInterpolate` path is now understood at algorithm level.

It interpolates in reciprocal color temperature rather than directly in Kelvin.

Equivalent form:

```text
w = (1/T - 1/T1) / (1/T2 - 1/T1)
M(T) = (1-w) * M1 + w * M2
```

Supporting matrix routines were decoded as ordinary 3×3 double-precision operations:

- scalar × 3×3 matrix
- add two 3×3 matrices

This is strong evidence of a dual-illuminant camera-calibration path and is directly implementable in an offline oracle.

---

# 9. ROBERTSON CCT TABLE — NOT LEICA-SPECIFIC COLOR

The table at `0x40013D48` was initially interesting because it is used by Kelvin/xy routines.

It decodes as records such as:

```text
0   0.18006  0.26352  -0.24341
10  0.18066  0.26589  -0.25479
20  0.18133  0.26846  -0.26876
30  0.18208  0.27119  -0.28539
40  0.18293  0.27407  -0.30470
...
```

This is characteristic of the Robertson correlated-color-temperature / isotemperature lookup table.

Therefore:

- it is useful to reproduce the Kelvin/xy math;
- it is NOT the Leica-specific M10-R color matrix calibration.

Do not waste time treating `0x40013D48` as the Leica look.

---

# 10. v1.22 — DNG CM PROVENANCE

Artifact:

- `research/M10R_v122_dng_cm_provenance.txt`

Workflow:

- `.github/workflows/m10r-v122-dng-cm-provenance.yml`

This trace established that DNG CM1/CM2 diagnostics and the CA9 command/callback path live around the IMG-side color-management wrapper.

The DNG matrices are not mere strings: the callback converts integer matrix terms into floating point for row-by-row diagnostics.

The DNG path must remain separate from rendered CC0/CC1.

Open question from v1.22:

- are CM1/CM2 fixed firmware tables, sensor-calibration / OTP supplied values, or workflow-owned metadata?

That provenance is still not frozen.

---

# 11. v1.23 — COLOR MANAGEMENT FINISHED / DNG LAYOUT

Artifact:

- `research/M10R_v123_color_finished_dng_layout.txt`

Workflow:

- `.github/workflows/m10r-v123-color-finished-dng-layout.yml`

Known callback:

- `ca9_cm_ColorManagementFinished` implementation wrapper at `0x420A3638` / Thumb entry `0x420A3639`

Important structure observations:

The callback handles two DNG matrix regions and two adjacent temperature values.

Observed result-root layout:

```text
result-root +0x38/+0x3C : first temperature as double
result-root +0x40       : first DNG matrix region

result-root +0x68/+0x6C : second temperature as double
result-root +0x70       : second DNG matrix region
```

The firmware prints all three rows of both DNG matrices.

The diagnostic string `Color Temperature CM1` appears to be reused for both first and second temperature prints. Treat that as a Leica debug-string typo, not proof that only one temperature exists.

## 11.1 Likely matrix record format

The 0x2C-byte record is strongly consistent with:

```text
+0x00 .. +0x20 : 9 signed 32-bit matrix numerators
+0x24          : scale / denominator field
+0x28          : additional final word, semantics NOT YET FROZEN
```

Each matrix element is converted using the common denominator/scale before diagnostic output.

Do NOT freeze a final C struct until `+0x28` semantics and copy direction are confirmed.

## 11.2 Important memcpy-direction correction

Before this handoff, a directionality issue was caught around helper `0x4204F2EC`.

The helper appears to follow ordinary ARM `memcpy(dest, src, size)` calling convention at other firmware sites.

Therefore the v1.23 callback may be SERIALIZING already-existing color-management state outward rather than copying returned CA9 data inward.

This must be resolved before declaring exact ownership/provenance of CM1/CM2.

This is the FIRST NEXT TASK.

---

# 12. v1.24 — RENDERED CC0 / CC1 LAYOUT

Artifact:

- `research/M10R_v124_rendered_cc0_cc1_layout.txt`

Workflow:

- `.github/workflows/m10r-v124-rendered-cc0-cc1-layout.yml`

Bot result commit / current pre-handoff branch head:

- `fdb90c3c3ab04d7edf312e5adec771e9c9db0eb1`

The trace successfully captured the rendered-color output region.

Known diagnostics include:

- `[out] Gain remapped R/G/B`
- `[out] CC0 default data`
- `[out] CC0 T[K], Tint`
- CC0 matrix rows
- `[out] CC1 default data`
- `[out] CC1 T[K], Tint`
- CC1 matrix rows

The branch clearly has two rendered color-correction endpoints, CC0 and CC1, distinct from DNG CM1/CM2.

The v1.24 artifact is not fully semantically decoded yet.

Do NOT freeze CC0/CC1 layout until the diagnostic ADR sites are mapped to exact structure offsets.

---

# 13. CURRENT COLOR-SCIENCE MODEL

Use this as the working hypothesis, with only the explicitly frozen portions treated as fact:

```text
sensor / camera RAW
    ↓
DNG calibration data
    - CM1
    - CM2
    - T1
    - T2
    ↓
Kelvin / xy handling
    ↓
reciprocal-temperature matrix interpolation
    ↓
white-point / neutral mapping
    ↓
rendered color correction
    - CC0
    - CC1
    - temperature
    - tint
    - gains
    ↓
B2Y
    - WB gain
    - CC matrix
    - gamma
    - tone-control table
    - RGB/YC transforms
    ↓
JPEG/output color space
```

Do not assume CM1/CM2 themselves are the complete Leica JPEG look.

---

# 14. NEXT INVESTIGATION ORDER

## FIRST — resolve v1.23 copy direction and exact DNG record ownership

Target:

- `0x4204F2EC`
- all relevant call sites around `0x420A3638`
- identify source vs destination for the 0x2C matrix copies
- determine exact ownership of CM1/CM2
- resolve the meaning of matrix-record `+0x28`

Desired freeze:

```text
M10R_DngColorCalibration {
    T1
    CM1[3][3]
    T2
    CM2[3][3]
    scale/denominator semantics
}
```

Do not manufacture field names without firmware support.

## SECOND — finish CC0/CC1 layout

Map exact offsets for:

- default-data flag
- Kelvin
- tint
- 3×3 matrix values
- gain-remap values

Determine how CC0 and CC1 relate to the two DNG illuminant endpoints versus scene/current white balance.

## THIRD — WB / AWB path

Trace:

- `get_kelvin_table_count`
- WB presets
- auto-WB selected Kelvin/tint
- `NeutralToXY`
- `SetWhiteXY`
- `MapWhiteMatrix`
- B2Y WB gain handoff

Separate:

1. measured/selected white point;
2. matrix interpolation temperature;
3. rendered WB gains.

## FOURTH — tone and rendering

Trace B2Y:

- CC matrix programming
- gamma tables
- tone-control tables
- RGB output clipping / deknee
- RGB↔YC transforms
- color NR/chroma suppression only if visually material

Find whether Leica image-style modes alter:

- matrix
- gamma
- tone curve
- saturation/chroma
- multiple stages.

## FIFTH — offline M10-R oracle

Once CM1/CM2 + WB + first tone path are frozen, build a desktop/offline reference renderer before the APK.

Suggested pipeline:

```text
Xiaomi RAW
    ↓
Xiaomi sensor linearization / calibration
    ↓
M10-R dual-illuminant color calibration
    ↓
M10-R WB / rendered color correction
    ↓
M10-R gamma / tone
    ↓
sRGB JPEG preview
```

Keep a separate DNG path that DOES NOT bake the JPEG look into the RAW.

---

# 15. SAMPLE APK TARGET

A sample APK is now an explicit project milestone.

Do not wait until every firmware color routine is understood.

First meaningful APK target:

```text
Xiaomi 15 Ultra MAIN CAMERA ONLY

capture
  → M10-R software metering
  → M10-R exposure decision
  → 12 MP / selected practical resolution
  → M10-R calibrated DNG
  → M10-R rendered JPEG
```

Use the same PhotonCamera branch family / capture infrastructure proven in the M9 project.

Recommended architectural split:

```text
Photon shared infrastructure
    |
    +-- M9 photographic implementation
    |     +-- M9 exposure
    |     +-- M9 DNG/RAW
    |     +-- M9 renderer
    |
    +-- M10-R photographic implementation
          +-- M10-R 22x16 metering
          +-- M10-R exposure solver
          +-- M10-R DNG calibration
          +-- M10-R WB / color management
          +-- M10-R renderer
```

Share infrastructure, NOT photographic constants.

The first APK should prioritize correctness and image quality over aggressive optimization.

---

# 16. M9 LESSONS TO REUSE

Reuse the engineering solutions already learned in the M9 Photon integration:

- primary custom render path
- JPEG + DNG dual output
- native/JNI color processing where performance matters
- avoid unnecessary RAW copies
- explicit timing diagnostics
- correct buffer ownership / rapid-shot lifecycle
- high-quality JPEG as a hard constraint
- main lens first
- freeze photographic behavior before performance tuning

Do not inherit M9-specific color or exposure constants into M10-R merely because the infrastructure is shared.

---

# 17. RESEARCH ARTIFACTS CREATED NEAR THIS HANDOFF

Metering closure / preceding chain:

- `research/M10R_v100_aeawb_grid_geometry_FROZEN.md`
- `research/M10R_v104_aeawb_mmio_grid_FROZEN.md`
- `research/M10R_v104_aeawb_register_data_plane.txt`
- `research/M10R_v105_pwch_channel6_schema.txt`
- `research/M10R_v106_channel6_pwlsize_provenance.txt`
- `research/M10R_v107_channel6_pwlsize_decode.txt`
- `research/M10R_v118_METERING_BOUNDARY_FROZEN.md`

Color science:

- `research/M10R_v119_color_science_survey.txt`
- `research/M10R_v120_color_management_parameter_map.txt`
- `research/M10R_v121_dng_matrix_kelvin_core.txt`
- `research/M10R_v122_dng_cm_provenance.txt`
- `research/M10R_v123_color_finished_dng_layout.txt`
- `research/M10R_v124_rendered_cc0_cc1_layout.txt`

Relevant workflows:

- `.github/workflows/m10r-v120-color-management-parameter-map.yml`
- `.github/workflows/m10r-v121-dng-matrix-kelvin-core.yml`
- `.github/workflows/m10r-v122-dng-cm-provenance.yml`
- `.github/workflows/m10r-v123-color-finished-dng-layout.yml`
- `.github/workflows/m10r-v124-rendered-cc0-cc1-layout.yml`

---

# 18. HARD RULES FOR CONTINUATION

1. Do not reopen broad metering archaeology unless implementation shows a real missing semantic.
2. Preserve `22 × 16 = 352` as the metering geometry.
3. Preserve the statistics-block `root + 0x80` payload ABI.
4. Do not claim physical equality between CA9 `workflow+0x480` and Prepro allocation base unless new evidence proves it.
5. Do not revive 20-byte/cell or 40-byte/cell PWLSIZE theories.
6. Keep DNG CM1/CM2 separate from rendered CC0/CC1.
7. Keep RAW/DNG color calibration separate from Leica JPEG/tone rendering.
8. Treat the Robertson table as CCT infrastructure, not Leica-specific color science.
9. Confirm copy direction before freezing structure ownership.
10. Prefer narrow/surgical disassembly over full-image Capstone scans; broad scans repeatedly caused runner cancellation.
11. Exact firmware behavior is preferred over approximations when firmware evidence exists.
12. The project goal is a working camera, not total firmware archaeology.

---

# 19. FIRST ACTION IN NEXT SESSION

Start with the v1.23 ambiguity:

```text
Resolve 0x4204F2EC copy direction and CM1/CM2 record ownership.
```

Then immediately:

```text
Freeze exact DNG CM1/CM2 + T1/T2 structure
    ↓
map CC0/CC1 exact structure
    ↓
trace WB/AWB
    ↓
trace B2Y gamma/tone
    ↓
build offline M10-R color oracle
    ↓
build first Photon-based sample APK
```

This is now the shortest path from firmware research to a usable M10-R camera implementation.
