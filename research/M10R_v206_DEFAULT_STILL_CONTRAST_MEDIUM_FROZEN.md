# M10-R v2.06 — Default still contrast = MEDIUM frozen

## Status

**Firmware-proven and frozen.**

The M10-R default still-image B2Y object is initialized with contrast enum `2`, and enum `2` is already proven to map to `_CONTRAST:MEDIUM`. The same initialized object is registered into the per-slot pointer table that the live B2Y acquisition path later reads.

Therefore the factory/default still-photo tone branch is:

```text
contrast enum 2
    -> _CONTRAST:MEDIUM
    -> ID8 MEDIUM descriptor
    -> ID19 MEDIUM TBL0
    -> ID1A MEDIUM TBL1 when descriptor enables the second bank
```

For this firmware the active MEDIUM TBL0 and TBL1 payloads are byte-identical.

## Exact initialization

In IMG-System around `0x4216F8C4`, `r7` is loaded with the global default B2Y object address `0x408FE188`.

The initializer then writes:

```asm
4216f8e6: movs r1, #2
4216f8e8: movs r0, #0xac
4216f8ea: str  r1, [r0, r7]    ; object +0xAC = 2
```

The same value `2` is also written to sibling fields `+0xA8` and `+0xB0`; their exact semantics are not frozen by this note.

Immediately after the writes:

```asm
4216f8fa: ldr  r0, =0x408CECF0
4216f8fc: ldr  r1, [r0]       ; context
4216f8fe: movs r0, r7          ; object
4216f900: bl   0x421599A0
```

## Exact registration into live slot table

`0x421599A0` receives:

- original `r0` = B2Y object pointer;
- original `r1` = context pointer.

It selects a free/appropriate slot and then performs:

```asm
421599d8: ldr  r0, [sp, #0x20]   ; slot index
421599da: lsls r2, r0, #2
421599dc: ldr  r3, =0x1D50
421599de: ldr  r0, [sp, #0x28]   ; original context
421599e0: adds r0, r0, r3
421599e2: ldr  r1, [sp, #0x24]   ; original object pointer
421599e4: str  r1, [r0, r2]
```

Thus it stores the initialized object at:

```text
context + 0x1D50 + 4 * slot
```

This is exactly the companion pointer table later read by `0x42160D40` before the object is passed to `0x42151F28` and `0x4215220C`.

## Exact enum mapping already frozen

From `M10R_v198_CONTRAST_ENUM_TONE_SELECTION_FROZEN.md`:

| Enum | Suffix |
|---:|---|
| 1 | `_CONTRAST:LOW` |
| 2 | `_CONTRAST:MEDIUM` |
| 3 | `_CONTRAST:HIGH` |
| 4 | `_CONTRAST:VIDEOLOW` |
| 5 | `_CONTRAST:VIDEOMEDIUM` |
| 6 | `_CONTRAST:VIDEOHIGH` |

Therefore `object+0xAC = 2` is not a heuristic interpretation; it deterministically selects the MEDIUM calibration records.

## Renderer rule

For the first-parity **default still-photo** renderer, select the MEDIUM tone asset by default.

The frozen first-parity tone math remains:

```text
idx  = x >> 1
gain = tone_medium_q15[idx] / 32768
y    ~= x * gain
```

Exact hardware rounding/live-domain normalization remain separate open details; the **choice of MEDIUM asset is closed**.

## Evidence

- `research/M10R_v195_contrast_enum_default_provenance.txt`
- `research/M10R_v198_CONTRAST_ENUM_TONE_SELECTION_FROZEN.md`
- `research/M10R_v204_contrast_ac_writers_bounded.txt`
- `research/M10R_v205_default_contrast_registration_proof.txt`
- `research/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md`
