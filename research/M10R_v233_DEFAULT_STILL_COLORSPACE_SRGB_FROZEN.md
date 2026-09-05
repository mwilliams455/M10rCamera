# M10-R v2.33 — Default still color space = sRGB (frozen)

## Scope

Freeze the factory/default STILL output color-space selection used by the CA9 rendered-color path.

## Proven enum mapping

The IMG B2Y string mapper reads the registered object at `+0x44` and maps:

- `1` -> `_COLORSPACE:SRGB`
- `2` -> `_COLORSPACE:ADOBERGB`
- `3` -> `_COLORSPACE:ECI`

The same original still object carries this value at `+0xB4`; the string-builder caller copies original `+0xB4` into the temporary object's `+0x44` before calling the mapper.

`ca9_cm_fill_parameter` independently reads original `+0xB4` and translates the IMG enum into CA9's zero-based ColorSpec mode byte:

- IMG `1` -> CA9 `0`
- IMG `2` -> CA9 `1`
- IMG `3` -> CA9 `2`

## Factory/default initializer

The already-proven registered STILL object initializer at `0x4216F8BE...` writes:

- `+0xB4 = 1`
- `+0xAC = 2` (contrast MEDIUM, frozen separately)
- sibling defaults at `+0xA8/+0xB0 = 2`

The object is then registered by the same `0x421599A0` path previously frozen for the STILL-default proof.

Therefore:

**Factory/default still output color space = sRGB.**

Equivalently, CA9 receives ColorSpec mode `0` for the default still path.

## Consequence for first-parity reconstruction

For factory/default still JPEG parity, CC1 must use the sRGB output-space branch unless capture metadata or an explicit camera setting proves another color-space selection.

## Evidence boundary

This freezes only the default still color-space selection and its enum translation. It does not alter the separately frozen CC0/CC1 architecture or claim anything about B2Y stage ordering beyond already-proven dataflow.
