# M10-R v1.71 — TF REMAPPING INERT ON PROVEN CM/B2Y PATH — FROZEN

## Scope

This note freezes the current interpretation of `B2Y_TF_REMAPPING_CA9_CM.bin` for Leica M10-R firmware `30.22.23.34` based on the proven IMG↔CA9 color-management execution path.

It does **not** claim that no undocumented hardware/DMA engine could ever observe the shared memory. It does claim that no executable IMG/CA9 consumer has been found on the proven per-frame color-management path, and the previously suspected ASN-remap interpretation is false.

## Proven file / serialization ABI

The IMG parser `ca9_cm_Get_BinFileTfRemappingData` (`0x420A4884`) reads:

- enable
- entry count, maximum 31
- up to 31 pairs of two `u32` values, stride 8

`ca9_cm_config_fill` (`0x420A4AAC`) serializes the data into the live color configuration at `0x43705830`:

- `CFG + 0x128`: enable
- `CFG + 0x12C`: entry count
- `CFG + 0x130`: derived count-related field
- `CFG + 0x134 .. +0x22B`: 31 pair slots (`0xF8` bytes)

The ordering is also proven: default/preset construction occurs first; the TF file is parsed and overlaid near the end of `ca9_cm_config_fill`, then the routine returns.

## Opcode 0x20 does not overwrite the TF block

The real IMG sender of CA9 opcode `0x20` was recovered in v1.66.

Its request word 2 is:

`0x43705AA4`

Given live CM configuration base:

`0x43705830`

this is:

`CFG + 0x274`

The CA9 opcode `0x20` handler (`0x4000B59C`) operates relative to that later substructure. Its zero/recompute region therefore begins after the TF block and cannot clear or replace `CFG+0x128/+0x12C/+0x130/+0x134`.

This closes the earlier ordering concern.

## Per-frame request forwarding

`ca9_cm_fill_parameter` (`0x420A591C`) prepares the per-frame parameter block at `0x43705760` immediately before `StartColorManagement` sends opcode `0x40`.

It forwards:

- input ASN doubles at parameter `+0x08/+0x10/+0x18`
- CM mode at `+0x20`
- live CM configuration pointer `0x43705830` at `+0x24`
- debug `remap_color` software flag `0x40818764` at parameter byte `+1`

The IMG-side global `0x40818764` has exactly one executable reader in the scanned IMG image: `ca9_cm_fill_parameter`. The other two references are the debug command's on/off writes.

Therefore IMG does not itself apply `remap_color` before sending the request.

## CA9 opcode 0x40 path

The dispatcher maps opcode `0x40` to:

`0x40004050 -> 0x40003AF4`

`0x40004050` only loads request word 2 and tail-calls the CM core.

v1.70 symbolic pointer provenance over `0x40003AF4` proves:

### Request accesses

The core reads/writes request fields including:

- `REQ + 0x00`
- `REQ + 0x20`
- `REQ + 0x24`
- output fields `REQ + 0x48 .. +0xB0`

It does **not** access `REQ + 0x01`.

Thus the forwarded `remap_color` byte is not consumed by the CA9 CM core.

### Configuration accesses

The core follows `REQ+0x24` to `CFG`, but the proven effective CFG accesses are only low/matrix fields such as:

- `CFG + 0x20`
- `CFG + 0x28`
- `CFG + 0x38`
- `CFG + 0x68`
- sub-block pointers passed as `CFG + 0x98`
- sub-block pointers passed as `CFG + 0xE0`

There is no:

- `CFG + 0x128`
- `CFG + 0x12C`
- `CFG + 0x130`
- `CFG + 0x134`

and no callee receives the raw `CFG` pointer from the CM core.

Therefore the 31-pair TF block cannot be consumed indirectly by an op40 callee through the live config pointer.

## ASN correction

Earlier work inferred from the diagnostic label `ASN remapped R/G/B` that the TF table might remap ASN.

That interpretation is withdrawn.

The CA9 CM core copies the three input ASN doubles into its local working triplet and does not mutate that triplet before copying it to the returned ASN fields (`+0xB8/+0xC0/+0xC8`).

So:

`ASN_out = ASN_in`

on the recovered path.

## Completion side

`ColorManagementFinished` (`0x420A3639`) follows `parameter+0x24` and consumes the low CM configuration / returned matrix fields required for DNG and rendered CC handling.

The recovered completion path does not read the TF count/pair block and does not read parameter byte `+1` as the remap switch.

Other direct IMG references to the per-frame parameter block are diagnostics, gain/mode reads, setup/reset, and request construction. v1.68 found no runtime path from those references to the TF block.

## Frozen conclusion

For the proven Leica M10-R 30.22.23.34 IMG↔CA9 color-management execution path:

1. `B2Y_TF_REMAPPING_CA9_CM.bin` is a real parsed configuration file.
2. Its enable/count/31-pair structure is serialized into live CM configuration memory.
3. The table survives opcode `0x20` configuration processing.
4. The per-frame parameter forwards a `remap_color` debug flag and the configuration pointer.
5. Neither the CA9 op40 CM core nor its tagged configuration callees consumes the TF table or the remap flag.
6. The IMG completion/result path also does not consume them.
7. The TF table does not remap ASN on the recovered path.

**Implementation status:** treat this TF table as inert / non-required for first-parity M10-R rendering unless a later hardware/DMA trace proves another consumer.

## Next research target

Stop spending color-science effort on the 31-pair TF block for now.

Follow the data that is demonstrably live:

- `0x408FE124` B2Y control/header block
- `0x408FE130` rendered CC bank 0
- `0x408FE15C` rendered CC bank 1
- B2Y register programmers around `0x42152F8C` / `0x421536BC`
- any live curve/tone/LUT data loaded from `B2Y.bin`

Goal: recover the actual M10-R rendered transfer/tone behavior that reaches B2Y hardware and distinguish it from dead/debug CM configuration.