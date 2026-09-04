# M10-R v1.45 — WB / ASN / B2Y baseline frozen

This note freezes only firmware-proven structure. It intentionally leaves remaining WB mode names and the final rendered-CC-to-B2Y consumer boundary open.

## 1. WB mode and preset are separate enums

- Top-level WB mode `3` is the **preset-dispatch mode**.
- Preset selector is a separate value at CA9 WB input `+0x18`.
- Firmware error fallback explicitly logs that it is setting WB to Daylight and writes:
  - top-level mode = `3`
  - preset = `1`
- Therefore **preset 1 = Daylight**.
- Do not rename other numeric modes/presets until direct firmware semantics prove them.

## 2. Raw WB gain input ABI

`ca9_cm_fill_parameter` at `0x420A591C` reads three signed 16-bit gains from its input object:

- R = `int16(input + 0xF4)`
- G = `int16(input + 0xF6)`
- B = `int16(input + 0xF8)`

Each channel is independently clamped to `[1, 2000]`.

These integer gains are the cleanest canonical WB gain representation recovered so far.

## 3. ASN shared color-management ABI

Shared block base: `0x43705760`.

`ca9_cm_fill_parameter` converts the clamped integer RGB gains to doubles and writes reciprocal ASN values:

- ASN R = `256.0 / gainR` at shared `+0x08` (double)
- ASN G = `256.0 / gainG` at shared `+0x10` (double)
- ASN B = `256.0 / gainB` at shared `+0x18` (double)

Other proven shared fields:

- `+0x00` byte is logged as `performCalculation`.
- `+0x20` byte is a separately selected color-management control value; exact semantic name remains open.
- `ca9_StartColorManagement` embeds pointer `0x43705760` in its submission record before calling `0x420A3488`.

When debug/override flag `0x40818766` is nonzero, doubles from `0x408F0E48` overwrite the generated ASN triplet. Treat this as an override path; exact user-facing purpose remains unfrozen.

## 4. Gain recovery / rounding

`ColorManagementFinished` recovers debug RGB gains from the ASN triplet as:

`gainRecovered = round(256.0 / ASN)`

Channel order is R/G/B from shared offsets `+0x08/+0x10/+0x18`.

Helper `0x421A0A44` implements nearest-integer rounding with halfway cases away from zero (C `round()` semantics), returning a double. Its internal nearest-integer primitive at `0x421E6A6C` uses ties-to-even, then `0x421A0A44` explicitly corrects half-way residuals to away-from-zero behavior.

Thus, absent the override path and floating error:

`gain -> ASN = 256/gain -> round(256/ASN)`

round-trips the original clamped integer gain.

## 5. B2Y baseline calibration/config files

Two firmware-owned binary payloads are distinct from the per-frame ASN block:

- `B2Y_CC0_CA9_CM.bin`: exact payload size `0x84` bytes.
- `B2Y_TF_REMAPPING_CA9_CM.bin`: exact payload size `0x100` bytes.

B2Y CC0 config destination base: `0x43705830`.

The CC0 builder at `0x420A4AAC`:

- loads the 0x84-byte CC0 payload through `0x420A4628`,
- copies file `+0x58..+0x83` (0x2C bytes) directly to destination `+0x00..+0x2B`,
- interprets file `+0x00..+0x20` as nine fixed-point coefficient words,
- uses file `+0x24` as a power-of-two scale exponent,
- converts those packed coefficients to a floating working representation later in the destination structure.

The TF-remap loader at `0x420A4884` validates a 0x100-byte payload. `ca9_cm_config_fill` serializes it with:

- enable byte at destination `+0x128`,
- 32-bit field at destination `+0x12C` from payload `+0x04`,
- payload `+0x08..+0xFF` copied as 0xF8 bytes to destination `+0x134`.

## 6. Static B2Y setup vs per-frame color management

B2Y baseline config initialization uses a separate setup entry:

`0x420A78EA -> 0x420A5DE4 -> 0x420A4AAC`

Per-frame color-management submission follows:

`0x420A78C4 -> ca9_StartColorManagement (0x420A2EB0)`

and inside `ca9_StartColorManagement`:

`ca9_cm_fill_parameter (0x420A591C) -> build submission containing 0x43705760 -> 0x420A3488`

Therefore the 0x84/0x100 B2Y files are baseline calibration/config structures, while WB scene state is supplied per color-management invocation through the ASN/result block.

## 7. Still open

- Exact semantic names for remaining WB top-level modes and presets.
- Exact user-facing purpose of ASN override flag `0x40818766` / source `0x408F0E48`.
- Whether the final per-frame B2Y white-balance effect is programmed through rendered CC0/CC1 matrix consumers, a separate gain path, or both.
- Exact downstream consumers of rendered CC globals `0x408FE130` and `0x408FE15C`.

Those downstream CC consumers are the next investigation boundary.