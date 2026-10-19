# M10-R v1.98 — Contrast enum / tone selection ABI frozen

## Status

This note freezes the firmware-proven mapping from the IMG B2Y input structure's contrast field to the calibration-key suffix used to select the LOW / MEDIUM / HIGH tone tables.

The camera's factory/default still-photo contrast enum remains unresolved at this point and is **not** inferred here.

## Proven source field

`0x4215220C` reads a 32-bit value from its B2Y input object at `input + 0xAC`, copies it to the tone-selector object's `+0x68`, and calls `0x42151508`.

`0x42151508` maps that numeric value into an ASCII suffix stored at selector `+0x6C`. The tone selector then builds the B2Y calibration key by concatenating the base mode string and this suffix before ID8/ID19/ID1A lookup.

## Exact enum mapping

The switch helper at IMG `0x4209F988` is an inline byte-table dispatcher. Decoding the table at the contrast call site proves:

| Numeric value | Calibration suffix | Meaning |
|---:|---|---|
| 0 | error path | invalid / unsupported for this mapper |
| 1 | `_CONTRAST:LOW` | LOW |
| 2 | `_CONTRAST:MEDIUM` | MEDIUM |
| 3 | `_CONTRAST:HIGH` | HIGH |
| 4 | `_CONTRAST:VIDEOLOW` | VIDEO LOW |
| 5 | `_CONTRAST:VIDEOMEDIUM` | VIDEO MEDIUM |
| 6 | `_CONTRAST:VIDEOHIGH` | VIDEO HIGH |
| >=7 | error path | invalid / unsupported |

The six suffix strings are resident next to the mapper in IMG-System and are used by the corresponding switch branches.

## Selection chain

```text
B2Y input +0xAC
      |
      v
contrast enum
      |
      v
0x42151508
      |
      +--> 1 -> _CONTRAST:LOW
      +--> 2 -> _CONTRAST:MEDIUM
      +--> 3 -> _CONTRAST:HIGH
      +--> 4 -> _CONTRAST:VIDEOLOW
      +--> 5 -> _CONTRAST:VIDEOMEDIUM
      +--> 6 -> _CONTRAST:VIDEOHIGH
      |
      v
base B2Y mode key + suffix
      |
      v
ID8 descriptor + ID19 TBL0 (+ ID1A TBL1 when enabled)
```

## Object provenance now known

The two clearest STILL-style callers obtain their object pointers through `0x42160D40` and then pass the same pointer first to `0x42151F28` and then to `0x4215220C`.

`0x42160D40` is an acquisition/lookup routine, not the constructor of the B2Y object. On its successful path it returns an existing pointer from a context table rooted at:

```text
context + 0x1D50 + 4 * slot
```

where the slot index is derived from the low five bits of a state byte. Therefore the contrast value at object `+0xAC` predates B2Y acquisition and must be traced to the producer/initializer of the objects stored in that pointer table.

## What remains open

Do **not** freeze MEDIUM as the camera default yet.

Still unresolved:

1. which routine populates the `context + 0x1D50` object-pointer table;
2. where the selected object receives its `+0xAC` contrast enum;
3. which enum is used by the factory/default still-photo settings.

## Evidence

- `research/M10R_v193_default_contrast_provenance.txt`
- `research/M10R_v194_contrast_suffix_mapper.txt`
- `research/M10R_v195_contrast_enum_default_provenance.txt`
- `research/M10R_v196b_contrast_pointer_provenance_fast.txt`
- `research/M10R_v197_b2y_object_acquire_contrast.txt`
- tone math/model: `research/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md`

## Frozen implementation rule

A renderer/API that is given a recovered contrast enum may map values 1/2/3 directly to the frozen LOW/MEDIUM/HIGH tone-table assets. It must not silently substitute MEDIUM for an unknown/default enum until the upstream default producer is recovered.
