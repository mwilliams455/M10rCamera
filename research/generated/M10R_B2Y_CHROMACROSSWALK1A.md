# M10-R B2Y CHROMACROSSWALK1A

Cross-execution proof that IMG calibration record 0x18 and SAM7 Im_B2Y_Ctrl_Chroma_Suppress are two representations of the same hardware control block.

## Result

- All four real M10-R saturation modes produced identical MMIO output through IMG +0xD0770 and SAM7 +0x51F1A after packing.
- Randomized cross-execution cases passed: 256/256.
- Compact SAM7 structure size used: 0x4E bytes.
- The six LOW/MEDIUM/HIGH saturation-strength fields map to compact offsets 0x04,0x06,0x08,0x0A,0x0C,0x0E and registers 0x20021110..0x20021118.

## Consequence

Record 0x18 is now structurally bound to Leica's named Im_B2Y_Ctrl_Chroma_Suppress API, not merely inferred from the IMG selector string.

This still does not recover the B2Y hardware consumer equation or prove where Chroma Suppress sits relative to CC1/Yc in the pixel path. Those remain the next boundary before renderer implementation.
