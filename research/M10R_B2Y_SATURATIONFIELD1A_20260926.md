# M10-R B2Y SATURATIONFIELD1A — 0x18 six-lane bitfield packing frozen

Date: 2026-09-26

Parent research:
- CROSSMODEL-DIFF1A
- CC-CONTROL CROSSMODEL1A
- CHROMA-KEY CROSSMODEL1A
- SATURATION1A

## Result

The M10-R B2Y record `0x18` (`color_dif_suppression`) LOW/MEDIUM/HIGH still-saturation distinction is carried only by six payload words at offsets:

```
+0x10 +0x14 +0x18 +0x1C +0x20 +0x24
```

SATURATION1A proved:
- LOW: all six = `0x1B34` = 6964 = 0.85009765625 relative to `0x2000`
- MEDIUM: all six = `0x2000` = 8192
- HIGH: all six = `0x2666` = 9830 = 1.199951171875 relative to `0x2000`

Original setter `IMG-System +0xD0770` maps them exactly into three B2Y MMIO words.

## Exact field packing

### Register 0x20021110

Payload `+0x10`:

```
old &= ~0x00003FFF
new |= payload_10 & 0x3FFF
```

Therefore payload `+0x10` -> register bits `0..13`.

Payload `+0x14`:

```
old &= 0xC000FFFF
new |= (payload_14 & 0x3FFF) << 16
```

Therefore payload `+0x14` -> register bits `16..29`.

### Register 0x20021114

- payload `+0x18` -> bits `0..13`
- payload `+0x1C` -> bits `16..29`

### Register 0x20021118

- payload `+0x20` -> bits `0..13`
- payload `+0x24` -> bits `16..29`

For all three words:
- bits `14..15` are preserved;
- bits `30..31` are preserved.

Thus the saturation-mode delta is six independent 14-bit hardware parameters packed as three low/high pairs.

## Strong numeric constraint

`0x2000` is the exact MEDIUM reference in a 14-bit field. LOW/HIGH are deliberately symmetric-looking scale choices around it:

- LOW / MEDIUM = 6964 / 8192 = 0.85009765625
- HIGH / MEDIUM = 9830 / 8192 = 1.199951171875

This strongly supports a scale-like interpretation with `0x2000` as the neutral reference. It is compatible with Q13 unity, but the exact B2Y pixel equation has not yet been recovered, so do not label the hardware arithmetic Q13 multiplication as proven yet.

## What this rules out

The six values are not:
- Y_BLEND k values;
- CC0/CC1 matrices;
- a single global Android saturation coefficient;
- 32-bit free-form calibration words.

They are six packed B2Y `color_dif_suppression` parameters selected by Leica's still-saturation mode.

## Renderer boundary

No renderer change in this pass.

Do not implement a global `Cb/Cr *= 0.85/1.0/1.2` merely from this result.

Next recover what the six lanes represent and the hardware operation they control. Only then place the equivalent operation relative to POSTYC1A / CC1 and validate offline first.
