# M10-R Exposure Engine v0.16 — Metering Mode Enum and Named CMOS BV Fields

**Date:** 2026-09-04  
**Branch:** `m10r-metering-latch-trace`  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Firmware SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Milestone

This pass closes the semantic identity of the three-state selector at `0x20000132` and the three CMOS BV candidate fields consumed by CTRL.

The selector is now proved to be the **exposure metering mode** selector, with this exact mapping:

```text
0 -> Spot
1 -> Integral
2 -> MFM
invalid/other -> Integral
```

The prior caution against naming the three ring candidates is superseded by the instruction-level IMG payload labels recovered in v0.31.

## 2. Exposure metering mode transport

CTRL has two direct callers of the selector setter `0x0800DE28`:

```text
0x08001C1C
0x080020D6
```

Both pass the incoming byte through `0x08007C20` first.

`0x08007C20` is a bounded identity mapper:

```text
0 -> 0
1 -> 1
2 -> 2
anything else -> 1
```

The dedicated receiver at `0x080020BA` logs:

```text
Exposure metering mode received (%i)
```

then converts the received signed byte through `0x08007C20` and stores it through `0x0800DE28` into:

```text
0x20000132
```

The bulk-apply path at `0x08001BB0` obtains the same field from structure offset `+0x1A` before using the same converter and setter.

IMG independently logs `exposure metering mode: %d` from structure byte `+0x1A`, closing the cross-core field identity.

The IMG system-parameter handler also contains:

```text
CtrlCPU: IMG_SPARAM_ID_EXP_METERING_MODE
exposure metering mode: %d
```

and reads the mode byte from its parameter payload at `+0x02`.

## 3. Named IMG CMOS BV payload fields

The v0.31 ADR trace resolves the inline debug strings and the exact byte pairs reconstructed immediately before each print.

For the upstream 16-bit CMOS BV candidates:

```text
input +0x21/+0x22 = BV_Integral
input +0x23/+0x24 = BV_spot
input +0x25/+0x26 = BV_MFM
```

Each pair is reconstructed low byte / high byte into the signed exposure coordinate used by the firmware.

Firmware terminology is exact:

```text
BV_Integral = %d
BV_spot = %d
BV_MFM = %d
```

## 4. CTRL ring provenance

The CTRL record producer at `0x08003068` copies:

```text
input +0x21 .. +0x30 -> ring +0x05 .. +0x14
```

Therefore:

```text
ring +0x05 = BV_Integral
ring +0x07 = BV_spot
ring +0x09 = BV_MFM
```

This closes the semantic identity left unresolved in v0.15.

## 5. Metering selector at 0x0800F1C0

`0x0800F1C0` chooses the ring field as follows:

```text
selector 0 -> ring +0x07
selector 1 -> ring +0x05
selector 2 -> ring +0x09
other      -> ring +0x05
```

Combining the ring provenance with the named IMG fields gives the exact exposure-metering enum:

```text
selector 0 -> BV_spot
selector 1 -> BV_Integral
selector 2 -> BV_MFM
other      -> BV_Integral
```

After selection, factory `AV0` is added and the result participates in the BvCMOS update path ending at setter `0x08011D82` (`AE state +0x16`).

## 6. Current cross-core model

```text
IMG / CA9 CMOS AE outputs
    BV_Integral
    BV_spot
    BV_MFM
        |
        v
upstream input structure
    +0x21 Integral
    +0x23 Spot
    +0x25 MFM
        |
        v
CTRL 0x08003068
        |
        v
ring 0x200190AC
    +0x05 Integral
    +0x07 Spot
    +0x09 MFM
        |
        v
meter-mode selector 0x20000132
    0 Spot
    1 Integral
    2 MFM
        |
        v
0x0800F1C0 + AV0
        |
        v
BvCMOS -> AE state +0x16
```

## 7. Remaining upstream seam

The unresolved boundary is no longer the metering-mode enum. The next target is the serializer/transport between:

```text
CA9/shared AE pack at 0x408F0EC0
```

where the named values are written as:

```text
+0x2A/+0x2B Integral
+0x2C/+0x2D Spot
+0x2E/+0x2F MFM
+0x30/+0x31 AV-field
```

and the IMG/CTRL input structure where they appear as:

```text
+0x21 Integral
+0x23 Spot
+0x25 MFM
```

Event `0x78000032` has already been shown to be a zero-payload synchronization/doorbell event rather than the carrier of those values.

The next investigation should locate the shared-block reader or serializer that copies/transforms the packed AE values into the LVVideoSync/input record.
