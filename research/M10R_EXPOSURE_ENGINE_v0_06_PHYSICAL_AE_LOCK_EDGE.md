# M10-R Exposure Engine v0.06: Physical AE-Lock State Edges

## Outcome

The physical shutter-button AE-lock path is now closed statically from the
key translator through the IMG state machine and CTRL exposure calculator.

The two AE states are 0x90-byte BSTM records:

| State | Runtime VA | Entry callback | Entry effect |
|---|---:|---:|---|
| `ae_lock_enabled` | `0x40992E3C` | `0x421BD5D4` | sends CTRL command `0x12`, payload `1` |
| `ae_lock_disabled` | `0x40992ECC` | `0x421BD5E4` | sends CTRL command `0x12`, payload `0` |

Their constructors are emitted at `0x421CA6D0..0x421CA712`. The controller
initialization at `0x421C7264..0x421C729C` installs the disabled state as the
initial state; the controller name `AE_LOCK_CONTROL` is copied at
`0x421C73A4`.

## Corrected load-image mapping

The transition arrays are addressed by their runtime RAM VAs, but their
initializers are stored later in the firmware image. Reading the bytes at the
RAM-shaped file offset produces misleading zeros.

For this BSTM initializer block:

```text
file_offset = runtime_RAM_VA - 0x40000000 + 0x91078
```

That maps the two one-entry transition arrays as follows:

| Source state | Transition RAM VA | File offset | Event | Guard | Action | Target state |
|---|---:|---:|---:|---:|---:|---|
| `ae_lock_enabled` | `0x408D988C` | `0x96A904` | `0xD5` | `0` | `0` | `ae_lock_disabled` (`0x40992ECC`) |
| `ae_lock_disabled` | `0x408D989C` | `0x96A914` | `0xD6` | `0` | `0` | `ae_lock_enabled` (`0x40992E3C`) |

The BSTM dispatcher at `0x420A27A6` confirms the 16-byte transition layout:

```text
+0x00  event ID (low halfword)
+0x04  optional guard callback
+0x08  optional action callback
+0x0C  optional target-state pointer
```

It compares the transition event directly with the incoming event, runs the
guard if present, runs the action if present, and finally switches to the
target state. The framework's state-machine cloning routine at
`0x421E3AFE..0x421E3B5C` independently confirms that `+0x0C` is a state
pointer by resolving and rewriting it in the cloned machine.

## Production shutter sequence

The v0.05 physical-key mapping and the recovered edges combine into this
stateful rule:

| Physical input | IMG event | AE state effect |
|---|---:|---|
| first detent / raw state `1` | `0xD6` `K_Release_1` | disabled → enabled; lock payload `1` is sent |
| second detent / raw state `3` | `0xD7` `K_Release_2` | no AE-local transition; lock remains enabled |
| release / raw state `2` | `0xD5` `K_Release_0` | enabled → disabled; unlock payload `0` is sent |

This is not a blind toggle. `K_Release_1` is only an edge out of the disabled
state, and `K_Release_0` is only an edge out of the enabled state. The second
detent does not cancel AE lock.

## End-to-end oracle rule

The production exposure oracle may now model physical AE lock without a
provisional assumption:

1. On `K_Release_1`, enter `ae_lock_enabled` and send IMG→CTRL command `0x12`
   with payload `1`.
2. CTRL stores the value in byte `0x2001AD6E` and exposes it as exposure-input
   `+0x25 bit 1`.
3. While that bit is set, the calculator at `0x080203B4` skips the write that
   refreshes cached calculation Bv at `0x2000012A`; the rest of the exposure
   computation continues using the previously latched Bv.
4. `K_Release_2` does not change the AE-lock state.
5. On `K_Release_0`, enter `ae_lock_disabled`, send payload `0`, and allow the
   next exposure calculation to refresh cached Bv.

The external `EXT_AE_LOCK`/`EXT_AE_UNLOCK` actions remain a separate direct
command path and must not be conflated with shutter detents.

## Reproducibility

```bash
python tools/m10r_ae_lock_inspect.py \
  firmware/sections/090_CTRL-System.bin \
  firmware/sections/092_IMG-System.bin
python -m unittest discover -s tests -v
```

The inspector verifies the RAM-to-load-image mapping, both state records,
both physical transition entries, the entry callbacks, the IPC contract, and
the CTRL cached-Bv gate.
