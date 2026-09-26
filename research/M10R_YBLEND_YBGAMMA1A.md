# M10-R YBLEND YBGAMMA1A

Extraction from the already verified YBPATH1A evidence; no firmware or renderer change.

- Record 0x09 values: [0, 0, 0, 0, 0, 0]
- Record 0x0B values: [1, 1]
- Normal four gamma-related control bits: **[0, 0, 1, 1]**

Destinations:
- record 0x09 slot0 -> 0x20020800 bit16
- record 0x09 slot1 -> 0x20020800 bit17
- record 0x0B slot0 -> 0x20020800 bit24
- record 0x0B slot1 -> 0x20020800 bit25

Boundary: the public related R2Y SDK exposes a separate Yb gamma-table path, but its ABI differs from Leica. These Leica bits must not be renamed as Yb controls without stronger evidence.

Next: use the extracted normal state plus table routing to decide whether an untone-mapped Yb candidate should nevertheless pass the recovered DG/gamma transfer before Y_BLEND.
