# M10-R Y BLEND CLIPROLE1A
## Same-firmware clipping analogues; positive-limit / negative-magnitude candidate

**Date:** 20 September 2026  
**Repository:** `mwilliams455/M10rCamera`  
**Research branch:** `m10r-yblend-cliprole1a`  
**Base:** `a1a32af288e6c74835c9d3cff7bf0e7f18e35f5a`  
**Source-tool commit:** `4b43cfd78e30f72c1550c1e548d56e8dac7148a4`  
**Exact CI-tested commit:** `6e3823a7f834beb1d3e344381625d57f6f105409`  
**Result:** `PASS_NAMED_CLIP_ANALOGUE_ONLY`  
**Gate-C:** NOT passed. No Y BLEND hardware pixel equation or edge-input routing was recovered.

## 1. Result

The unexplained low-15/full-high-16 packing has now been compared against explicitly named clipping controls inside the **same hash-verified M10-R firmware**, not only a related SDK. Two complete SAM7 routines named `Im_B2Y_Ctrl_RGB_OutClip` and `Im_B2Y_Ctrl_JpegXR_OutClip` use exactly that interleaved packing. Separately, original IMG diagnostics label SUPPRE fields as positive- and negative-direction clips; their corresponding register fields are 15 and 16 bits respectively. [F1–F2; E1–E2]

This provides a same-firmware basis for a **positive-limit / negative-magnitude candidate** for the Y BLEND pairs. It does not establish that candidate as the actual Y BLEND operation. The blocks have different addresses, and no pixel-signal connection between them was demonstrated. In particular, zero-extending a parameter into a diagnostic does not prove how the ASIC interprets its bits.

The two EDGE SYNTHESIS controls normally set to `2` remain unidentified. No new result maps either of them to Y or Yb. The previous dual-consumer patent remains an external hypothesis, not a Leica specification.

No application code, renderer setting, exposure policy, white balance, image-quality option or capture behavior was changed. No APK was built. The final branch-scope and frozen-head checks are retained separately in the evidence package.

## 2. Two explicitly named B2Y clipping routines use the same packing

Addresses in this report are raw extracted-section offsets unless marked MMIO. The routines are bounded separately; adjacent functions are not merged.

| SAM7 routine | Entry | Own-name ADR anchor | Selector 0 first register | Selector 1 first register |
|---|---:|---:|---:|---:|
| RGB_OutClip | `0x4F30E` | `0x4F326` | `0x20022548` | `0x20022580` |
| JpegXR_OutClip | `0x4F414` | `0x4F42C` | `0x20022554` | `0x2002258C` |

Each selected bank contains three paired words at offsets `+0/+4/+8`. The first argument selects bank 0 or 1; the second points to six halfwords. Across both routines and both selectors, original instructions produce:

```python
word = (old & 0x8000) | (low & 0x7fff) | ((high & 0xffff) << 16)
```

This is the same packing contract as the already-established Y BLEND pairs at `0x20020930/34`. It establishes that the encoding is used by functions which Leica's own diagnostics call clipping controls. It does **not** identify each Y BLEND word, prove an inter-block wire, or provide a limiter equation. [F2; E1–E2]

The normal entry paths were executed in full. Their clock helpers alone are substituted. The name guards resolve actual ADR instructions into the original strings, rather than assigning names from the closest string. The existence of these routines is not itself claimed as a newly discovered feature; the contribution here is the executed comparison tied to the named fields.

## 3. Original IMG diagnostics identify the directional field widths

A different firmware block, SUPPRE, provides more explicit per-field names. Its register-programming slice and its diagnostic slice access the same four halfword offsets in the supplied parameter block:

| Source offset | Original diagnostic label | Actual destination |
|---|---|---|
| `+0x10E` | Cb positive direction level clip | `0x20070350`, bits 0–14 |
| `+0x110` | Cr positive direction level clip | `0x20070350`, bits 16–30 |
| `+0x112` | Cb negative direction level clip | `0x20070354`, bits 0–15 |
| `+0x114` | Cr negative direction level clip | `0x20070354`, bits 16–31 |

The table shows bank-index fixture zero. The executed address calculation adds `bank << 16`; both fixture values 0 and 1 were tested. This does not establish a full camera mode enumeration or physical availability of every bank. [F1; E1–E2]

SUPPRE groups the two positive fields into one word and the two negative fields into another. Y BLEND uses interleaved pairs. **Their word addresses, layout and channel labels must not be conflated.** The correspondence is in the directional field widths and default numbers, not proof of identical hardware.

