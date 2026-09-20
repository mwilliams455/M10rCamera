# M10-R Y BLEND SDKBRIDGE1A — Y/Yb source lead and revision boundary

Date: 20 September 2026.
Research branch: `m10r-yblend-sdkbridge1a`.
Base: `dfb013bf70c4b1c6758ce10fb89e887f8a2ba3b2` (CALIBSOURCE1A).
CI-tested source: `e15e6fb94e83db01b2714eb038e3ac9fd97e0b56`.

## Result

A public R2Y SDK port supplies a specific candidate meaning for the two six-bit controls: luminance **Y** and **Yb** blend ratios. Its bitfield layout, assignment order and grouping with YC conversion correspond to the original M10-R control programmers. Its full ABI does not match M10-R, and no actual M10-R pixel equation or SAM7 structure caller was recovered. **Gate-C remains NOT passed.** This is a source-backed hypothesis, not an exact-hardware claim.

## Public source and anchors

Repository: `ZMlogicL/companyTask`.
Pinned commit: `f5fc84bd5c475f4c15017b7bff749f81c3618287`.

This is a third-party R2Y code port, not a Leica source release or authenticated documentation for the M10-R ISP revision. Six files are hash-verified by `tools/m10r_yblend_sdkbridge1a.py`. Their complete URLs, Git blob IDs, sizes, SHA256 values and line anchors are in the CI artifact's `results/sdkbridge_results.json`. External SDK code is read, not compiled or executed.

| Source | Exact repository path | Relevant lines |
|---|---|---|
| S1 | `MILB_API/Project/ImageMacro/src/imr2yctrl2.h` | 127–129: Yb gamma-table control; 146–152: YC structure and ratio descriptions |
| S2 | `MILB_API/MILB_Header/include/Image/fr2y6a.h` | 1038–1047: control-word address and bitfields |
| S3 | `MILB_API/Project/ImageMacro/src/imr2yctrl2.c` | 271–272: register-DMA assignments; 775–811: direct programmer, assignments at 805–806 |
| S4 | `MILB_API/Project/ImageMacro/src/imr2yctrl.h` | 442–444: separate Yb tone enable; 453–455: TCYC/CCYC source distinction |
| S5 | `MILB_API/Project/ImageMacro/src/imr2y3.h` | 1105–1123: YC sample, controls `(0,0)` |
| S6 | `MILB_API/Project/ComponentTest/src/ctimr2yclassh.c` | 775–776: raw all-ones control register test |

S1 names `YYBLND` as the luminance Y blend ratio and `YBBLND` as the luminance Yb blend ratio, each with documented range 0–32. S2 places them at bits 0–5 and 8–13. S3 copies the corresponding parameters directly into those fields in both programming routes.

S4 distinguishes Y selected through TCYC from Yb selected through CCYC and permits tone processing of Yb separately from RGB. S1 exposes a Yb gamma-table control. These are source facts about that SDK. They motivate investigating a corresponding M10-R second-luminance path; they do not prove that mapping.

## Candidate map and the mismatches that prevent exact transplantation

| M10-R item | Corresponding SDK item | Evidence level |
|---|---|---|
| IMG first slot / SAM7 byte +0x1E -> `0x2002092C[5:0]` | `YYBLND`, Y blend ratio | Register-layout match; M10-R signal role remains a hypothesis |
| IMG second slot / SAM7 byte +0x1F -> `0x2002092C[13:8]` | `YBBLND`, Yb blend ratio | Register-layout match; M10-R signal role remains a hypothesis |
| M10-R Y BLEND pairs at `0x20020930/34` | No counterpart in the inspected SDK YC structure/writer | Meanings unresolved |

The full structures differ: M10-R has thirteen-bit YC matrix register fields, while the SDK declares nine-bit signed matrix fields. The SDK control word is at `0x2841A120`, not `0x2002092C`. Its YC parameter structure is nine 16-bit matrix members plus two 16-bit ratios (22 bytes under the declared types), not M10-R's 40-byte `<15H2B4H>`. It lacks all three M10-R YC paired words and both Y BLEND paired words in that structure/writer.

Therefore do not transplant the SDK ABI, smaller matrix coefficients, endpoint assumptions or pixel math into the renderer. The M10-R normal controls remain `(0,32)` and fallback `(0,0)` from the preceding verified work. The range 0–32 does not establish a denominator, unity, half-weight, blend direction or `k=0.35`.

The SDK's `(0,0)` example is not an observed pixel result. Its `(63,63)` register test is not proof of a valid photographic setting. Neither demonstrates an M10-R bypass.

## Executed tests

