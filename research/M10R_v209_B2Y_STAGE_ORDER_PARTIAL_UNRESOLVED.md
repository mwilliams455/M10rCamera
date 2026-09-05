# M10-R v2.09 — B2Y STAGE ORDER PARTIAL / UNRESOLVED BOUNDARY

Date: 2026-09-05
Branch: `m10r-color-science-trace`

## Scope

This note records the result of the bounded v2.08 / v2.08b B2Y routing probes. It is deliberately **not** a stage-order freeze.

Authoritative probe artifacts:

- `research/M10R_v208_b2y_stage_order_routing.txt`
- `research/M10R_v208b_b2y_link_xrefs_control.txt`

## Proven observations

1. High-level B2Y mode strings include distinct `STILL` and `STILLLINK` labels. The corrected Thumb ADR trace resolves:
   - `0x42151c64 -> 0x42151e20` `_B2YMODE:STILL`
   - `0x42151c6e -> 0x42151e30` `_B2YMODE:STILLLINK`

2. The low-level routine adjacent to `IMG: drv_img_b2y_start_link_mode_clk()` begins at approximately `0x420d47dc` in Thumb mode and manipulates the `0xD0001000` clock/control page. Its visible logic tests and changes clock-domain fields; it does not expose a B2Y CC/DG/tone source selector.

3. The named `drv_img_b2y_set_operation_mode` routine is a small Thumb routine beginning at `0x420d3434`. It reads a four-byte mode descriptor and writes the low nibble of `0x20022058`:
   - all four descriptor bytes zero -> field value `0`
   - bytes `[0,1,2,3] = [1,1,0,0]` -> field value `3`
   - bytes `[0,1,2] = [0,1,0]` on the recovered branch -> field value `2`
   - other combinations route to the error path in the recovered function.

   This is a real operation-mode selector, but the recovered code does not identify its values as specific internal pixel-stage source/destination edges.

4. Both known B2Y programmer variants program the same major blocks:
   - direct WB gain registers `0x2002008C / 0x20020090`
   - CC0 control/data `0x20020100 / 0x20020120..0x20020130`
   - CC1 control/data `0x20020880 / 0x200208A0..0x200208B0`

5. Differential gamma and tone both touch the `0x20020800` control page, but their recovered bit programming is block-local:
   - differential gamma has its already-frozen control bits including 24/25
   - tone uses low control bits beginning at bit 0/1 and associated tone registers such as `0x20020804`

   Shared register-page ownership does **not** establish pixel order.

6. The v2.08 shared-MMIO scan did not expose an explicit mux/source/bypass field naming a CC0/CC1 -> DG -> tone (or alternate) producer/consumer relation.

## Non-result that must be preserved

Do **not** infer any of the following solely from programmer/call order:

```text
CC0 -> CC1 -> DG -> tone
DG -> CC0/CC1 -> tone
CC0/CC1 -> tone -> DG
```

None is directly proven by the recovered routing bits as of v2.09.

## Implementation consequence

The first offline renderer must keep uncertain B2Y stage ordering explicit and switchable. Recovered assets and block arithmetic should be implemented exactly, but the renderer must not silently canonize a stage order that firmware evidence has not established.

Recommended diagnostic ordering switches should at minimum distinguish the relative placement of:

- rendered CC matrix application
- differential gamma
- tone Q15 gain stage
- de-knee/interpolation-gamma stage where applicable

Direct WB gain remains a distinct proven front-end hardware path and should not be removed.

## Next research action

Proceed to exact tone integer arithmetic:

- live sample domain / bit depth
- 4096-entry index derivation
- Q15 multiplication expression
- rounding bias
- right shift
- saturation/clamp

This arithmetic can be recovered without pretending that the unresolved inter-stage graph is closed.
