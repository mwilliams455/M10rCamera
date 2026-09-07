# M10-R B2Y DATAPATH AUDIT1B — TONE CONTROL ROUTING

Research-only. Renderer unchanged.

## Baseline

- Tone programmer: `0x420d3c1c .. 0x420d4298`
- Record-8 u32 fields: `44`
- Bit probes successful / failed: `1376 / 32`
- Focus registers: `0x20020800=0x00000001`, `0x20020804=0x00000011`, `0x20020808=0x0a650400`, `0x2002080c=0x0000019a`
- `0x20020804` write PCs: `0x420d3cbc`, `0x420d3ce0`, `0x420d3d04`, `0x420d3d28`, `0x420d3d4c`

## Descriptor fields affecting focus registers

| Descriptor offset | Baseline | Observed output-bit influence |
|---:|---:|---|
| `0x0` | `0x00000001` | `0x20020800:0x00000001` |
| `0x4` | `0x00000000` | `0x20020800:0x00000002` |
| `0xc` | `0x00000001` | `0x20020804:0x00000030` |
| `0x10` | `0x00000000` | `0x20020804:0x00000300` |
| `0x14` | `0x00000000` | `0x20020804:0x00010000` |
| `0x18` | `0x00000000` | `0x20020804:0x3f000000` |
| `0x1c` | `0x00000400` | `0x20020808:0x00000fff` |
| `0x20` | `0x00000a65` | `0x20020808:0x0fff0000` |
| `0x24` | `0x0000019a` | `0x2002080c:0x00000fff` |

## Fields affecting `0x20020804`

- descriptor `0xc` baseline `0x00000001` -> output mask `0x00000030`
  - input bit 0 (`0x00000001`) -> `0x00000011 -> 0x00000001`, xor `0x00000010`
  - input bit 1 (`0x00000002`) -> `0x00000011 -> 0x00000031`, xor `0x00000020`
- descriptor `0x10` baseline `0x00000000` -> output mask `0x00000300`
  - input bit 0 (`0x00000001`) -> `0x00000011 -> 0x00000111`, xor `0x00000100`
  - input bit 1 (`0x00000002`) -> `0x00000011 -> 0x00000211`, xor `0x00000200`
- descriptor `0x14` baseline `0x00000000` -> output mask `0x00010000`
  - input bit 0 (`0x00000001`) -> `0x00000011 -> 0x00010011`, xor `0x00010000`
- descriptor `0x18` baseline `0x00000000` -> output mask `0x3f000000`
  - input bit 0 (`0x00000001`) -> `0x00000011 -> 0x01000011`, xor `0x01000000`
  - input bit 1 (`0x00000002`) -> `0x00000011 -> 0x02000011`, xor `0x02000000`
  - input bit 2 (`0x00000004`) -> `0x00000011 -> 0x04000011`, xor `0x04000000`
  - input bit 3 (`0x00000008`) -> `0x00000011 -> 0x08000011`, xor `0x08000000`
  - input bit 4 (`0x00000010`) -> `0x00000011 -> 0x10000011`, xor `0x10000000`
  - input bit 5 (`0x00000020`) -> `0x00000011 -> 0x20000011`, xor `0x20000000`

## Real record-8 occurrences

- occurrence 0: `0x20020800=0x00000001`, `0x20020804=0x00000011`, `0x20020808=0x0a650400`, `0x2002080c=0x0000019a`

## Interpretation boundary

This audit can prove descriptor-to-register packing and control dependencies. It cannot by itself prove luma-vs-RGB signal routing, MEDIUM/DG pixel order, LUT coordinate scaling, clamp placement, Q15 rounding, or post-DG transfer semantics.
