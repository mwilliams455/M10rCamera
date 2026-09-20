# M10-R Y BLEND YBPATH1A
## Separate coefficient rows, asymmetric tone controls and conditional table loading

**Date:** 20 September 2026  
**Repository:** `mwilliams455/M10rCamera`  
**Research branch:** `m10r-yblend-ybpath1a`  
**Starting commit:** `febc0dd090a604ca4d5b4c465f5e0ca18853fb9a`  
**Exact successful CI-tested commit:** `2288190f2a1dcc5d43757657fbf13be2697e48e9`  
**Result:** `PASS_CONTROL_PATHS_ONLY`; **Gate-C remains NOT passed**.

## 1. Result and evidence boundary

The verified M10-R firmware programs three different coefficient rows in CC0, TONE and YC CONVERSION. Their source values, register destinations and independent configurability are now checked through original IMG and SAM7 instructions. The normal TONE record also programs two independent enable-like controls asymmetrically, plus a separate selection control. Original table-copy instructions demonstrate a configuration-dependent second table upload.

These findings strengthen the related-SDK Y/Yb lead. They do **not** establish the M10-R's internal pixel wiring. The SDK's names suggest a CCYC-derived Yb reference and a TCYC-derived Y reference, with separate tone handling. That remains a cross-revision hypothesis: neither the connection to the two Y BLEND ratios nor the final pixel equation has been recovered.

No application source, renderer setting or capture behavior was changed. RENDER1Q, CC1MAP1A, YBLEND1B `k=0.35`, the current YC2A matrix and `m10r-capture1b` remain frozen. No APK was built.

## 2. Three coefficient rows are real, separately programmed controls

All offsets below are raw offsets in the named extracted firmware section. Register addresses are MMIO addresses. Calibration slots are zero-based little-endian uint32 storage slots; the original load and destination widths need not equal that storage width.

| Source | Normal coefficients | Calibration slots | Destination | Width of each destination field |
|---|---|---|---|---:|
| CC0 trailing row, record `0x06` | **77, 150, 29** | 11, 12, 13 | `0x20020140`, shifts 0, 8, 16 | 8 bits |
| TONE row, record `0x08` | **1024, 2661, 410** | 7, 8, 9 | `0x20020808` low/high and `0x2002080C` low | 12 bits |
| YC CONVERSION first row, record `0x0C` | **1224, 2403, 469** | 0, 1, 2 | `0x20020900` low/high and `0x20020904` low | 13 bits |

The suite independently changes each row component, including values outside its destination width, while holding the other configuration fixed. Across 45 interventions and both cores, only the permitted coefficient-register family changes. The original instructions agree with independently expressed register-update models. The existing Y BLEND controls are not changed by these row interventions.

The row sums are 256, 4095 and 4096. The determinant of the matrix formed by these rows is 376215. Thus they are not one stored row or merely scalar copies of one another. These are algebraic statements, **not** proof of shared RGB input samples, physical fixed-point denominators, normalization rules or stage order. In particular, this does not authorize normalizing the TONE row by 4095 or replacing one row with another in the renderer.

### Source and instruction anchors

The CC0 selector has the firmware's own `COLORCORRECTION0` label, selects record 6 and calls IMG `0xD0C74`. Its label reference is at `0x153D4E`, lookup at `0x153D5C`, and driver call at `0x153D7C`.

The TONE selector's label reference is at `0x154BFC`, its record-8 lookup is at `0x154C0A`, and its **BLX** at `0x154C90` enters IMG `0xD3C20` in **ARM mode**. The corresponding SAM7 TONE routine at `0x5398C` is also ARM, not Thumb. SAM7's diagnostic at `0x53E38` identifies `Im_B2Y_Ctrl_Tone`.

| Routine | IMG entry / mode | SAM7 entry / mode |
|---|---|---|
| CC0 configuration | `0xD0C74`, Thumb | `0x4FDB6`, Thumb |
| TONE configuration | `0xD3C20`, ARM | `0x5398C`, ARM |
| Gamma-related configuration | `0xD25A8` and `0xD15EC`, Thumb | `0x51BCC`, Thumb |

