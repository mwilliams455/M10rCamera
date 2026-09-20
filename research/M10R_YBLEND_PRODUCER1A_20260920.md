# M10-R Y BLEND PRODUCER1A — 20 September 2026

## Result and boundary

**The normal record has been freshly re-extracted, and the actual IMG producer path has been executed through the original selector, record lookup, string comparison and D4480 register programmer.** The new suite passes **1,792 complete producer-path cases**. It establishes a fixed, empty-key calibration selection on this IMG path, not a scene-dependent calculation of the six Y BLEND fields.

This is a new producer constraint, not the missing ISP pixel equation. **Gate-C remains NOT passed.** Constant configuration can still govern signal-dependent hardware behavior. No change to RENDER1Q, CC1MAP1A, YBLEND1B `k=0.35`, the YC2A matrix, exposure, white balance, image quality or `m10r-capture1b` is authorized by this work.

Continue using the v2.78 identities: record `0x0C` / `D4570` = YC CONVERSION; record `0x0D` / `D4480` = Y BLEND; record `0x04` / `D42E0` = WBCLIPLEVEL. This work retained and executed the original-instruction identity guards.

## 1. Starting point and reproduction

Repository: `mwilliams455/M10rCamera`.

The live audit branch was read and matched the handoff head `f9f67f5e196ac0e6c6a737432b9c63d3f1678ea7`. The new isolated branch is `m10r-yblend-producer1a`, created from that exact commit. Bootstrap commit: `4693806eda84d79e0b98d7fedab6c2cf841bee4e`. The executable producer suite and evidence-only workflow were committed together at `f55f355df23e0c82edbefd8fbc7577631e5336bf`.

The initial local environment could not fetch the firmware or dependencies. Bootstrap Actions run `35497612885` therefore used the repository's existing download/decode recipe, verified the original and unpacked SHA256 values, reran BIT15 AUDIT1A and reran the existing v086 extractor. Its artifact `10600587953` was retrieved for local analysis. All 226 manifest entries were checked. The local BIT15 rerun was byte-identical to the bootstrap CI JSON and the retained earlier audit JSON: 10,240 checked executions, 61,440 paired-register writes, zero bit-15 mutations.

The bootstrap artifact contained analysis inputs. The subsequent producer-evidence workflow does **not** include firmware binaries, third-party libraries or an APK. Artifact names do not determine access control; repository permissions apply.

Producer Actions run **35498082473 succeeded** at commit `f55f355df23e0c82edbefd8fbc7577631e5336bf`. Downloaded artifact `10600838604` has SHA256 `a2176532bf6916160ad59a8c5be73668c957fac80661fc865d7e13f3f4b43e6d`. All 12 manifest entries passed validation. The committed source, producer JSON, instruction anchors, v086 extraction and old audit results are byte-identical between local execution and CI. The separate `ci_provenance.json` retains these checks. Report-persistence commits are not the exact CI-tested commit.

## 2. Independent raw calibration extraction: the disclosed v2.78 gap is closed

The original version remains `M10-R-30.22.23.34-Customer.FW`.

| Item | Verified value |
|---|---|
| Calibration section | `074_IMG_Calibration_Data_data_calib_B2Y.bin.bin` |
| Section size | `0x134FB0` bytes |
| Section SHA256 | `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b` |
| Number of records | 168 |
| Record-0x0D occurrences | Exactly one in this section |
| Zero-based record index | 146 |
| Record header offset | `0x60634` |
| Payload offset | `0x131874` |
| Payload size | `0x18` = 24 bytes |
| Declared lookup keys | One, the empty string |
| Decoding | Six little-endian uint32 slots |

Raw payload:

```text
00000000 20000000 ff3f0000 ff3f0000 ff3f0000 ff3f0000
```

Decoded:

```text
[0, 32, 16383, 16383, 16383, 16383]
```

Payload SHA256:

```text
cab40e527bfbe6b8a5cd0450a668f46d5d6569ee8405e89fdf7e1455f1492b50
```

The record header's first 16 bytes are `0d000000e0290c001800000001000000`. The existing `tools/m10r_ycc_calib_compact_v086.py` was invoked using its actual positional interface, and the new tool independently inspected all parsed occurrences, header bytes, keys and payload bytes.

YC CONVERSION record `0x0C` was also re-extracted: zero-based index 145, header `0x5FBA4`, payload `0x131834`, size 60 bytes, one empty key. Its coefficient row remains `1224/2403/469`. This verification is not a matrix change.

