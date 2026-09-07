# M10-R B2Y DATAPATH AUDIT1C — RECORD-8 +0x08 TABLE CONTROL

Research-only. Renderer unchanged.

Baseline record-8 `+0x08` = `0x00000001`.

## Synthetic +0x08 copy requests

| +0x08 | Returned | Copy requests |
|---:|:---:|---|
| `0x00000000` | `True` | `dst=0x20a00000 src=0x10002000 bytes=81920 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=81920 LR=0x420d4250` |
| `0x00000001` | `True` | `dst=0x20a00000 src=0x10002000 bytes=40960 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=40960 LR=0x420d4250` |
| `0x00000002` | `True` | `dst=0x20a00000 src=0x10002000 bytes=20480 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=20480 LR=0x420d4250` |
| `0x00000003` | `True` | `dst=0x20a00000 src=0x10002000 bytes=20480 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=20480 LR=0x420d4250` |
| `0x00000004` | `True` | `dst=0x20a00000 src=0x10002000 bytes=20480 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=20480 LR=0x420d4250` |
| `0x00000010` | `True` | `dst=0x20a00000 src=0x10002000 bytes=20480 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=20480 LR=0x420d4250` |
| `0x00000100` | `True` | `dst=0x20a00000 src=0x10002000 bytes=20480 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=20480 LR=0x420d4250` |
| `0xffffffff` | `True` | `dst=0x20a00000 src=0x10002000 bytes=20480 LR=0x420d4228; dst=0x20a0a000 src=0x1000c000 bytes=20480 LR=0x420d4250` |

## Static copy callsites

- `0x420d4224` `bl #0x4204f2ec`
- `0x420d424c` `bl #0x4204f2ec`

## Control disassembly 0x420D3C50..0x420D3D70

```text
  0x420d3c50  lsr      r0, r0, #0x1f
  0x420d3c54  cmp      r0, #0
  0x420d3c58  bne      #0x420d4258
  0x420d3c5c  ldr      r0, [pc, #0x634]
  0x420d3c60  ldr      r0, [r0, #0x800]
  0x420d3c64  bic      r0, r0, #1
  0x420d3c68  ldrb     r1, [r4]
  0x420d3c6c  and      r1, r1, #1
  0x420d3c70  orr      r0, r0, r1
  0x420d3c74  ldr      r1, [pc, #0x61c]
  0x420d3c78  str      r0, [r1, #0x800]
  0x420d3c7c  add      r0, r1, #0
  0x420d3c80  ldr      r0, [r0, #0x800]
  0x420d3c84  bic      r0, r0, #2
  0x420d3c88  mov      r2, #2
  0x420d3c8c  ldr      r1, [r4, #4]
  0x420d3c90  and      r1, r2, r1, lsl #1
  0x420d3c94  orr      r0, r0, r1
  0x420d3c98  ldr      r1, [pc, #0x5f8]
  0x420d3c9c  str      r0, [r1, #0x800]
  0x420d3ca0  add      r0, r1, #0
  0x420d3ca4  ldr      r0, [r0, #0x804]
  0x420d3ca8  bic      r0, r0, #3
  0x420d3cac  ldrb     r1, [r4, #8]
  0x420d3cb0  and      r1, r1, #3
  0x420d3cb4  orr      r0, r0, r1
  0x420d3cb8  ldr      r1, [pc, #0x5d8]
  0x420d3cbc  str      r0, [r1, #0x804]
  0x420d3cc0  add      r0, r1, #0
  0x420d3cc4  ldr      r0, [r0, #0x804]
  0x420d3cc8  bic      r0, r0, #0x30
  0x420d3ccc  mov      r2, #0x30
  0x420d3cd0  ldr      r1, [r4, #0xc]
  0x420d3cd4  and      r1, r2, r1, lsl #4
  0x420d3cd8  orr      r0, r0, r1
  0x420d3cdc  ldr      r1, [pc, #0x5b4]
  0x420d3ce0  str      r0, [r1, #0x804]
  0x420d3ce4  add      r0, r1, #0
  0x420d3ce8  ldr      r0, [r0, #0x804]
  0x420d3cec  bic      r0, r0, #0x300
  0x420d3cf0  mov      r2, #0x300
  0x420d3cf4  ldr      r1, [r4, #0x10]
  0x420d3cf8  and      r1, r2, r1, lsl #8
  0x420d3cfc  orr      r0, r0, r1
  0x420d3d00  ldr      r1, [pc, #0x590]
  0x420d3d04  str      r0, [r1, #0x804]
  0x420d3d08  add      r0, r1, #0
  0x420d3d0c  ldr      r0, [r0, #0x804]
  0x420d3d10  bic      r0, r0, #0x10000
  0x420d3d14  ldrh     r1, [r4, #0x14]
  0x420d3d18  mov      r2, #0x10000
  0x420d3d1c  and      r1, r2, r1, lsl #16
  0x420d3d20  orr      r0, r0, r1
  0x420d3d24  ldr      r1, [pc, #0x56c]
  0x420d3d28  str      r0, [r1, #0x804]
  0x420d3d2c  add      r0, r1, #0
  0x420d3d30  ldr      r0, [r0, #0x804]
  0x420d3d34  bic      r0, r0, #0x3f000000
  0x420d3d38  ldrb     r1, [r4, #0x18]
  0x420d3d3c  mov      r2, #0x3f000000
  0x420d3d40  and      r1, r2, r1, lsl #24
  0x420d3d44  orr      r0, r0, r1
  0x420d3d48  ldr      r1, [pc, #0x548]
  0x420d3d4c  str      r0, [r1, #0x804]
  0x420d3d50  ldr      r0, [pc, #0x544]
  0x420d3d54  ldrd     r0, r1, [r0]
  0x420d3d58  sub      r3, sb, r8, lsl #12
  0x420d3d5c  and      r2, r0, r3
  0x420d3d60  mov      r3, #0
  0x420d3d64  rsb      fp, r8, r8, lsl #12
  0x420d3d68  ldr      r0, [r4, #0x1c]
  0x420d3d6c  and      r0, r0, fp
```

## Boundary

Copy-request dependence can identify the +0x08 programming role, but does not prove MEDIUM/DG pixel order, signal source, coordinate scaling, clamp placement, rounding, or post-DG transfer.
