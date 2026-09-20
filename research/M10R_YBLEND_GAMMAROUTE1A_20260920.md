# M10-R Y BLEND GAMMAROUTE1A
## Five upload routes, the normal IMG route, and the unresolved hardware-sharing boundary

**Date:** 20 September 2026  
**Repository:** `mwilliams455/M10rCamera`  
**Research branch:** `m10r-yblend-gammaroute1a`  
**Starting commit:** `f6c6a0e0713a120e0cbcc642933cde88f0a5ae75` (YBPATH1A)  
**Exact CI-tested commit:** `ea1c61685e44d8f08d5538acdda20a219cbad488`  
**Result:** `PASS_GAMMA_UPLOAD_ROUTING_ONLY`. **Gate-C remains NOT passed.**

## 1. New finding and its significance

The original M10-R SAM7 code supports five CPU-visible table-upload selections for both its named IGamma and DGamma setters. The complete original IMG DIFFERENTIAL GAMMA selector, lookup and copy path uploads to the same two destinations as SAM7 DGamma selection zero. Selection four has distinct upload addresses. The test now connects a normal calibration selector to a specific upload route, rather than merely comparing gamma-control masks. [F, T, H]

The related SDK explicitly labels its corresponding gamma selections zero through four as RGB common, R, G, B and Yb. It also documents a separate control for simultaneous Yb-table writing. Therefore, a CPU trace showing only the common upload address does **not** establish that the hardware leaves Yb's table unwritten. Nor does the preceding conditional Yb tone-bypass interpretation establish gamma bypass. [S, I]

This is a new constraint on the candidate pipeline, **not a recovered pixel-consumer connection**. The upload addresses are proven for the executed code. Their proposed signal names remain cross-revision comparisons. No hardware broadcast, physical SRAM alias, table-read consumer, Y BLEND equation or photographic parity is demonstrated. [T, I]

No application code, `k=0.35`, CC1MAP1A, YC2A matrix, exposure, white balance, tone settings, image quality or capture behavior was changed. This pass creates no APK. Final branch/diff checks are retained separately in `results/ci_provenance.json`.

## 2. Original five-way upload map

All code offsets in this report are raw offsets within the named extracted section, including its four-byte prefix. Memory destinations are the addresses written by the original instructions. They are not offsets into the firmware file.

| Selector | SAM7 IGamma destination | SAM7 DGamma differential destination | SAM7 DGamma anchor destination | Corresponding gamma name in related SDK |
|---:|---|---|---|---|
| 0 | `0x20A20000` | `0x20A40000` | `0x20A68000` | RGB common |
| 1 | `0x20A21000` | `0x20A48000` | `0x20A69000` | R |
| 2 | `0x20A22000` | `0x20A50000` | `0x20A6A000` | G |
| 3 | `0x20A23000` | `0x20A58000` | `0x20A6B000` | B |
| 4 | `0x20A24000` | `0x20A60000` | `0x20A6C000` | Yb |

**The rightmost column is not a recovered Leica field label.** In particular, the SDK comparison does not directly authenticate an IGamma signal assignment. The original names IGamma and DGamma are established by their own diagnostic references, not by importing the SDK's consolidated gamma API. [F, S]

SAM7 IGamma entry `0x5262C` copies 2,048 halfwords, or 4,096 bytes. Its load/store loop is at `0x5268A/0x5268C`. DGamma entry `0x526BC` copies 2,048 anchor halfwords (4,096 bytes) and 32,768 differential bytes. Its corresponding load/store sites are `0x52734/0x52736` and `0x52744/0x52746`. Both setters return zero after successful copying. [F, T]

The computed switch is executed, not substituted. Thumb calls at `0x5265E` and `0x52704` enter the original ARM dispatch helper `0xB1B78`; the helper uses the original inline branch-offset table. The evidence listing records executed instructions and excludes those inline data bytes. This resolves these two specific computed dispatches. It does **not** recover the missing caller of SAM7 YC/Y BLEND programmer `0x51DA6`. [T, H]

Values 5, 255, 65,536 and `0xFFFFFFFF` were also executed as selector arguments. All took the parameter-error route, with no table writes. In particular, the tested firmware entry does not first truncate 65,536 to the SDK's nominal 16-bit index zero. Error code `0x0B000001` is observed; this is not an exhaustive test of all invalid arguments. [T, H]

