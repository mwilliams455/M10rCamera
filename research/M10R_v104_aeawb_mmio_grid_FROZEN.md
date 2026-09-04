# M10-R v1.04 — AEAWB MMIO grid mapping FROZEN

## Frozen result

For AFAEAWB mode `0x11`, the firmware programs the Prepro AEAWB block-count registers as:

- **MMIO `0x2000401C` = horizontal block count = 22**
- **MMIO `0x20004018` = vertical block count = 16**

This is the hardware-level form of the already frozen 22 horizontal x 16 vertical = 352 block geometry.

## Evidence chain

### 1. Mode-object semantics are explicitly named by firmware

The AFAEAWB mode-data debug path copies the complete 0x7C-byte mode object and prints:

- mode object `+0x18` as `Prepro: AEAWB Block Numbers (horizontal): %d`
- mode object `+0x1C` as `Prepro: AEAWB Block Numbers (vertical): %d`

For mode `0x11`, its initializer writes:

- `+0x18 = 0x16 = 22`
- `+0x1C = 0x10 = 16`

### 2. SetPreproGlobalSettings selects the same semantic mode ID

`drv_prepro_afaeawb_SetPreproGlobalSettings` first calls `drv_prepro_afaeawb_GetAFAEAWBMode`, stores the returned mode at Prepro state `0x408F0310`, and branches on that value.

In the `mode == 0x11` branch it initializes the compact live AEAWB-window structure around `0x408F03F0` with:

- compact `+0x0A = 0x16 = 22`
- compact `+0x08 = 0x10 = 16`

Because this is the same AFAEAWB mode ID whose named mode object defines horizontal=22 and vertical=16, the compact fields are identified as:

- compact `+0x0A` = horizontal block count
- compact `+0x08` = vertical block count

### 3. Hardware writer maps compact fields into MMIO

`set aeawb-window` at `0x420DC974` receives the compact structure and writes:

- `[compact +0x08]` -> `[0x20004000 +0x18]`
- `[compact +0x0A]` -> `[0x20004000 +0x1C]`

Therefore:

- `0x20004018` = vertical block count = 16
- `0x2000401C` = horizontal block count = 22

## Cross-check

CA9 independently indexes the statistics grid as `row * 22 + col` and consumes 352 cells. The producer's named configuration, live compact settings, and hardware register programming all now agree with that geometry.

## Still not frozen

This note does **not** establish:

- the exact producer statistics record stride,
- the exact per-cell channel layout,
- whether the CA9 object at `workflow+0x480` is byte-identical to the Prepro normal block, fallback `base+0x14080`, or a serialized/cross-core copy,
- the cross-core transfer mechanism.

## Next target

Trace the post-window configuration path in `drv_prepro_afaeawb_if_Config`, beginning with selector `6` and `base+0x80` passed to `0x420E0850`, and identify the statistics destination/transfer owner. Use the frozen 352-cell geometry as the structural fingerprint for the data-plane match.