All offsets above are within the extracted section, including its four-byte prefix. The emulated calibration loader view starts after that prefix. The test's chosen runtime payload address is therefore `CALIB + 0x131874 - 4`; it is not a recovered physical runtime address.

## 3. New source-anchored producer map

The directly observed chain is:

```text
IMG central setup call at 0x155094
    -> selector 0x154E18
    -> lookup 0x1A0FC4("B2Y.bin", record=0x0D, key="")
    -> returned pointer to the record payload
    -> D4480(payload_pointer, fallback=0)
    -> 0x2002092C / 0x20020930 / 0x20020934
```

The central call's preceding instructions pass a parameter pointer derived from `r4+0x2C` and a second argument from `r5`. This is configuration-call sequencing, not ISP pixel-stage order.

### The selector's first argument does not supply the six field values

At `0x154E1C`, the selector saves its first argument into `r7`. The bounded body `0x154E18..0x154E6E` does not subsequently consume that saved value or dereference the argument. Instead:

- `0x154E34..0x154E3A` copies a zero byte from static offset `0x154E74` into the lookup-key buffer;
- `0x154E48` selects record ID 13;
- `0x154E4A` addresses the actual `B2Y.bin` string;
- `0x154E4C` invokes the original record lookup;
- `0x154E50` preserves the returned pointer;
- `0x154E64..0x154E68` passes that pointer and the fallback flag directly to D4480.

No payload-field arithmetic occurs between the successful lookup and the driver call. Executions with eight first-argument values, including null, unaligned and unmapped values, support the static def-use result. The monitored mapped argument block had zero reads.

**Constraint:** the six controls in this normal calibration path are not calculated from the caller's scene/settings parameter block by this selector. This is not a claim that every firmware path, calibration-memory writer or hardware operation is scene-independent.

### The selector's second argument is a cache-control input here

The byte at `0x408CEDBF` is tested against 1 at `0x154E24..0x154E28`. Only when it equals 1 and the second argument also equals 1 does execution return without lookup or programming (`0x154E2A..0x154E2C`).

Otherwise the selector attempts the empty-key record lookup. On success it leaves the cache byte set to 1. On failure it clears the byte, sets the driver's fallback flag to 1 and passes a null payload pointer. The original driver's already-audited fallback then supplies its fallback controls and pairs.

| Software outcome | Observed operation | Photographic interpretation |
|---|---|---|
| Successful normal lookup | Program record values, including controls `(0,32)` | Pixel effect unresolved |
| Failed lookup | Program the known fallback, including controls `(0,0)` | Not proven to be an ISP enable/bypass mode |
| Cache=1 and selector argument 1=1 | No lookup, no driver call, no register writes | Retains prior register state; **not** a demonstrated hardware bypass |

The selector's second argument must not be relabeled as a blend strength. It is also distinct from D4480's second argument, which selects normal versus fallback programming.

## 4. The actual field reads are now linked to the raw payload

| Field | Source slot offset | Driver load | Read width | Controlled destination |
|---|---:|---:|---:|---|
| Control 0 | `+0x00` | `0xD448E` | 1 byte | `0x2002092C`, bits 0–5 |
| Control 1 | `+0x04` | `0xD44A4` | 4 bytes | `0x2002092C`, bits 8–13 |
| Pair 0 low payload | `+0x08` | `0xD44BC` | 2 bytes | `0x20020930`, bits 0–14 |
| Pair 0 high payload | `+0x0C` | `0xD44D0` | 2 bytes | `0x20020930`, bits 16–31 |
| Pair 1 low payload | `+0x10` | `0xD44E6` | 2 bytes | `0x20020934`, bits 0–14 |
| Pair 1 high payload | `+0x14` | `0xD44FA` | 2 bytes | `0x20020934`, bits 16–31 |

This distinguishes the storage format (six four-byte slots) from actual load widths. The whole-chain tests observed these exact six source accesses and matched the existing packing formulas. The four paired payload fields still do not have recovered endpoint, signedness or channel semantics. Preserved bit 15 remains preserved, not a discovered mode flag.

## 5. Executed tests: new coverage versus the old audit

Canonical tool: `tools/m10r_yblend_producer1a.py`.

Original instructions executed together:

```text
selector       0x154E18
record lookup  0x1A0FC4
string compare 0x4F164
driver         0xD4480
```

Only the file-registry resolver `0x1A0C80` and diagnostic logger `0x140154` are stubbed. The resolver returns a synthetic descriptor pointing at the supplied verified calibration bytes, or null for the missing-file test. Descriptor field `+0x208` is read by the original lookup. Storage I/O and calibration loading are not emulated.

