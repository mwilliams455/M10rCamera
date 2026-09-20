# M10-R Y BLEND EDGEISOLATION1A
## ISO/mode-dependent edge synthesis is separately configured from Y BLEND

**Date:** 20 September 2026  
**Repository:** `mwilliams455/M10rCamera`  
**Isolated research branch:** `m10r-yblend-edgeisolation1a`  
**Starting head:** `f6c6a0e0713a120e0cbcc642933cde88f0a5ae75`  
**Exact CI-tested commit:** `d80ad91dbd07ce91aaf63a1c2ea20206df86c458`  
**Result:** `PASS_EDGE_CONFIGURATION_ISOLATION_ONLY`  
**Gate-C:** NOT passed. The actual Y BLEND pixel equation and consumer routing remain unresolved.

## 1. What this pass establishes

The original M10-R edge selector, calibration lookup and register programmer have now been executed together for **all 132 declared keys of the 15 EDGE SYNTHESIS records** in the verified B2Y calibration section. The same record values also pass through the original SAM7 edge programmer. In these tests, edge-synthesis fields change with ISO and internal mode while the already-programmed Y BLEND registers remain unchanged. [F1–F3; E1]

This is a concrete competing explanation to control for in the dual-consumer investigation: ordinary image differences across ISO or operating modes cannot, by themselves, identify which signal Y BLEND supplies to edge processing. The firmware independently changes edge-synthesis configuration. **No resulting photographic strength or brightness change was measured here.** [E1; inference]

The existing v094 inventory had already identified the IMG EDGE SYNTHESIS selector and register bank. This work does not claim that map as a new discovery. The new contribution is complete original-code selection across the calibration keys, cross-core configuration checks, explicit mode/ISO transitions, and isolation from the separately identified Y BLEND registers. [P1; E1]

Nothing in these findings proves or disproves that a Y BLEND output feeds edge processing in hardware. No renderer, capture branch, photographic parameter or APK is changed by this work.

## 2. Actual Leica path, not a name borrowed from the SDK

The executed IMG chain is:

```text
0x154064  EDGE SYNTHESIS selector
    -> 0x4EFD8 / 0x4F1F8  original string copy / concatenation
    -> 0x1A0FC4            original record lookup, ID 0x11
    -> 0xD16DC             original register programmer
    -> 0x20020E00 and selected registers through 0x20020E40
```

Identity guards resolve the selector's own label reference at `0x1540AA`, check record ID `0x11` at `0x1540B4`, check the lookup call at `0x1540B8`, and check the driver call at `0x1540D8`. The source label is **EDGE SYNTHESIS**. [F2; E2]

The independently executed SAM7 programmer begins at `0x51342`. Its own diagnostic reference at `0x5149C` resolves to `Im_B2Y_Ctrl_EdgeBlend`. This is **not** SAM7 `0x51DA6`, the previously audited combined YC CONVERSION / Y BLEND programmer. [F3; E2]

The calibration lookup key is assembled from a caller-supplied mode string at `+0x02` and ISO string at `+0xB4`. Examples are `_B2YMODE:STILL_ISO:100` and `_B2YMODE:SLIVE_ISO:800`. The separate numeric mode halfword at `+0x00` and numeric ISO word at `+0xB0` participate in the selector's cached-update decision. [F2; E1]

**Fixture boundary:** the harness supplies the exact stored strings but uses deliberately distinct numerical mode IDs. It tests the selector's equality-based cache behavior; it does not recover Leica's true numerical mode enumeration or reproduce full camera caller-state construction.

## 3. Fresh calibration inventory and concrete changes

Record ID `0x11` occurs at indices **36–50**, with one 84-byte payload per record and **132 unique declared keys** in total. Payload offsets run from `0x6FC14` through `0x70154`. Exact headers, keys, decoded values, offsets and SHA256 hashes are in `edgeisolation_results.json`. Offsets include the extracted section's four-byte prefix. [F1; E1]

All 15 records share this form, where `A` varies by key group:

```text
slots 0–1:   2, 2
slots 2–7:   A, A, A, A, A, A
slots 8–18:  eleven zeros
slots 19–20: 8191, 8191
```

The following table reports stored field values, **not decoded sharpening gain or a fixed-point denominator**:

| Declared ISO key | STILL / STILLLINK: each of slots 2–7 | SLIVE / SMAGNI: each of slots 2–7 |
|---|---:|---:|
| 100, 160 | 5400 | 1800 |
| 200, 250, 320 | 4096 | 1800 |
| 400, 500, 640 | 4096 | 1500 |
| 800, 1000, 1250 | 3700 | 1200 |
| 1600 through the listed 10000 keys | 3700 | 2000 |
| 12500 through the listed 32000 keys | 3700 | 4500 |
| Listed keys from 40000 through 200000 | 3700 | 0 |

These ranges group **discrete stored keys**, not every intervening ISO value. High-ISO keys and internal mode names do not establish available user-facing camera settings. Likewise, the names SLIVE/SMAGNI are retained as firmware key strings; this pass does not map them to a particular phone-preview implementation. [F1]

The real selector was run through a transition sequence with its cache-use argument set to one:

```text
STILL ISO100 -> STILL ISO200 -> STILL ISO800
             -> SLIVE ISO800 -> SMAGNI ISO800
```

Every changed numeric key triggers original lookup/programming. The transitions from 5400 to 4096 to 3700 to 1200 change the six fields in registers `0x20020E10/14/18`. The final mode change performs another lookup but makes no register-value change because the selected payloads are equal. The Y BLEND bank is preserved throughout. [E1]

This distinguishes changed caller state, a new lookup, and a changed register result. None of those alone establishes a measured pixel effect.

## 4. Edge synthesis and Y BLEND are distinct programming contracts

The edge programmer consumes 21 four-byte source slots. Its actual destination widths are:

| IMG source slots | Destination | Field widths |
|---|---|---|
| 0, 1 | `0x20020E00`, shifts 0 and 4 | Two 2-bit fields |
| 2–7 | `0x20020E10/14/18`, low/high halves | Six 14-bit fields |
| 8–13 | `0x20020E20/24/28`, low/high halves | Six 14-bit fields |
| 14–18 | `0x20020E30/34/38` | Five 16-bit fields |
| 19, 20 | `0x20020E40`, high then low | Two 13-bit fields |

The tested SAM7 packing is **`<2B19H>`**, with the final two halfwords exchanged relative to the IMG slot order. This is a 40-byte analysis-side reconstruction validated against original instructions, **not a recovered firmware-side constructor**. [F2–F3; E1–E2]

By contrast, the actual Y BLEND record `0x0D` controls two six-bit fields at `0x2002092C` plus the two differently packed words at `0x20020930/34`. Its normal record remains `[0,32,16383,16383,16383,16383]`. [F1; E1]

For every edge key, the suite first executes the actual Y BLEND selector and verifies its normal programming. It then executes EDGE SYNTHESIS. The complete modeled `0x4000`-byte register window matches the edge-only update model; the three Y BLEND words are unchanged. The original edge selector/programmer path makes no monitored MMIO read of those three Y BLEND words. [E1]

For all 15 edge payloads, the test also reverses the order of direct edge and Y BLEND programming. The resulting full register windows match. This is **commutation of disjoint configuration updates**, not commutation of pixel operations, hardware stage ordering, or proof that the signals are independent.

## 5. The SDK's EdgeBlend structure cannot be substituted directly

The related public source at pinned commit `f5fc84bd5c475f4c15017b7bff749f81c3618287` declares a different `CtrlEdgeBlend`: one one-bit type selection, three 10-bit boundaries, two sets of four offset/gain fields, and two 9-bit direction-clip fields. [S1]

Leica's tested path instead contains **two two-bit controls**, both set to **2** by every normal edge record, together with the different field groups above. A direct mapping of one of those normal values to the SDK's one-bit selector would lose information. This is a concrete layout incompatibility, not merely a different structure name.

The comparison source is a third-party port, not an authenticated specification for the M10-R revision. It gives useful terminology and search leads but does not identify Leica's source signals, field meanings, fixed-point scales or blend equation. The SDK's separately named YC Y/Yb ratios also remain separate from its EdgeBlend control. [S1; prior SDKBRIDGE1A boundary]

**The unknown Y BLEND pairs remain unknown.** EdgeBlend's final 13-bit fields do not explain the low-15/full-high-16 packing of `0x20020930/34`. No min/max, signed endpoint, positive/negative magnitude or channel assignment is promoted by this comparison.

## 6. What executed and passed

| Group | Original routine entries |
|---|---:|
| All 132 keys: Y selector, edge selector, SAM edge programmer, cached edge repeat | 528 |
| 128 boundary/random parameter sets: IMG normal, IMG fallback, SAM normal | 384 |
| Initial Y setup and five mode/ISO transition entries | 6 |
| Synthetic missing-key fallback | 1 |
| Both programming orders for all 15 payloads, four entries each | 60 |
| **Total** | **979** |

There are **719 IMG entries**, **260 SAM7 entries**, **15,342 monitored register writes**, and zero calibration-memory writes by the executed original instructions. The test compares the complete modeled register window after every entry. All 132 cached repeats skip lookup/programming as expected. [E1]

The synthetic missing key uses ISO string `101` to exercise the real lookup failure and fallback. It is not an observed camera state or a new Leica preset. The fallback supplies zeros to the two controls and twelve 14-bit fields, `0x8000` to each of the five 16-bit fields, and `0x1FFF` to both final fields. The selector clears its numeric cache values after failure. No hardware bypass or photographic interpretation of this fallback is established. [F2; E1]

The only substitutions are the IMG file-registry resolver and diagnostic logger, or SAM7 clock helpers. Original string copy, concatenation and comparison, record lookup, selectors and register writers execute. The registry fixture points to verified calibration bytes after removal of the extracted section prefix; its runtime addresses are chosen test addresses, not recovered physical allocations.

Inputs include deterministic randomized register windows, a fixed stack sentinel, actual calibration bytes and explicit boundary/full-width parameter interventions. These tests do not emulate sensor input, physical clocks, memory-mapped hardware side effects or any ISP pixel datapath. **They are not 979 photographs or photographic parity tests.**