Bounded original slices executed:

```text
Parameter-driven clip programming:  0x110C7E .. 0x110D2A (end exclusive)
Parameter diagnostic arguments:     0x110EF8 .. 0x110F30
Literal-default clip programming:   0x111840 .. 0x1118CC
Literal-default diagnostics:        0x111974 .. 0x111994
```

These are four explicitly bounded slices, not a recovered complete SUPPRE selector/producer chain. The harness supplies entry registers `r4` and `r5`; it does not claim camera-state construction or why a physical capture enters the literal-default path.

### Negative direction does not mean software sign-extension here

The original diagnostic loads at `0x110F18` and `0x110F26` use `LDRH`, not `LDRSH`. They pass the zero-extended halfword as the `%d` argument. For example, one executed fixture supplies `[16384,32767,32768,65535]`; the Cb negative-direction diagnostic receives **32768**, not -32768. The logger hook records the original arguments and then clobbers `r0`, `r1` and `r2` before returning. The remaining original loads still reproduce the subsequent arguments. [E1]

This rules out describing this observed software reporting path as sign-extending the negative field. It does **not** rule out a hardware interpretation of the same bits as a signed endpoint. A parameter may be carried as an unsigned bit pattern even when a later consumer uses signed arithmetic.

## 4. The default numbers match the Y BLEND fallback numbers

The original SUPPRE literal-default slice writes positive fields `0x7FFF` and negative fields `0x8000`. The adjacent original diagnostics explicitly name those values as positive and negative direction clips. Both the written words and the literal labels were executed and checked. [F1; E1]

Separately, the original Y BLEND fallback at `D4480` was rerun and verified to supply low `0x7FFF` and high `0x8000` to each pair while clearing the two six-bit controls. Its independent register identity remains the corrected record `0x0D` contract. This is a numerical and structural comparison, not a recovered call or signal connection to SUPPRE. [F1; E1]

The normal Y BLEND record was freshly re-read from the verified calibration bytes: exactly one record 13, index 146, payload offset `0x131874`, 24 bytes:

```text
[0, 32, 16383, 16383, 16383, 16383]
```

Payload SHA256: `cab40e527bfbe6b8a5cd0450a668f46d5d6569ee8405e89fdf7e1455f1492b50`. This agrees with the preceding producer work and is not claimed as a newly discovered preset. [F3; E1]

## 5. Candidate arithmetic and the boundary on its interpretation

A concrete candidate consistent with the directional-width analogy is:

```python
P = word & 0x7fff
N = (word >> 16) & 0xffff
candidate_output = min(P, max(-N, input_value))
```

Here `N` is a **nonnegative magnitude for the negative-direction limit**. This does not mean the field uses a sign-magnitude bit encoding. There is no assertion that bit 15 is a sign or mode flag; its known preservation is unchanged.

Under this candidate only:

| Configuration | Candidate interval |
|---|---|
| Normal pair `0x3FFF / 0x3FFF` | `[-16383, +16383]` |
| Fallback pair `0x7FFF / 0x8000` | `[-32768, +32767]` |

The standalone model checks that the latter is the identity over an **assumed** signed-16 input domain. This is a mathematical test of the declared candidate, not firmware pixel execution. Neither that input domain nor the placement of a limiter before or after blending is established.

This explains why two equal positive stored numbers need not define a collapsed interval. However, ordinary signed-endpoint interpretations are not globally falsified: activation may differ, fields may be ignored in a mode, or the hardware encoding may differ. If both values were interpreted as active, direct equal interval endpoints, the interval would collapse; that is a conditional algebraic observation, not an observed M10-R failure.

**Evidence status:** same-firmware clipping analogy is established; positive/negative-magnitude interpretation for Y BLEND is supported as a candidate; actual Y BLEND pair semantics, channel assignment, activation and pixel arithmetic remain unresolved.

## 6. Executions and checks

The new script uses 128 deterministic parameter sets, including eight boundary patterns followed by pseudorandom halfwords. Seed: `0xC11F2026`.

| Check group | Executed entries |
|---|---:|
| Complete SAM7 RGB and JPEG-XR clip routines, both selectors | 512 |
| Bounded SUPPRE programming and diagnostic slices, including literal defaults | 516 |
| Original IMG Y BLEND fallback comparison | 1 |

These categories must stay separate: 516 bounded slices are not 516 complete firmware call chains. The suite does not simulate any ISP pixels.