The suite uses seed `0xD44802026`, randomized stack and MMIO state, and:

- 768 cases: six source scenarios × four cache values × four second-argument values × eight first-argument values;
- 1,024 full-uint32 payload interventions, including boundary values, passed through the original lookup and programmer.

The six scenarios are the original source plus synthetic missing-file, missing-record-ID, mismatching-key, zero-key-count and invalid-magic controls. They are deliberate tests, not observed camera failures or additional Leica presets.

| Result | Count |
|---|---:|
| Complete producer executions | **1,792** |
| Normal programming outcomes | 1,144 |
| Fallback programming outcomes | 600 |
| Cached no-update outcomes | 48 |
| Writes to all three watched registers | **10,464** |
| Paired-word writes within that total | 6,976 |
| Bit-15 changes in paired words | **0** |
| Reads from the supplied argument block | **0** |
| Calibration-memory writes by original executed firmware | **0** |

Every case compares the complete modeled `0x4000`-byte MMIO window against the independent packing model, verifies the cache result and checks direct payload-pointer forwarding. Source-memory preservation is checked separately. These results extend the earlier programmer audit; they must not be counted as ISP pixel validation.

## 6. SAM7 producer: investigated, but not resolved

The actual programmer remains `0x51DA6`, with the known `<15H2B4H` structure. A targeted scan of SAM7 immediate Thumb/ARM calls did not find a call to that exact entry. Searching 102 extracted `.bin` sections for four conventional pointer encodings also found no hits:

```text
0x00051DA6  0x00051DA7  0x43051DA2  0x43051DA3
```

This is a bounded negative result. Computed pointers, relocations, indirect dispatch, alternative entry paths and different encodings are not exhaustively covered. It does **not** prove the function is unused or that the compact producer does not exist. The producer/caller of the actual SAM7 compact structure remains unresolved.

The earlier v086 compacting script is an analysis-side reconstruction of register-equivalent structure packing. It must not be described as a recovered firmware-side constructor.

## 7. What changed in the investigation

**Closed:** fresh normal record-0x0D extraction, its key and uniqueness in this calibration section, the bounded IMG selector's inputs, direct source-pointer forwarding, the selector's cache/normal/fallback behavior, and the original driver reads of each source field.

**New model constraint:** a proposed normal-path implementation cannot justify a scene-computed coefficient by attributing it to this IMG selector. Any such dependence would need evidence from another producer, modified calibration memory or the hardware datapath itself.

**Still open:** meanings of both six-bit controls; the paired-field semantics; source signals; scaling and denominator; stage placement; signedness where relevant; rounding; clipping; the actual SAM7 compact-structure producer; and the actual Y BLEND per-pixel equation. Neither value 32 nor this fixed-record result maps the firmware to `k=0.35`.

## 8. Next research target

The next producer-side question is no longer whether `0x154E18` computes the six fields: its bounded normal path is now traced. Further producer work should target a concrete writer to the loaded calibration payload or an actual indirect/relocated caller of SAM7 `0x51DA6`, rather than repeat exact-literal scans without a new pointer-provenance lead.

For the pixel equation, require evidence identifying the two controls' signal roles and the paired fields' effects. Existing image diagnostics can reject candidate behavior, but they cannot establish an ASIC equation. A public exact-symbol search during this continuation supplied no usable specification, so no external semantics were imported.

Keep output-neutral research separate from renderer promotion. No additional phone captures or APK installation are needed to reproduce this completed producer suite.

## 9. Reproduction and evidence files

From the research branch, after the existing workflow has produced the verified sections:

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_bit15_audit1a.py /path/to/sections --cases 1024 --out audit.json
python3 tools/m10r_ycc_calib_compact_v086.py /path/to/sections .
python3 tools/m10r_yblend_producer1a.py /path/to/sections . results --stress-cases 1024
```

Do not disable assertions. The local execution used Python 3.13.5 with the original Unicorn 2.1.3 Python/ctypes files and shared library from the CI wheel; its original audit result matched CI. The independently executed producer CI comparison is recorded separately.

Source hierarchy for this report: verified firmware bytes and original-instruction execution first; the prior v2.78 handoff for frozen boundaries; source-anchored deductions from the tested code; explicitly marked limitations and proposed next work. The evidence ZIP includes the report, machine-readable results, instruction anchors, reproducible tools, v086 extraction output, audit rerun and checksum manifest. It excludes firmware binaries, APKs, photographs and third-party libraries.