The existing YC CONVERSION and Y BLEND identities remain record `0x0C` / `D4570` and record `0x0D` / `D4480`. They are not renamed by this work.

The executed instruction listing is separate from `static_selector_anchors.txt`. Selector identity bindings are checked, and the bounded selectors are disassembled; this pass does **not** claim to execute complete selector/lookup chains.

## 3. Normal tone controls are asymmetric

The freshly extracted normal record-8 controls are:

| Source slot | Value | Programmed destination | Related-SDK interpretation, not yet proven Leica signal identity |
|---|---:|---|---|
| 0 | **1** | `0x20020800`, bit 0 | RGB tone enabled |
| 1 | **0** | `0x20020800`, bit 1 | Yb tone disabled |
| 5 | **0** | `0x20020804`, bit 16 | Tone reference selected from TCYC-derived Y rather than CCYC-derived Yb |

Both original cores were executed for all eight combinations of these three controls. The controls are independently programmable without changing the coefficient rows or the separate Y BLEND ratios. This is an original-firmware result.

The rightmost column comes from the related SDK: its tone-control declaration distinguishes RGB and Yb tone enables, and describes two tone-reference choices derived through TCYC and CCYC. The SDK layout and field widths differ from Leica's. Consequently, the defensible inference is conditional: **if these corresponding controls preserve their signal roles across revisions, the normal configuration applies unequal tone treatment to RGB and Yb.** It is not yet proven that Leica's Yb pixels bypass tone, or that either reference reaches final image luminance.

This prevents an unsupported assumption that every luminance reference receives the same curve. It does not supply the missing Y BLEND numerator, denominator, direction or clipping rule.

## 4. A real table-loading condition accompanies the selection control

The TONE record is one 176-byte record with twelve declared keys: four B2Y modes crossed with LOW, MEDIUM and HIGH contrast. Its coefficient row and the three controls above are shared across those keys. Separate table records `0x19` and `0x1A` have contrast-specific payloads.

With the normal record, the original IMG driver copies:

```text
record 0x19 payload prefix -> 0x20A00000, 0xA000 bytes
record 0x1A payload prefix -> 0x20A0A000, 0xA000 bytes
```

The second copy occurs when the full source value in slot 5 equals zero and the full source value in slot 3 equals one. Switching slot 5 from zero to one, holding other normal values fixed, suppresses the second copy. Synthetic full-width cases verify that this software condition must not be replaced by a test of only the masked register bits.

The original ARM memory-copy function at `0x4F2F0` executes unchanged. The tests compare the complete modeled 262144-byte table window, including regions that should remain untouched. LOW, MEDIUM and HIGH source records are tested directly, not replaced with generated tone curves.

Records `0x19` and `0x1A` are byte-identical within each contrast setting, while their payloads differ between contrast settings. This is evidence of actual table content and upload behavior. **It does not identify one bank as RGB and the other as Yb**, prove which pixels consume a bank, or prove hardware stage order.

## 5. CC0's matrix and trailing row have different provenance

The CC0 selector supplies its caller-state pointer plus `0xD4` as the driver's third argument. In the tested normal path, the driver reads its nine correction-matrix coefficients and precision from this auxiliary state, rather than from record-6 slots 1 through 10. The trailing `77,150,29` row, however, comes directly from record-6 slots 11 through 13.

Holding the auxiliary state and trailing row fixed, the suite changes each of record-6 slots 1 through 10 independently. No register changes result. This distinguishes the caller-supplied correction matrix from the calibration-supplied trailing row; it does not prove that all CC0 behavior is fixed.

The tests' auxiliary matrix and precision are explicit fixtures. They are **not** claimed to reproduce a physical camera's white balance, illumination-dependent state or live correction matrix.

## 6. Limits of the SDK correspondence