All comparisons passed over the complete modeled windows: 16,384 bytes for the SAM7 register tests and 131,072 bytes for SUPPRE. Observed writes were 3,072 in the SAM7 window and 1,032 in the SUPPRE window. There were zero monitored firmware writes to the supplied parameter memory. The source offsets, widths, values and diagnostic arguments were checked, including synthetic values outside the positive field width. Such values are interventions, not actual Leica presets. [E1]

Only SAM7 clock helpers `0x4D1B4/0x4D118` and IMG logger `0x140154` are substituted. The tests do not model physical clocks, MMIO side effects, camera mode selection, sensor input or actual clipping hardware.

The retained BIT15 audit was separately rerun. Its 10,240 checks passed, and its result JSON remains byte-identical to the retained hash `50eb66d4091436c76bd90d9fff94d89214c945089e4b27e95d5cba7792e747e3`. This regression is not additional pixel validation.

## 7. Independent CI and integrity

GitHub Actions run **35517761570** succeeded at exact commit **6e3823a7f834beb1d3e344381625d57f6f105409**. Artifact **10607371972**, `M10R-YBLEND-CLIPROLE1A-EVIDENCE`, was downloaded and verified. [E3]

```text
CI ZIP SHA256:
79175606e7de463548b1193970e87cf4bfa41aef3328ad0b5fe0424292fe8dd6

Research script SHA256:
569fa810aebefa1a94ee750e6e90a1411a4e66a3e57bfa89eedc205bf49080e4

cliprole_results.json SHA256:
dcd88257979b44de4ee7b577773b60a9338322155d0b83fe911a7a38ce15fbb1
```

The ZIP CRC check and all 11 manifest entries passed. Eight files match local execution byte-for-byte: both source tools, full result JSON, all execution histories, instruction anchors, both stdout files and the retained regression JSON. The 768 history objects group complete SAM7 entries or paired SUPPRE programming/diagnostic runs; they are not the entry count.

The tested diff contains only the new tool and workflow. Later report/index persistence commits are not the exact tested commit. The final head and scope are recorded in `results/ci_provenance.json` in the downloadable evidence package.

## 8. Search limitations and next work

Public exact-symbol searches did not supply a usable old-revision B2Y definition for the two edge controls or the Y BLEND pairs. Some attempted older-report retrievals failed; no conclusions here rely on the unread files. The new findings above rely on verified local firmware bytes and original-instruction execution, not on those failed lookups or on an external patent.

This pass narrows the paired-field hypothesis, not the main/edge routing. The next useful evidence is an actual parameter producer or pixel consumer that establishes **how the high-half field is interpreted**, or a matching original B2Y definition with unambiguous field semantics. A negative-field arithmetic use, a hardware output test with unequal positive/negative limits, or an exact-revision specification could discriminate the candidate. Another store-mask match alone would not.

The two normal value-2 edge controls, the two six-bit Y BLEND control encodings, their signals, the blend denominator and polarity, stage placement, rounding and clipping remain open. Keep these unknowns explicit. Do not silently turn this candidate into a renderer change or call Gate-C passed.

## 9. Reproduction and source index

```bash
python3 -m pip install capstone==5.0.3 unicorn==2.1.3
python3 tools/m10r_yblend_cliprole1a.py /path/to/verified/sections results --cases 128
python3 tools/m10r_yblend_bit15_audit1a.py /path/to/verified/sections \
  --cases 1024 --out results/register_emulation.json
```

Keep both tools together and do not disable assertions. The workflow reuses the existing verified firmware decoder and checks the original and unpacked hashes before section extraction. The local run used the original pinned Capstone and Unicorn files from the retained research-input wheels.

**[F1]** `092_IMG-System.bin`, SHA256 `53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4`.

**[F2]** `100_IMG-SAM7.bin`, SHA256 `c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae`.

**[F3]** `074_IMG_Calibration_Data_data_calib_B2Y.bin.bin`, SHA256 `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b`.

**[E1]** `results/cliprole_results.json` and `results/execution_histories.json`.

**[E2]** `results/original_instruction_anchors.txt` and the executable tool's identity guards.

**[E3]** `results/ci_provenance.json`, downloaded CI manifest, source commit and changed-path record.

The downloadable package contains the report, reproducible tools, workflow, results, histories, instruction anchors, CI provenance and checksum manifest. It intentionally excludes firmware binaries, third-party libraries, images and APKs. Frozen reference heads remain RENDER1Q `a66b73cc339ebcb863d345c7a9ee7ff631fc86f0` and capture `3b1e86b5055a21b548d56b23bd47f9dc66c57012`; final live rechecks are recorded in the package provenance.