## 3. The normal IMG calibration reaches selection-zero addresses

The full bounded path executed in this pass is:

```text
IMG selector 0x153F64
    -> original readiness check 0xCF45C
    -> original key copy 0x4EFD8
    -> original lookup 0x1A0FC4, B2Y.bin, record 0x0B
    -> control driver 0xD15EC
    -> original lookup, record 0x1C
    -> differential upload driver 0xD164C
    -> original lookup, record 0x1D
    -> anchor upload driver 0xD1694
```

Its exact diagnostic ADR at `0x153F94` resolves to the DIFFERENTIAL GAMMA string at `0x154028`. Lookup IDs and driver targets have source-instruction guards. The copies execute the original ARM memory-copy entry `0x4F21C`, including its aligned implementation; no Python replacement supplies the table writes. [F, T]

Fresh extraction of the normal record `0x0B` gives `[1,1]`. The driver programs bits 24 and 25 of `0x20020800`. This report does not identify either bit as a Yb enable or as the related SDK's simultaneous-write control. Record `0x09` is independently extracted as six zero words; its selection path is not executed in this new suite. [F, T]

Each of records `0x0B`, `0x1C` and `0x1D` has the same four declared keys:

```text
_B2YMODE:STILL
_B2YMODE:STILLLINK
_B2YMODE:SLIVE
_B2YMODE:SMAGNI
```

All four keys pass through the original lookup. Successful normal or forced updates copy:

| Calibration source | Full payload size | Original copied prefix | Destination |
|---|---:|---:|---|
| Record `0x1C`, payload `0x11F834` | 65,536 bytes | 32,768 bytes | `0x20A40000` |
| Record `0x1D`, payload `0x12F834` | 8,192 bytes | 4,096 bytes | `0x20A68000` |

The copied prefix sizes agree with the retained DG asset tooling; they are not a newly invented gamma-coordinate model. Full record and active-prefix hashes are in the machine results. A separate execution of SAM7 selection zero with the same calibration prefixes matches these intended write ranges and byte values. [T, H]

An executed write to selection-zero addresses proves **where the CPU uploads**, not which physical table stores receive it after any hardware fan-out, or which pixel signal subsequently reads it. Likewise, the absence of a direct selection-four write in this bounded IMG selector does not prove that no other firmware path writes there. [I]

## 4. Upload selection and gamma configuration are separate software questions

For SAM7 DGamma, all sixteen combinations of the four previously identified gamma configuration bits (16, 17, 24 and 25 in `0x20020800`) were tested at selections zero and four. The same index still selects the same destination pair. The setters leave the modeled control-register window unchanged. In these successful setter traces, their only read in that window is the activity-status word `0x20020004`; they do not read the four gamma-configuration fields. [T, H]

This bounds a software fact: these fields do not change the setter's CPU destination selection. It says nothing about whether hardware interprets those fields during a table write or during pixel processing. A RAM-backed test cannot adjudicate either effect. [I]

The original activity checks are also executed. IGamma checks status bit 5 through `0x51C42`; DGamma checks bit 6 through `0x51C58`. Busy tests at all five selections return `0x0B000005` and write no tables. Null-source tests also leave the table window untouched. Real peripheral timing and clocks are not modeled. [T, H]

## 5. Cache, busy and incomplete-update cases

The normal IMG selector uses a halfword cache at `0x408CEDBC`. A matching cached halfword and update argument equal to one return before lookup **and before the readiness test**. The explicit cached-plus-busy case performs neither MMIO reads nor table writes. A forced update with argument zero goes through readiness checking and lookup even when the cache matches. The test's mode/cache value 17 is a fixture, not an identified Leica enum. [T, H]

If an uncached/forced update finds the DG activity bit set, the original selector clears the cache and does not enter the record loaders. This differs from merely seeing no upload after a cached request. [T, H]

The negative-control sequence also exposes a non-atomic update. If record `0x1D` is synthetically removed, record `0x1C` has already been copied. The later fallback clears the two DG controls and the cache, but does not undo the differential-table bytes. By contrast, a missing earlier control or differential record prevents subsequent normal copies because the fallback flag persists across the calls. [T, H]

These interventions are tests of code paths, not observed camera corruption or newly discovered Leica operating modes. They matter when interpreting diagnostic traces: an upload, a skipped upload and a partial failed update are not interchangeable evidence of which tables the ISP actually used. [I]

