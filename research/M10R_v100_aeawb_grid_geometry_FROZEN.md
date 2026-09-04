# M10-R v1.00 — AFAEAWB producer grid geometry FROZEN

## Frozen result

For the relevant Prepro AFAEAWB mode configuration, the firmware defines an AEAWB statistics grid of:

- **22 horizontal blocks**
- **16 vertical blocks**
- **352 blocks total**

This is now frozen as producer-side geometry.

## Evidence chain

1. `0x420D926C` is identified by firmware diagnostic string as `drv_prepro_afaeawb_GetAFAEAWBMode`.
2. `0x420D9304` maps the returned AFAEAWB mode to a fixed 0x7C-byte mode object.
3. In the mode-2 initializer (`0x420D9BD4...`), firmware writes:
   - mode object `+0x18 = 0x16 = 22`
   - mode object `+0x1C = 0x10 = 16`
4. `0x420DAE48` calls `0x420D926C`, calls `0x420D9304`, then copies exactly `0x7C` bytes from the resolved mode object to the caller-provided destination.
5. Debug wrapper `0x420D93C8` calls `0x420DAE48(mode, sp)` and then prints:
   - `[sp + 0x18]` with firmware label `Prepro: AEAWB Block Numbers (horizontal): %d`
   - `[sp + 0x1C]` with firmware label `Prepro: AEAWB Block Numbers (vertical): %d`
6. Therefore mode-object fields `+0x18/+0x1C` are explicitly named by Leica firmware as horizontal/vertical AEAWB block counts, and their initialized values are 22/16.

## Correction to v0.96 interpretation

v0.96 decoded a later, separate c-aberration settings dump whose unrelated structure also contains fields at `+0x18/+0x1C` (`ABLRVL`/`ABLRHL`). That did **not** describe the AFAEAWB mode object copied by `0x420DAE48`. The identical offsets belong to different structures. v0.99 plus the `0x420DAE48` copy chain resolves the ambiguity.

## Cross-check against CA9

Existing CA9 recovery independently established grid indexing as `row * 22 + col`, yielding 352 cells. The independently recovered Prepro producer geometry now matches that consumer geometry exactly: **22 x 16 = 352**.

## Still not frozen

Do **not** yet freeze any of the following:

- `workflow + 0x480 == Prepro AFAEAWB base pointer`
- `workflow + 0x480 == Prepro base + 0x14080`
- exact AFAEAWB per-cell record size/stride
- exact producer-to-CA9 serialization/cross-core transfer path
- exact channel/field mapping inside each producer statistics record

## Next target

Use the now-frozen 22x16 geometry as a structural fingerprint. Trace non-debug consumers/programmers of the AFAEAWB mode-data block, especially block-count fields `+0x18/+0x1C`, into the Prepro statistic buffer and then match its 352-record layout against the CA9 object reached via `workflow + 0x480`.