Five public files were pinned to `ZMlogicL/companyTask` commit `f5fc84bd5c475f4c15017b7bff749f81c3618287`, fetched independently in CI and SHA256-verified. The repository is a third-party port, not an authenticated specification for the exact M10-R image processor. Source URLs, hashes and line anchors are in `ybpath_results.json` and the test tool.

The relevant declarations are in `imr2yctrl2.h` (CCYC-derived Yb and gamma controls), `imr2yctrl.h` (tone enables and reference selection), and `imr2y.h` (a separate chroma-referenced luminance-blend block). The register header `fr2y6a.h` and writer `imr2yctrl2.c` preserve the comparison's structural context.

Two boundaries are particularly important:

**Gamma is not a direct ABI match.** Leica's record 9 supplies the two controls at `0x20020800` bits 16/17; record 11 supplies bits 24/25. A four-byte SAM7 structure programs the same four independent fields. All sixteen boolean combinations were checked. The SDK's gamma structure and bit layout differ. Do not label Leica bit 25 a Yb enable merely because the related SDK has Yb gamma-table controls.

**The SDK's chroma-reference blend block is separate.** Its `YBCRVCTL` area controls are not the previously identified `YYBLND`/`YBBLND` ratio fields. A similarly named luminance blend elsewhere in the SDK does not establish a bridge to Leica's Y BLEND registers.

No additional usable public specification was found that resolves the exact Leica datapath. These source differences are retained rather than reconciled by assumption.

## 7. What ran and what passed

The canonical tool is `tools/m10r_yblend_ybpath1a.py`. It verifies firmware-section hashes, calibration identity and source hashes before testing. Assertions must remain enabled. The test seed is `0xB1A2026`.

| Check group | Original routine entries executed |
|---|---:|
| Normal configuration setup | 9 |
| 45 coefficient-isolation interventions, two cores | 90 |
| Eight tone-control combinations, two cores | 16 |
| Sixteen gamma combinations, two IMG routines and one SAM7 routine | 48 |
| 256 CC0 plus 256 TONE boundary/random cases, two cores | 1024 |
| Ten unused-record-matrix-slot interventions, two cores | 20 |
| Three contrast table uploads, two cores | 6 |
| **Total** | **1213** |

There were 616 IMG entries and 597 SAM7 entries, 32927 observed MMIO writes, and zero changes to preserved bit 15 in the monitored paired words. Each register result is compared over the complete 16384-byte modeled MMIO window.

Only SAM7 clock helpers `0x4D1B4` / `0x4D118` and IMG diagnostic logging at `0x140154` are stubbed. The original IMG memory-copy instructions execute. MMIO state and stress parameters are deterministic randomized/boundary fixtures; stack memory uses a fixed sentinel. Busy status bits are cleared for these success-path tests. Busy/error behavior, physical clock effects, reset side effects and ISP pixels are not modeled.

The 28-byte SAM7 CC0 and 104-byte TONE parameter structures are analysis-side packing reconstructions validated against original programmers. They are **not recovered firmware-side constructors**, and the actual SAM7 compact-structure caller remains unresolved.

The retained BIT15 suite was separately rerun: 10240 checked executions, 61440 paired-register writes, zero bit-15 changes. Its result remains byte-identical to the retained audit. Do not combine either suite's totals into a claim of pixel validation.

## 8. CI and integrity

Source was committed at `eed75c865cc9e55807a503ff10f7a6a93191b0ac`. The first workflow commit, `5111576173b65f820f8b9cdd3d22bf18eedbe12a`, ran the tests but failed the final provenance diff because a shallow checkout lacked the starting commit. Run `35509601272` is therefore correctly recorded as failed.

A workflow-only correction fetches that immutable base before the diff. **Run `35509666868` succeeded** at commit `2288190f2a1dcc5d43757657fbf13be2697e48e9`. The research script was not changed to obtain the successful result.

