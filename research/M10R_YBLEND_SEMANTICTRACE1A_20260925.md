# M10-R Y_BLEND SEMANTICTRACE1A — FIXED RECORD / NO SOFTWARE CONSUMER FOUND

Date: 2026-09-25

Repository: `mwilliams455/M10rCamera`

Research branch: `m10r-yblend-semantictrace1a`

Successful Actions run: `36175002052`

Validated source commit: `512135424f363add86fb48aac488c9d3dbe340df`

Artifact: `M10R-YBLEND-SEMANTICTRACE1A-RESULTS` (artifact ID `10882460403`)

## Scope

This pass continues from D4480 PRODUCER1A. It is a bounded firmware/static census. It does **not** recover the ISP pixel equation and does not change any photographic/capture code.

## 1. Exact normal record 0x0D occurs twice, identically

The exact 24-byte normal Y BLEND payload:

```
00000000 20000000 ff3f0000 ff3f0000 ff3f0000 ff3f0000
```

(`[0,32,0x3fff,0x3fff,0x3fff,0x3fff]` as little-endian U32) appears only at:

- active B2Y payload offset `0x131874`
- trailing duplicate/default region offset `0x1349b4`

Both are inside the same extracted `IMG Calibration Data/data/calib/B2Y.bin` section and have the same surrounding-context SHA256.

This is consistent with the previously identified trailing duplicate/default record and gives no alternate calibrated Y BLEND value in this firmware.

## 2. No stored compact YCC/Y_BLEND ABI copy

The 40-byte SAM7 compact structure `<15H2B4H` is not stored verbatim in the extracted firmware.

The compact structure remains a runtime packing/cross-core configuration representation derived from record 0x0C + record 0x0D, not a second independent calibration table.

## 3. Named-string census remains sparse

Specific strings found:

- IMG-System: `Y BLEND     String:%s` at `0x154E78`
- IMG-System: `img_b2y_select_y_blend_paraset` near `0x154EB9`
- IMG-SAM7: `Im_B2Y_Ctrl_Yc_Convert` diagnostic near `0x51FFE`

No additional field-name strings were found that name p0..p5 or explain `0`, `32`, or the paired `0x3FFF` values.

## 4. No direct SAM7 caller or stored function pointer to 0x51DA6

Direct Thumb BL census:

- IMG D4480: canonical direct call at `0x154E68`
- SAM7 `0x51DA6`: **no direct BL call found**

Raw stored-pointer census for `0x51DA6/0x51DA7` also found no pointer occurrence.

This does not prove the SAM7 routine is unused. The evidence is consistent with it being an externally dispatched/API entry point rather than a locally direct-called function. No completeness claim is made for indirect/RPC dispatch.

## 5. 0x20020900 page-owner census

SAM7 has two literal owners of page `0x20020900`:

- `0x50414` via literal `0x50624`: existing research identifies this as the **YNR** control family, using later offsets such as `+0x40/+0x50...`
- `0x51DB0` via literal `0x51FF8`: the **YCC / Im_B2Y_Ctrl_Yc_Convert** function that reaches `+0x2C/+0x30/+0x34`

No raw literal of the exact watched addresses `0x2002092C/30/34` was found in IMG-System or SAM7. They are reached by base-plus-offset addressing.

The earlier writer audit remains the stronger evidence for the watched registers: D4480 and the SAM7 YCC programmer are the established software writers to this scope.

## 6. Resulting constraint

Together with PRODUCER1A, the normal still Y BLEND configuration is now strongly constrained as a **fixed calibration state**:

```
record 0x0D
  p0 = 0
  p1 = 32
  p2..p5 = 0x3FFF
      ↓ direct selector handoff
D4480 / SAM7 YCC register programmer
      ↓
0x2002092C / 30 / 34
      ↓
opaque B2Y hardware consumer
```

No scene-dependent software coefficient has been found between the calibration record and the hardware registers.

The remaining unknown is therefore the hardware interpretation of those fields.

## 7. Still unresolved

Do not infer from this pass:

- `32 == 0.5`, Q5, Q6, unity, or any other denominator;
- `0x3FFF` pair semantics as min/max, clipping, scale, threshold, or signed endpoints;
- which pixel-domain signals are blended;
- stage order, rounding, clipping, or per-pixel arithmetic;
- exact Leica photographic parity.

## 8. Next highest-value research

A more discriminating next step is **cross-firmware comparison**.

The same M10-R hardware has publicly released older firmware generations. If record 0x0D changes across versions, the deltas can constrain field roles. If it remains byte-identical across substantially different firmware generations, that supports the interpretation that these values are stable hardware constants rather than later photographic tuning.

This is more useful than another renderer `k` experiment.
