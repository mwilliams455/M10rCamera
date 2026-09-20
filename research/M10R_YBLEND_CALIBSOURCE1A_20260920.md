# M10-R Y BLEND CALIBSOURCE1A — 20 September 2026

## Result and decision

**A concrete calibration-source replacement path is now recovered and executed. The original IMG resolver can reuse a loaded source, select a matching NOR-cached source, or request `/data/calib/B2Y.bin` from the filesystem. The original registration routine can replace the complete source descriptor. That replacement does not itself clear Y BLEND's separate register-programming cache.**

This extends PRODUCER1A by removing its file-resolver stub, identifying real source-pointer writers, and testing replacement/invalidation across both caches. **544 original-entry executions pass locally and in GitHub Actions.** A separate, bounded SAM7 startup-copy test excludes one specific relocation route, with a disclosed four-byte source-tail fixture.

These are software configuration results. **Gate-C remains NOT passed:** no Y BLEND per-pixel equation, source-signal roles, denominator, paired-field meanings, rounding, clipping or hardware stage order has been recovered. No renderer, exposure, white balance, tone, matrix, `k=0.35`, capture code or APK was changed.

## 1. Verified starting point and evidence hierarchy

Repository: `mwilliams455/M10rCamera`.

The live PRODUCER1A branch was read twice and matched `13799098ba5112f85fa48073b5e8d6f348d1cbaa`. The isolated branch `m10r-yblend-calibsource1a` was created from that exact commit. Its executable tool and workflow were committed together at:

```text
80fb609f3decfc8b5d1b3a1e9ce9e1ee94abd731
```

The preceding bootstrap artifact `10600587953` supplied verified extracted firmware sections and pinned research dependencies. All 226 entries in its manifest passed byte-length and SHA256 checks. The new source tests retain the original-instruction identity guards and the original calibration payload checks from the preceding work.

Evidence hierarchy: hash-verified firmware bytes and original-instruction execution; deterministic machine results; source-anchored deductions; separately identified synthetic interventions and unresolved questions. No external hardware specification was found that justified importing Y BLEND pixel semantics.

The canonical identities remain: record `0x0D` / IMG `D4480` = Y BLEND; `0x0C` / `D4570` = YC CONVERSION; `0x04` / `D42E0` = WBCLIPLEVEL. The normal record-0x0D payload remains `[0,32,16383,16383,16383,16383]`. This continuation does not reopen those mappings.

Address convention: IMG code locations below are raw section offsets. Runtime addresses, globals and MMIO are explicitly identified. The IMG/SAM7 virtual views use their respective `0x42000000`/`0x43000000` bases after the extracted four-byte section prefix.

## 2. Original calibration resolver: three source routes

PRODUCER1A executed the selector, record lookup and driver, but stubbed resolver `0x1A0C80`. CALIBSOURCE1A executes that resolver and its NOR metadata search, base helper and filesystem-loading wrapper.

The tested chain is:

```text
selector 0x154E18
  -> record lookup 0x1A0FC4 (record 0x0D, empty key)
     -> file resolver 0x1A0C80 (B2Y.bin)
        -> existing source pointer, or matching NOR source, or filesystem read
     -> original record lookup and payload pointer
  -> D4480
  -> 0x2002092C / 0x20020930 / 0x20020934
```

| Resolver condition | Executed behavior | Concrete pointer writer |
|---|---|---|
| Matching registered descriptor already has nonzero `+0x208` | Reuses that loaded source; no NOR or file read is needed. | None on this reuse path. |
| Pointer is zero and the NOR-cache metadata matches | Uses the cached calibration region. | IMG `0x1A0D66` installs the source pointer at descriptor `+0x208`. |
| Pointer is zero and cache filename, offset or region size mismatches | Constructs `/data/calib/B2Y.bin`, calls the original allocation/read wrapper, then installs the returned allocation. | IMG `0x1A0DC0` stores the source pointer at descriptor `+0x208`. |
| Registry is empty or lacks the requested name | Lookup returns no source and the selector takes the established driver fallback. | No successful source-pointer installation. |

