# M10-R B2Y OFFSET2 CROSSMODEL1A

Key-aware cross-model audit of record 0x02 (offset).

## Summary

- Record counts: {'M10R-20.20.47.37': 1, 'M10M-2.12.8.0': 1, 'M10M-3.21.2.50': 1}
- Union keys: **4**
- STILL keys: **1**
- STILL keys changed/missing across models: **0**

## STILL keys

| Key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |
|---|---|---:|---:|---:|
| _B2YMODE:STILL | exact_equal | 0 | 0 | 0 |

## Record inventory

| Firmware | Ordinal | Keys | SHA256 | First 8 signed words |
|---|---:|---|---|---|
| M10R-20.20.47.37 | 0 | _B2YMODE:STILL, _B2YMODE:STILLLINK, _B2YMODE:SLIVE, _B2YMODE:SMAGNI | 374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb | [0, 0, 0, 0] |
| M10M-2.12.8.0 | 0 | _B2YMODE:STILL, _B2YMODE:STILLLINK, _B2YMODE:SLIVE, _B2YMODE:SMAGNI | 374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb | [0, 0, 0, 0] |
| M10M-3.21.2.50 | 0 | _B2YMODE:STILL, _B2YMODE:STILLLINK, _B2YMODE:SLIVE, _B2YMODE:SMAGNI | 374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb | [0, 0, 0, 0] |

## Next

Map the key-resolved M10-R STILL payload(s) through driver 0xD3284 and determine whether the effective fields are chroma/color offsets, luma offsets, or another B2Y state. Keep renderer frozen.