## 6. What the related SDK adds—and what it cannot add

Four files were checked against their immutable hashes at `ZMlogicL/companyTask` commit `f5fc84bd5c475f4c15017b7bff749f81c3618287`. They were independently fetched and rechecked in CI. This is a third-party SDK port for a different revision, not an authenticated specification for the M10-R processor. [S, C]

Relevant source anchors:

- `MILB_API/Project/ImageMacro/src/imr2yset.c`, lines 282–303: gamma selection mapping, including RGB-common and Yb destination members.
- `MILB_API/Project/ImageMacro/src/imr2yctrl2.h`, lines 118–131: gamma enable, mode and the separately described Yb simultaneous-writing choice.
- `MILB_API/Project/ImageMacro/src/imr2yctrl2.c`, lines 623–625: corresponding assignments into `GMCTL`.
- `MILB_API/MILB_Header/include/Image/fr2y6a.h`, lines 931–944: the inspected `GMCTL` bitfield layout, with the simultaneous-write field at bit 8.

The declaration comment refers to `TGCTL.GAMSW`, whereas the inspected writer and register declaration place it in `GMCTL`. That discrepancy is retained, not silently turned into a Leica register name. The SDK also has gamma access-control fields at bits 4/5 that are not the four Leica fields under test. No matching Leica simultaneous-write field or writer was established here. [S]

**New model constraint:** do not infer “Yb is uncurved” from the conditional Yb tone-bypass interpretation in YBPATH1A, and do not infer “Yb's gamma table is unwritten” from an IMG common-address-only upload. The related implementation provides a concrete way a common write and Yb table programming could coexist; this is an alternative to investigate, not proof Leica uses that mechanism. [I]

Shared table contents would also not, by themselves, establish shared pixel input, stage location, enable state or output routing. We still need evidence of a pixel consumer. [I]

## 7. Executed checks and scope

Canonical tool: `tools/m10r_yblend_gammaroute1a.py`. It verifies three firmware sections, the retained audit/parser source hashes and four comparison-source hashes. Test seed: `0x6A20260920`. Python assertions must remain enabled. [T]

| Test group | Original routine entries |
|---|---:|
| Five selections × two SAM7 setters × three source fixtures | 30 |
| Four invalid selections × two setters | 8 |
| Five busy selections × two setters | 10 |
| Null-source cases | 3 |
| Sixteen control combinations × two DG destinations | 32 |
| SAM7 selection-zero calibration comparison | 1 |
| Four IMG keys × normal/cached/forced/busy paths | 16 |
| Three missing records, missing file, cached-plus-busy | 5 |
| **Total** | **105** |

Totals comprise 84 SAM7 and 21 IMG entries. Every case compares the complete 1,048,576-byte modeled table-address window and 16,384-byte modeled control-register window against the expected result. A separate per-byte write-coverage assertion verifies that unchanged bytes were not silently overwritten with identical data. Observed writes: 1,783,808 table stores and 38 control stores. No source-memory writes by the executed code were observed. These are store counts, not pixels or photographs. [T, H]

The three table fixtures are actual DG calibration prefixes, zeros and a deterministic diagnostic pattern. The DG-derived bytes supplied to IGamma are intentionally byte-copy fixtures, not evidence of real Leica IGamma presets. The randomized initial table state and fixed stack sentinel are also test fixtures. [T]

Declared substitutes are IMG file-registry resolution `0x1A0C80` and logging `0x140154`; SAM7 clock helpers `0x4D1B4`, `0x4D118`, `0x4D1A2`, `0x4D140`, plus logging `0x4548/0x454A`. The original lookup, copy, readiness and computed-switch instructions execute. File I/O, physical clock effects, hardware table broadcasts, reset states and ISP pixels do not. [T]

The retained BIT15 audit was separately rerun and remains byte-identical: 10,240 checked executions, 61,440 paired-register writes and zero bit-15 changes. This regression protects earlier facts; it does not add pixel-equation evidence. [C]

## 8. CI, integrity and reproduction

Source commit: `137a465706a975c6898eab955d1a9bde041d8f4a`. Workflow and exact tested commit: `ea1c61685e44d8f08d5538acdda20a219cbad488`.