The filesystem read and heap operations are declared test stubs. The returned file bytes are deliberate fixtures. This establishes which original code paths request and consume those bytes, not that any particular physical camera loaded a different calibration file.

The tested paths do not calculate new values for the six Y BLEND fields. They select the source whose record is subsequently read. A fixed record in the supplied firmware remains a fixed record; the presence of a replacement mechanism is not evidence of scene-adaptive coefficient generation.

## 3. Recovered NOR metadata and conditional address calculation

The original IMG catalog contains a 512-byte entry at raw offset `0x7F641C`, virtual address `0x427F6418`:

| Original field | Value |
|---|---|
| Path | `/data/calib/B2Y.bin` |
| Region offset, uint32 at `+504` | `0x00400000` |
| Region size, uint32 at `+508` | `0x00300000` |

The region size is a reserved/cache-region extent, **not the length of record 0x0D and not a measured size of an installed file**. The full metadata bytes and hash are in `results/calibsource_results.json`.

Original metadata lookup `0x142508` and base helper `0x13DE50` execute. The base helper initializes runtime global `0x408EEBC0` to `0x02000000` when it is zero. Cache metadata is checked at:

```text
NOR base + region offset + region size - 0x200
```

Under that default base, the implied calibration-data address is `0x02400000` and the metadata address is `0x026FFE00`. Applying the unchanged record-0x0D payload offset in the loaded view (`0x131870`) gives `0x02531870`.

**These are conditional address calculations, verified using constructed matching cache contents—not a NOR dump or observed real-camera runtime pointer.** The supplied extracted calibration section includes a four-byte prefix; the loaded view used here starts after it. The matching cache metadata fixture was copied from the original catalog entry; it is not represented as a captured cache footer.

## 4. Concrete source-descriptor replacement

The registry uses runtime globals:

```text
0x408D5024 : descriptor-table pointer
0x408D5028 : entry count
entry size: 0x210 bytes
name:       entry + 0x008
source ptr: entry + 0x208
```

Original routine `0x1A270C` searches using `0x1A29D4`. When it finds a matching entry, it copies the entire `0x210`-byte supplied descriptor over that entry. The copy call at `0x1A2756` executes original ARM helper `0x4F2F0`. Because the copied range includes `+0x208`, this is a concrete original-code writer capable of replacing or clearing the loaded-source pointer.

The no-match branch grows the table through the declared reallocation stub, updates registry state and executes the same original descriptor copy. Tests verify the existing entry remains intact and the newly appended descriptor is subsequently consumed by the original selector/resolver.

This is **whole-descriptor replacement, not a discovered field-specific writer into the six existing payload slots**. Replacement descriptors and alternative field values in the test are explicit interventions, not discovered Leica presets. Filename-collision rules, allocation failures and concurrent registry changes were not exhaustively tested.

Static caller anchors provide directions for further tracing: `0x1A2BDE` calls the registration routine from a calibration-directory enumeration slice; `0x1BAA6A` calls it from a file-write-related calibration registration slice. Their bounded instructions are retained. The surrounding enumeration and file-write handlers were **not** executed end-to-end, and these anchors do not show scene-dependent calculation of Y BLEND values.

## 5. Two independent cache layers: executable state transition

The file descriptor's loaded-source pointer and Y BLEND's register-update cache are different state. Register-update cache byte `0x408CEDBF` is not cleared by the tested descriptor replacement routine.

The following sequence was executed for 32 deterministic rounds:

1. Program the original source, setting the selector cache to 1.
2. Replace the registered descriptor with one pointing at deliberately altered calibration data.
3. Call the selector with its second argument equal to 1: it skips lookup and programming, retaining the prior registers.
4. Call with the second argument equal to 0: it consumes the replacement source and programs the altered values.
5. Replace the descriptor again, this time setting its source pointer to zero.
6. Call with the second argument equal to 1: it again skips programming, retaining the last register values.
7. Call with the second argument equal to 0: the original resolver selects the constructed matching NOR source and restores the original record values.

