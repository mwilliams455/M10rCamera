# M10-R B2Y COLOR CANDIDATES1A

Key-aware cross-model audit of the remaining near-color B2Y records 0x13, 0x14, 0x15 and 0x17.

## 0x13 color_dif_lpf_A

- Record counts: {'M10R-20.20.47.37': 1, 'M10M-2.12.8.0': 1, 'M10M-3.21.2.50': 1}
- Union keys: **12**
- STILL: exact=3, changed=0, missing/added=0

| STILL key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |
|---|---|---:|---:|---:|
| _B2YMODE:STILL_SHARPNESS:HIGH | exact_equal | 0 | 0 | 0 |
| _B2YMODE:STILL_SHARPNESS:LOW | exact_equal | 0 | 0 | 0 |
| _B2YMODE:STILL_SHARPNESS:MEDIUM | exact_equal | 0 | 0 | 0 |

Representative M10-R occurrences:

| Ord | Size | Keys | First 12 signed words |
|---:|---:|---|---|
| 0 | 16 | _B2YMODE:STILL_SHARPNESS:LOW, _B2YMODE:STILL_SHARPNESS:MEDIUM, _B2YMODE:STILL_SHARPNESS:HIGH, _B2YMODE:STILLLINK_SHARPNESS:LOW, _B2YMODE:STILLLINK_SHARPNESS:MEDIUM ... | [0, 0, 0, 0] |

## 0x14 unknown_page21000

- Record counts: {'M10R-20.20.47.37': 1, 'M10M-2.12.8.0': 1, 'M10M-3.21.2.50': 1}
- Union keys: **12**
- STILL: exact=3, changed=0, missing/added=0

| STILL key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |
|---|---|---:|---:|---:|
| _B2YMODE:STILL_SHARPNESS:HIGH | exact_equal | 0 | 0 | 0 |
| _B2YMODE:STILL_SHARPNESS:LOW | exact_equal | 0 | 0 | 0 |
| _B2YMODE:STILL_SHARPNESS:MEDIUM | exact_equal | 0 | 0 | 0 |

Representative M10-R occurrences:

| Ord | Size | Keys | First 12 signed words |
|---:|---:|---|---|
| 0 | 72 | _B2YMODE:STILL_SHARPNESS:LOW, _B2YMODE:STILL_SHARPNESS:MEDIUM, _B2YMODE:STILL_SHARPNESS:HIGH, _B2YMODE:STILLLINK_SHARPNESS:LOW, _B2YMODE:STILLLINK_SHARPNESS:MEDIUM ... | [0, 0, 0, 128, 0, 0, 0, 0, 255, 0, 128, 0] |

## 0x15 colorcorrection0_A

- Record counts: {'M10R-20.20.47.37': 1, 'M10M-2.12.8.0': 1, 'M10M-3.21.2.50': 1}
- Union keys: **12**
- STILL: exact=3, changed=0, missing/added=0

| STILL key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |
|---|---|---:|---:|---:|
| _B2YMODE:STILL_SHARPNESS:HIGH | exact_equal | 0 | 0 | 0 |
| _B2YMODE:STILL_SHARPNESS:LOW | exact_equal | 0 | 0 | 0 |
| _B2YMODE:STILL_SHARPNESS:MEDIUM | exact_equal | 0 | 0 | 0 |

Representative M10-R occurrences:

| Ord | Size | Keys | First 12 signed words |
|---:|---:|---|---|
| 0 | 72 | _B2YMODE:STILL_SHARPNESS:LOW, _B2YMODE:STILL_SHARPNESS:MEDIUM, _B2YMODE:STILL_SHARPNESS:HIGH, _B2YMODE:STILLLINK_SHARPNESS:LOW, _B2YMODE:STILLLINK_SHARPNESS:MEDIUM ... | [0, 0, 0, 128, 0, 0, 0, 0, 255, 0, 128, 0] |

## 0x17 post_processing_filter

- Record counts: {'M10R-20.20.47.37': 1, 'M10M-2.12.8.0': 1, 'M10M-3.21.2.50': 1}
- Union keys: **4**
- STILL: exact=1, changed=0, missing/added=0

| STILL key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |
|---|---|---:|---:|---:|
| _B2YMODE:STILL | exact_equal | 0 | 0 | 0 |

Representative M10-R occurrences:

| Ord | Size | Keys | First 12 signed words |
|---:|---:|---|---|
| 0 | 24 | _B2YMODE:STILL, _B2YMODE:STILLLINK, _B2YMODE:SLIVE, _B2YMODE:SMAGNI | [16383, 16383, 16383, 16383, 16383, 16383] |

## Interpretation boundary

This pass only identifies model/version-specific key-resolved calibration. Selector identities and hardware fields must be recovered before any renderer experiment.
