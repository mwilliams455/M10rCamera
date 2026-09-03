# M10-R Exposure Engine v0.05: Release-Key and AE-Lock Trigger Boundary

## Outcome

This pass resolves the physical shutter-key encoding but does **not** yet prove
that the first detent is the sole producer of AE lock.

The IMG key translator at `0x42186734` consumes a physical-key index and raw
state. Its 28-byte key descriptor table starts at `0x427F8EC4`; record 13 is
named `K_Release` and contains event IDs `0xD5..0xD8`.

For the release-button record (type 1), the production branches are:

| Raw state | Emitted event | Address of selection block |
|---|---|---|
| `1` | `0xD6` = `K_Release_1` | `0x4218687E..0x42186890` |
| `3` | `0xD7` = `K_Release_2` | `0x42186892..0x421868A4` |
| `2` | `0xD5` = `K_Release_0` | `0x421868A6..0x421868B8` |

`0xD8` (`K_Release_3`) exists in the descriptor but is not selected by this
type-1 branch. It is emitted elsewhere during exposure/reset sequencing and
must not be treated as a fourth physical detent.

## Separation from external AE commands

The initialized global-action records at `0x4096942C..0x4096946C` keep two
families separate:

| External event | Action |
|---|---|
| `0xAB` `EXT_EXPOSURE_START` | emits `K_Release_1`, plus exposure preparation |
| `0xAC` `EXT_EXPOSURE_KRELEASE2` | emits `K_Release_2` |
| `0xAD` `EXT_EXPOSURE_STOP` | emits `K_Release_0` |
| `0xAE` `EXT_AE_LOCK` | directly sends CTRL command `0x12`, payload `1` |
| `0xAF` `EXT_AE_UNLOCK` | directly sends CTRL command `0x12`, payload `0` |

This proves that remote/external AE lock is not implemented by synthesizing a
release-button detent. External exposure control synthesizes release events;
external AE lock uses its own commands.

## Corrected negative result

The large switch beginning at `0x42134D50` was initially a tempting producer
candidate because its cases at `0x42135388` and `0x42135392` mention `0xAE` and
`0xAF`. It is not an event dispatcher.

Each case passes an identifier and option to `0x42139598`, which searches a
runtime mapping table and returns a value. Its failure string is:

```text
 string not found: _string = %d, _option = %d
```

The function returns immediately after the lookup and never calls the IMG
event-packet producer at `0x421BC9E8`. Those cases are enum/string-option
translation, not evidence of an AE-lock trigger.

## What remains open

The only direct callers of the two CTRL command senders remain:

- AE-lock state-entry callback `0x421BD5D4` and external action `0x421BE68C`;
- AE-unlock state-entry callback `0x421BD5E4` and external action `0x421BE69A`.

Therefore the unresolved production question has narrowed to the transition
logic that enters `ae_lock_enabled` and `ae_lock_disabled`. The physical key
path is now known through `K_Release_0/1/2`, but a direct transition edge from
`K_Release_1` to the enabled state (and from `K_Release_0` to disabled) has not
yet been recovered from the generated state-machine metadata.

Do not promote the plausible rule “first detent locks, release unlocks” into
the oracle until either that metadata edge or a hardware event trace confirms
it. The cross-CPU hold behavior documented in v0.04 remains unchanged.

## Reproducibility

```bash
python tools/m10r_ae_lock_inspect.py \
  firmware/sections/090_CTRL-System.bin \
  firmware/sections/092_IMG-System.bin
python -m unittest discover -s tests -v
```

The inspector now verifies both IMG address aliases, the release-key descriptor
and detent mapping, the independent external AE action records, and the enum
mapper's non-producer signature.