## 7. CI and integrity

Source-tool commit: `1c1c1cda425a6750b8ed0572fbf681884829f227`.  
Workflow / exact tested commit: `d80ad91dbd07ce91aaf63a1c2ea20206df86c458`.

**GitHub Actions run `35516051722` succeeded**, producing artifact `10606418774`. The downloaded ZIP passes CRC checking and all **eight manifest entries** pass length and SHA256 validation. The source tool, workflow, full result JSON, all execution histories, original instruction listing and stdout are byte-identical between local execution and CI. [E3]

```text
CI artifact SHA256:
88b1a5b83bb0fb618e62ba622d0843dadaf16f8adbf32aefe020593cc8123c92

Canonical tool SHA256:
2624c1ea34402663a8968c5a0e9b628ddcdf92bccd743b2b387694da707e7592

Full result JSON SHA256:
8a750be1351f74c92f40ea06457082d8f1c53a965cfa2cd8295440c35cbbd1b3

Execution histories SHA256:
56723c17bf4e98cd7da6455278e097838ddc6648d209757327a8d9ffe4052280
```

The tested diff contains only the new research tool and workflow. Later report/index persistence is separate from the exact CI-tested commit. Final scope and frozen branch rechecks are recorded in the package's provenance file.

Unlike the preceding local-only CONSUMER1A pass, repository writes were available in this continuation and the new work was pushed to its isolated branch. CONSUMER1A's external hypothesis is referenced as retained context; its separate local patch is not silently represented as part of the tested repository diff.

## 8. What this changes in the investigation

**Established:** exact edge-record selection over the whole declared key set; source-pointer forwarding; independent normal/fallback/cache behavior; cross-core field packing; and software isolation from Y BLEND updates.

**Constraint on candidate testing:** hold operating mode and edge configuration fixed when attributing an observed edge difference to a proposed Y/Yb source blend. Changing ISO is not a clean intervention on a single hypothetical source weight. This inference follows from the verified independent configuration changes; it is not a measurement of their photographic effects.

**Still not established:** the input signal to the edge block, the meaning of its two normal value-2 controls, their relationship to the two Y BLEND ratios, the Y BLEND paired-field semantics, or the scaling, rounding and clipping of the hardware pixel equation. The patented dual-consumer model remains an external hypothesis, neither verified nor falsified by this pass.

The next discriminating target is a source-backed meaning for the two controls at `0x20020E00` and/or an actual pixel-input routing relationship. Do not substitute the SDK's one-bit selector or identify a Y BLEND weight with EDGE SYNTHESIS solely because both names contain “blend.” Additional register-mask repetitions do not settle that relationship.

## 9. Bounded external search result

The inspected related-SDK YC component test (`CT_Im_R2y_1_67`) sets register parameters and prints register values; it does not supply a golden pixel result for those ratios. The inspected Palladium test wrapper imports input memory and exports output memory around hardware execution; those imported pixel vectors and expected outputs are not present in that inspected function. These excerpts therefore did not provide an independent pixel oracle. This is a bounded source observation, not a claim that no such vectors exist anywhere. [S2–S3]

No usable exact-revision hardware specification was obtained in this continuation. The external source comparisons were not executed in CI; they are read-only comparisons with separately retained source hashes. No undocumented numerical inference was used to change the renderer.

## 10. Reproduction and evidence index

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_edgeisolation1a.py \
  /path/to/verified/sections results --stress-cases 128
```

Do not use `python -O`. The tool checks all three section SHA256 values before execution. The workflow demonstrates obtaining the original firmware, verifying its hash, using the repository's existing decoder, and verifying the unpacked hash before section extraction.

**[F1]** Verified `074_IMG_Calibration_Data_data_calib_B2Y.bin.bin`, SHA256 `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b`.

**[F2]** Verified `092_IMG-System.bin`, SHA256 `53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4`.

**[F3]** Verified `100_IMG-SAM7.bin`, SHA256 `c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae`.

**[P1]** Retained `research/M10R_v094_b2y_selector_inventory.txt`, including the existing `0x154064` / record `0x11` / `D16DC` mapping. This prior inventory is context, not a substitute for the newly executed tests.

**[E1]** `results/edgeisolation_results.json` and `results/execution_histories.json`; full key inventory, results and execution records.

**[E2]** `results/original_instruction_anchors.txt`; bounded original selector and programmer disassembly.

**[E3]** `results/ci_provenance.json`; verified run, commit, artifact and local/CI comparisons.

**[S1–S3]** Pinned `ZMlogicL/companyTask` source paths, hashes, URLs and line ranges in `results/source_index.json`. The primary structural comparison is `MILB_API/Project/ImageMacro/src/imr2y.h`, lines 701–712, SHA256 `2a23e54a55f1e44978fa41e9c597e371489f3d76cbaa4d9e54392db4198447f8`.

The deliverable contains the report, reproducible tool/workflow, machine results, execution evidence, source index, provenance and a checksum manifest. It excludes firmware binaries, external SDK source files, third-party libraries, photographs and APKs. The manifest identifies package contents, not all required external reproduction inputs.
