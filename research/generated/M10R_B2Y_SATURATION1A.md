# M10-R B2Y SATURATION1A

Original-firmware execution of record 0x18 (color_dif_suppression) for M10-R STILL saturation LOW/MEDIUM/HIGH.

## Payload result

- LOW: six words at 0x10..0x24 = 0x1b34 (6964), ratio to MEDIUM = 0.85009766x.
- MEDIUM: six words at 0x10..0x24 = 0x2000 (8192).
- HIGH: six words at 0x10..0x24 = 0x2666 (9830), ratio to MEDIUM = 1.19995117x.
- Apart from those six words, LOW/MEDIUM/HIGH 144-byte payloads are identical.

## Original setter execution

Setter: IMG-System +0xd0770.
The six scale words affect exactly 3 MMIO word address(es): 0x20021110, 0x20021114, 0x20021118.

Each of the six payload words was perturbed independently from MEDIUM to the LOW value. Their union exactly equals the full LOW-vs-MEDIUM and HIGH-vs-MEDIUM register-programmer delta under a nonzero deterministic MMIO initial state.

Therefore the LOW/MEDIUM/HIGH distinction in the M10-R 0x18 still-saturation record is fully isolated to these six firmware-programmed values.

## Boundary

This does not yet prove the hardware pixel equation or Q-format. Do not simply multiply Android chroma by 0.85/1.0/1.2 until the destination-register semantics and signal domain are recovered.

## Next

Trace the exact destination register bitfields for the six scale words, then identify where the equivalent operation belongs relative to POSTYC1A / CC1 in the renderer. Validate offline first; keep the Android renderer frozen.