The canonical tool verifies six source hashes, parses the named control-word layout, guards the source assignments, checks firmware hashes and executes the retained identity guards. It then enumerates all 64 x 64 six-bit control pairs through both original firmware programmers:

- IMG D4480: 4,096 executions.
- SAM7 0x51DA6: 4,096 executions.
- Total: 8,192 original-programmer executions, 57,344 paired-word writes, zero paired-word bit-15 changes.

Each execution checks the whole 16,384-byte modeled MMIO window against the retained packing model and separately checks the SDK's control-word layout. Prior register bytes and four Y BLEND tail halfwords vary deterministically with seed `0xB2A65D26`. This is exhaustive only over the two six-bit fields, not every input/state combination.

The original programmers accept and store the tested raw six-bit values 33–63; they do not clamp the fields at the SDK comment's maximum of 32. There are 1,089 control pairs inside 0–32 on both axes and 3,007 outside. That does not determine hardware behavior for invalid parameter values.

Only the retained SAM7 clock helpers 0x4D1B4 and 0x4D118 are substituted. No sensor, ISP pixels, clock gating, reset side effects or photographic behavior are emulated. Unknown M10-R tail fields are not relabeled as SDK fields.

Concatenated output-window SHA256:
`4f3ebceeda9f93433cceeabe1270a036f8bdb07a46f4938a115f1cb123aa3a79`.

## SAM7 caller investigation

The canonical census decodes branch candidates at every ARM/Thumb alignment in raw SAM7 offsets 0x4..0x106264, including conditional and tail branches. It decoded 688,772 instruction candidates, found three internal branches into the programmer body and no external immediate branch into it. It found 91 candidates targeting known clock helper 0x4D1B4, a positive decoder control, and recorded 1,442 indirect-branch candidates.

Possible data decodes are included. The indirect candidates are not proven live calls. Indirect target calculation, runtime relocation, alternative address mappings and reachability are not solved. **The actual compact-structure producer/caller remains unresolved; this is not proof of dead code.**

## CI and integrity

Complete verification run **35501765107 succeeded** at source commit `e15e6fb94e83db01b2714eb038e3ac9fd97e0b56`.
Artifact: `10601993659`, `M10R-YBLEND-SDKBRIDGE1A-EVIDENCE`.
Artifact ZIP SHA256: `68e9c7e210ba81205fa31ef9b61c0bea09e393b8328edb8d6667df175ce9798c`.
New tool SHA256: `8a452793052bf865317ce4052b142c4f005e19ad99007b8593185c50a387283b`.

All seven CI-manifest entries passed integrity checks. The downloaded new tool and new machine results are byte-identical to local execution. The retained 10,240-execution BIT15 audit was rerun locally and in CI; those JSONs also match byte-for-byte. The old audit is regression coverage, not new pixel evidence.

Input acquisition disclosure: bootstrap run 35501513461 fetched 158 path-selected external files, but its artifact omitted two hidden temporary document/lock files. The 156 present files passed size, SHA256 and Git-blob checks; this was not a complete 158-entry artifact match. None of the six canonical files was missing. The final workflow explicitly fetches only those six and verifies all six hashes, so it does not depend on the omitted files. Bootstrap artifact 10601863612 SHA256: `26ff677ae99af496feb24820d602857507dccdce3e0f77b650673d1e4ebfccf7`.

The final evidence artifact does not include firmware, external SDK source, dependency libraries or an APK. Report-persistence commits are separate from the exact CI-tested source commit.

## Frozen boundaries and next target

Freshly read frozen refs remained:
- `m10r-render1q-yblend1b-k035`: `a66b73cc339ebcb863d345c7a9ee7ff631fc86f0`.
- `m10r-capture1b`: `3b1e86b5055a21b548d56b23bd47f9dc66c57012`.

No renderer, matrix, WB, exposure, tone, image-quality setting or capture behavior changed. No APK was built. Keep `k=0.35` as a frozen photographic approximation.

The next discriminating investigation is whether M10-R has the corresponding CCYC-derived Yb / TCYC-derived luminance paths, where they are produced and consumed, and whether the Y BLEND outputs feed final luminance or a downstream reference path. Link any such claim through original M10-R code or matching-revision documentation rather than adopting SDK names alone. The two M10-R paired words, mixing direction, denominator, signal scaling, stage placement, rounding and clipping still need evidence. Another register-mask sweep will not solve those questions.

Reproduce with Capstone 5.0.3, Unicorn 2.1.3 and assertions enabled:

```bash
python3 tools/m10r_yblend_sdkbridge1a.py VERIFIED_SECTIONS REPO_ROOT SDK_SOURCE_ROOT results
```

The companion full downloadable report expands this repository summary. The result index in this branch identifies exact source/CI evidence; the artifact retains the full machine-readable result.