```text
Artifact ID: 10603774878
Artifact: M10R-YBLEND-YBPATH1A-EVIDENCE
Artifact ZIP SHA256:
2cd0c4b443f500ef3874fe564895434672680b8ace22d92e4129f745a31f623c

Research script SHA256:
376162e0839b83be755e3726714685d9dcbe124fe14d8237a809d678580cb925

ybpath_results.json SHA256:
4c86b0bc18fca3c10578b435f3da7127936a18c07dd157331ddd8ad589499a23

Retained audit result SHA256:
50eb66d4091436c76bd90d9fff94d89214c945089e4b27e95d5cba7792e747e3
```

The downloaded CI ZIP passes CRC checking and all twelve manifest entries pass length/SHA256 validation. The canonical tool, complete results, all execution histories, executed instruction listing, stdout and old audit output are byte-identical between local execution and CI. The local run used Python 3.13.5 with original Capstone 5.0.3 and Unicorn 2.1.3 files/libraries; no binary patch was used.

The exact CI-tested diff contains only the new workflow and research tool. Report and result-index persistence commits are separate from the CI-tested commit. Final branch state and post-persistence scope are recorded in the package's `ci_provenance.json`.

## 9. Reproduction and source inventory

The workflow obtains `M10-R-30.22.23.34-Customer.FW` using the existing verified extractor. Expected firmware SHA256 is `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`; unpacked SHA256 is `859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0`. Exact section and SDK hashes are embedded in the executable tool and result JSON.

Freshly examined control payloads include record 6 at `0xA7694` (64 bytes), record 8 at `0xA76D4` (176 bytes), record 9 at `0x11F794` (24 bytes), record 11 at `0x11F814` (8 bytes), record 12 at `0x131834` (60 bytes) and record 13 at `0x131874` (24 bytes). Offsets include the extracted section's four-byte prefix. Full decoded values, table records, lookup keys and payload hashes are retained in the machine results.

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_ybpath1a.py \
  /path/to/verified/sections /path/to/repository \
  /path/to/hash-pinned/sdk/sources results --cases 256
python3 tools/m10r_yblend_bit15_audit1a.py \
  /path/to/verified/sections --cases 1024 --out results/register_emulation.json
```

The SDK root must contain the original `MILB_API/...` paths. The workflow demonstrates fetching exactly the required pinned files. Neither a report nor an input manifest substitutes for the binary inputs needed to execute the suite.

The evidence package contains this report, the full result JSON, execution histories, original instruction anchors, static selector anchors, reproducible tools, workflow, CI provenance and a checksum manifest. It excludes firmware binaries, third-party SDK files/libraries, photographs and APKs. The earlier input-artifact inventories were checked separately; they are not described as contents of this deliverable.

## 10. What this changes, and what remains to establish

A candidate implementation should no longer silently collapse CC0's trailing row, the tone-reference row and final YC conversion into one luminance calculation. It must also explain the independent tone controls and the asymmetric normal settings. These are stronger constraints than a generic two-weight blend analogy.

The original-code results establish **configuration separation**. They do not prove the hardware signals operate on the same RGB domain, determine which tone-table bank supplies which signal, identify final Y BLEND input/output routing, explain its two paired words, or recover scaling, rounding and clipping. The known normal Y BLEND controls remain `(0,32)`, fallback remains `(0,0)`, and neither maps to the renderer's `k=0.35` by this work.

The next discriminating evidence must connect these independently configured quantities to a hardware consumer or a matching-revision datapath description. A software consumer, an actual compact-structure constructor with meaningful signal provenance, or controlled hardware observations could constrain that connection. Another sweep of already-established register masks will not do so. Any interim pixel model must remain explicitly approximate and separate from renderer promotion.

**Frozen heads checked before this research:** `m10r-render1q-yblend1b-k035` at `a66b73cc339ebcb863d345c7a9ee7ff631fc86f0`; `m10r-capture1b` at `3b1e86b5055a21b548d56b23bd47f9dc66c57012`. No merge or photographic change is authorized by YBPATH1A.