Every step checks the complete modeled MMIO window against the independently expressed packing model. Registration steps additionally verify the entire descriptor and count; cached steps verify that neither resolver nor driver executes. No observed original instruction modifies the monitored source payload memory.

**Constraint:** replacing or invalidating a calibration-source descriptor is not equivalent to forcing a Y BLEND register update. Conversely, retaining old register contents after replacement is not evidence that the replacement data were transformed or ignored by hardware. This is configuration-state behavior, not a pixel-processing equation.

## 6. Execution counts and test limits

Canonical tool: `tools/m10r_yblend_calibsource1a.py`. Seed: `0xCA11B2026`.

| Group | Original-entry executions |
|---|---:|
| Eight source conditions across 32 rounds | 256 |
| Seven-step replacement/invalidation sequences across 32 rounds | 224 |
| Descriptor append followed by selection, across 32 rounds | 64 |
| **Total** | **544** |

Within that total: **448 selector entries and 96 registration entries**. The 64 dual-cache transition phases and 32 append scenarios are subcounts, not additional executions. Boundary and random uint32 payload interventions, randomized stack/register state, source-pointer forwarding and full modeled register-window checks are included.

```text
status: PASS_CALIBRATION_SOURCE_SOFTWARE_ONLY
source-memory writes by executed original firmware: 0
observed paired-word bit-15 changes:                0
Gate-C:                                           NOT passed
```

Original code executed includes selector `0x154E18`, resolver `0x1A0C80`, NOR metadata lookup `0x142508`, NOR base helper `0x13DE50`, file allocation/read wrapper `0x1A3128`, record lookup `0x1A0FC4`, registration `0x1A270C`, index lookup `0x1A29D4`, copy `0x4F2F0`, string helpers and driver `0xD4480`.

The stubs are path allocator `0x14254C`, payload allocator `0x143170`, registry reallocator `0x147038` (in-place fixture), file I/O `0x1A2154` (supplies declared bytes and a full-read result), and logger `0x140154`. External fixture writes are not original firmware-instruction writes. A zero source-write count does not exclude external writers, other threads or unexecuted paths.

The preceding BIT15 audit was also actually rerun, locally and in CI: **10,240 checks, 61,440 paired-register writes, zero bit-15 changes**. Its JSON is byte-identical to the retained prior result, SHA256 `50eb66d4091436c76bd90d9fff94d89214c945089e4b27e95d5cba7792e747e3`. This remains a separate register audit, not additional new source-route coverage.

## 7. SAM7: one relocation explanation excluded, with a disclosed input gap

Instead of repeating the prior exact-pointer search, this continuation inspected and executed the original ARM startup scatter loader, entering at virtual `0x43000F20` and stopping at `0x430010A0` before the next startup stage. The six entries at raw `0x103748..0x1037A8` specify four copy regions and two zero-initialized regions.

| Operation | Source | Destination | Length |
|---|---:|---:|---:|
| Copy | `0x431038D8` | `0x00000000` | `0x2F8` |
| Copy | `0x43103BD0` | `0x43400000` | `0x1194` |
| Copy | `0x43104D64` | `0x43401194` | `0x80` |
| Copy | `0x43104DE4` | `0x43800000` | `0x1480` |
| Zero | Not consumed | `0x43401214` | `0x2B245C` |
| Zero | Not consumed | `0x43801480` | `0x72910` |

The YC/Y BLEND programmer at raw `0x51DA6` maps to virtual `0x43051DA2`. **None of the four copy-source ranges contains it.** Therefore this specific startup table does not generate a relocated copy of the programmer that would explain the earlier missing direct caller. This does not exclude later copies, indirect dispatch, alternate entries, pointer arithmetic or other mappings, and does not establish dead code.