**GitHub Actions run `35512146381` succeeded.** Artifact ID `10605912881`, `M10R-YBLEND-GAMMAROUTE1A-EVIDENCE`. Downloaded ZIP SHA256:

```text
02fb5708c1aeda883a9e2c001903c12e0231f271414eabcfe3af108fd17c583c
```

The ZIP passed CRC checks and all twelve manifest entries passed size/hash checks. Nine locally present files—including all result/history/instruction evidence and all three tools—are byte-identical to CI. Source and result identifiers:

```text
m10r_yblend_gammaroute1a.py:
efae8aa67ca119f8c4fb4defc7f77af51b11aed1f062b8f61e08e4f0b2a37eda

gammaroute_results.json:
a6d2b75ce5361868c7baa16516ce6e2e0884de8ffdb8599b9029ff4ab9ad7705

execution_history.json:
8debbd393012a2125a9bafa2968e709f41875100150ef076df7a5299480cfd62
```

The first successful canonical local run with all four source hashes was used for the CI comparison; an earlier exploratory run without the source manifest populated is not the canonical evidence. Two temporary-document entries in the broader SDK inventory are absent from the supplied archive; this pass claims verification of its four selected source files, not completeness of that earlier input archive. No firmware or third-party library instructions were patched.

After obtaining the same hash-verified sections and the four pinned SDK files:

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_gammaroute1a.py \
  /path/to/sections /path/to/repository /path/to/sdk/sources results
python3 tools/m10r_yblend_bit15_audit1a.py \
  /path/to/sections --cases 1024 --out results/register_emulation.json
```

The committed workflow fetches and verifies the original firmware using the retained extractor and downloads only the four comparison sources. Its explicit base fetch avoids the prior shallow-checkout provenance failure. The workflow scope check permits only this tool, workflow and the two named research-metadata files, so report persistence does not invalidate later reruns. The earlier run `35511858833` also passed; the subsequent workflow-only scope adjustment did not change the research script or results. Report/result-index persistence is separate from the exact tested commit. The evidence package contains no firmware binary, SDK source, third-party library, photograph or APK.

## 9. Remaining research target

The completed task identifies **upload routing** and rejects an unsupported bypass inference. It does not identify a **pixel-data consumer**. Both that distinction and the cross-revision label boundary must survive the next handoff.

The next discriminating evidence would be a Leica-specific table-sharing/write-control connection, or an explicit hardware signal relationship between the CC0/TONE/YC-derived references and the two Y BLEND ratio inputs. Any proposed equivalent of the SDK's simultaneous-write field needs an original Leica writer and bit interpretation, not an analogy between two one-bit values. A direct table-read/debug-output path would also provide an independent route to evidence.

The Y BLEND pair meanings, input domains, stage placement, denominator, rounding and clipping remain unresolved. The public exact-symbol/specification search in this continuation did not supply an exact M10-R datapath specification. No new SAM7 YC/Y BLEND caller was recovered. Do not treat successful five-way gamma dispatch as recovery of that separate caller.

RENDER1Q + CC1MAP1A + YBLEND1B `k=0.35` and `m10r-capture1b` remain frozen. No new phone captures or installation are needed to reproduce this research pass.

## Source hierarchy

**[F]** Hash-verified `092_IMG-System.bin`, `100_IMG-SAM7.bin` and `074_IMG_Calibration_Data_data_calib_B2Y.bin.bin`, original firmware `M10-R-30.22.23.34-Customer.FW`; hashes are in the tool/results. Original instructions and raw calibration bytes are primary evidence.

**[T]** Committed executable `tools/m10r_yblend_gammaroute1a.py` and `results/gammaroute_results.json`; original-entry tests and independent expected destination/write models.

**[H]** `results/execution_history.json` and `results/original_executed_instructions.txt`; all 105 entry histories and source-anchored instruction evidence.

**[S]** Four hash-pinned related SDK source files identified above and in `sdk_sources`; they establish facts about that port, not automatic Leica equivalence.

**[C]** Downloaded CI manifest, exact source commit, retained audit JSON and `results/ci_provenance.json`. Final report-persistence head is recorded separately from the tested source commit.

**[I]** Explicit inferences and limitations, not newly observed ISP behavior. The preceding YBPATH1A report supplies the conditional tone-control context; it is not replaced by gamma-route results.