**Input gap:** with the documented four-byte-prefix mapping, the final initialized source region extends four bytes beyond the supplied SAM7 section. The harness explicitly supplies `12 34 AB CD` as synthetic tail bytes and records that intervention. It does not silently call them firmware bytes or assume they are zero. Destination checks include this declared fixture. The status is `PASS_SCATTER_WITH_DECLARED_4BYTE_TAIL_FIXTURE`, not successful camera-boot validation. The range-exclusion finding above comes from the table itself and does not depend on the missing bytes' values.

## 8. Independent CI verification and artifact provenance

GitHub Actions run **35500379167**, job **106050992634**, completed successfully at source commit **80fb609f3decfc8b5d1b3a1e9ce9e1ee94abd731**. Original firmware and unpacked-image hashes were verified before extraction. The new suite and old audit both ran; no APK build was part of this job.

```text
Artifact:    M10R-YBLEND-CALIBSOURCE1A-EVIDENCE
Artifact ID: 10602540215
ZIP SHA256:  f7f90cc12b7208a9837c69353d308f7dd5e85638084e90ece3dbdb6189d07285
Tool SHA256: 48da32bae48834ffbf5adb0123262288e672e5dc8f30ac1079458b2906d9d5a1
```

All **12 CI-manifest entries** passed length/hash verification; ZIP CRC checks passed. The canonical source, full result JSON, 544-entry execution history, instruction evidence, stdout and earlier audit result are byte-identical between local execution and downloaded CI evidence. Local Python was 3.13.5; CI Python was 3.12.3; both used original Capstone 5.0.3 and Unicorn 2.1.3 components.

Report/result-index persistence is a later commit, not the exact CI-tested source commit. `results/ci_provenance.json` and the final repository-state record preserve that distinction. The repository result index is a compact index of the full artifact results, not a second execution or a replacement for the per-execution history.

## 9. Frozen branches and practical consequence

Live reads during this continuation still returned:

```text
m10r-render1q-yblend1b-k035
  a66b73cc339ebcb863d345c7a9ee7ff631fc86f0
m10r-capture1b
  3b1e86b5055a21b548d56b23bd47f9dc66c57012
```

Only isolated research/CI files are added. No photographic behavior is promoted. Existing approximations must remain described as approximations. There is no reason to install an APK or capture more phone photographs to reproduce this completed source-path suite.

The new result narrows an actual uncertainty: an alternate source can enter through a concrete descriptor writer, but the selector's cached no-update path may retain prior registers until forced. It does **not** explain the visual effect of the two controls or the paired fields, and does not justify changing `k=0.35`.

## 10. Next research target

Do not spend another pass merely re-proving source reuse, record uniqueness or paired-register packing. The IMG configuration-source path is now constrained enough to distinguish source replacement from arithmetic transformation.

A further producer claim needs a concrete field-specific calculation or an actual caller supplying the SAM7 compact structure. For SAM7, this startup-copy table is no longer a useful missing-caller explanation; prioritize evidence of indirect dispatch, alternative entry flow or a demonstrable later relocation. For the pixel equation, require evidence of signal roles and the effects of both controls and both pairs. A calibration file-write path alone is not that evidence.

Keep scene tests as candidate evaluation, not ASIC proof. Keep the photographic and capture branches unchanged unless a separate promotion is justified.

## 11. Reproduction and packaged sources

With the verified sections produced by the committed workflow:

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_bit15_audit1a.py /path/to/sections --cases 1024 --out results/audit_rerun.json
python3 tools/m10r_yblend_calibsource1a.py /path/to/sections . results --rounds 32
```

Do not use optimized Python. The tool verifies the retained audit-script hash, section hashes, identity guards and normal payload before executing. Firmware remains `M10-R-30.22.23.34-Customer.FW`; original SHA256 is `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`; unpacked SHA256 is `859c936b6ac8efe0bc4ce7f05623013644fc5d8aee3c6835f09860f452adc2e0`.

The evidence package contains this report, canonical tools, raw machine results, all 544 execution histories, original-instruction excerpts, audit rerun, CI provenance and checksum manifests. It excludes firmware binaries, dependency wheels, APKs and photographs. Prior PRODUCER1A context is separately labeled. Artifact names do not determine access permissions.
