# M10-R B2Y CHROMA-KEY CROSSMODEL1A

Key-aware comparison of B2Y 0x16 color_dif_lpf and 0x18 color_dif_suppression.

Lookup model: firmware scans records in table order for the requested record ID, then compares the runtime selector string against each 64-byte key slot; the first exact key match supplies the payload.

## 0x16 color_dif_lpf

Union keys: **128**; exact-equal: **58**; changed: **58**; missing/added: **12**.
STILL keys changed: **0** of **32**.
STILLLINK keys changed: **0** of **32**.
SLIVE keys changed: **29** of **32**.
SMAGNI keys changed: **29** of **32**.

### Changed STILL keys

| Key | M10-R occurrence | M10M latest occurrence | Status |
|---|---:|---:|---|
| _B2YMODE:STILL_ISO:200000 | - | 0 | missing_or_added |
| _B2YMODE:STILL_ISO:64000 | 0 | - | missing_or_added |
| _B2YMODE:STILL_ISO:80000 | 0 | - | missing_or_added |

### Record occurrences

| Firmware | Ordinal | Table index | Keys | Scope counts | SHA256 |
|---|---:|---:|---:|---|---|
| M10R-20.20.47.37 | 0 | 151 | 31 | {'STILL': 31} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10R-20.20.47.37 | 1 | 152 | 31 | {'STILLLINK': 31} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10R-20.20.47.37 | 2 | 153 | 31 | {'SLIVE': 31} | 2a5f409d1d41f6f99e736a8c4a67f871a8b554fdb2b9cb48fe93766ab00c4b44 |
| M10R-20.20.47.37 | 3 | 154 | 31 | {'SMAGNI': 31} | 2a5f409d1d41f6f99e736a8c4a67f871a8b554fdb2b9cb48fe93766ab00c4b44 |
| M10M-2.12.8.0 | 0 | 31 | 30 | {'STILL': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-2.12.8.0 | 1 | 32 | 30 | {'STILLLINK': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-2.12.8.0 | 2 | 33 | 30 | {'SLIVE': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-2.12.8.0 | 3 | 34 | 30 | {'SMAGNI': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-3.21.2.50 | 0 | 31 | 30 | {'STILL': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-3.21.2.50 | 1 | 32 | 30 | {'STILLLINK': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-3.21.2.50 | 2 | 33 | 30 | {'SLIVE': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |
| M10M-3.21.2.50 | 3 | 34 | 30 | {'SMAGNI': 30} | 66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925 |

## 0x18 color_dif_suppression

Union keys: **23**; exact-equal: **0**; changed: **0**; missing/added: **23**.
STILL keys changed: **0** of **4**.
STILLLINK keys changed: **0** of **4**.
SLIVE keys changed: **0** of **4**.
SMAGNI keys changed: **0** of **4**.

### Changed STILL keys

| Key | M10-R occurrence | M10M latest occurrence | Status |
|---|---:|---:|---|
| _B2YMODE:STILL_SATURATION:HIGH | 2 | - | missing_or_added |
| _B2YMODE:STILL_SATURATION:LOW | 0 | - | missing_or_added |
| _B2YMODE:STILL_SATURATION:MEDIUM | 1 | - | missing_or_added |
| _B2YMODE:STILL_SATURATION:MONOCHROME | 3 | - | missing_or_added |

### Record occurrences

| Firmware | Ordinal | Table index | Keys | Scope counts | SHA256 |
|---|---:|---:|---:|---|---|
| M10R-20.20.47.37 | 0 | 156 | 4 | {'SMAGNI': 1, 'STILL': 1, 'STILLLINK': 1, 'SLIVE': 1} | 1398e69d8a2a800fbeed2f19206c77c1ce4c9dfed5d5826981f18587200adbbd |
| M10R-20.20.47.37 | 1 | 157 | 4 | {'SMAGNI': 1, 'STILL': 1, 'STILLLINK': 1, 'SLIVE': 1} | 54cde24003101f41623747e60ccdacc95bc6fa716a05df9e34ecf01880c1c501 |
| M10R-20.20.47.37 | 2 | 158 | 4 | {'SMAGNI': 1, 'STILL': 1, 'STILLLINK': 1, 'SLIVE': 1} | 71278a1e06c05ff2d91857b66cc83606987a05da3068e7dc74c7b8146dcbcb6d |
| M10R-20.20.47.37 | 3 | 159 | 4 | {'SMAGNI': 1, 'STILL': 1, 'STILLLINK': 1, 'SLIVE': 1} | f5bfd9c52989f480321c26c0b8fb64f0ec7aed9f0362532b777b04d889a934db |
| M10M-2.12.8.0 | 0 | 36 | 1 | {'OTHER': 1} | 9374eda49d1ac00848b1bb801fcd32022de0d3476a724ed0490bc55c1d7f86e5 |
| M10M-2.12.8.0 | 1 | 37 | 1 | {'OTHER': 1} | 8297ad0f8849c49333ec42ff6240de9465c165f00e3ed0524e3820b14d8975a2 |
| M10M-2.12.8.0 | 2 | 38 | 1 | {'OTHER': 1} | 6db0fb4d290e78ce7ad617d7831458e00dd8a8ca6c40d2189988d90eba0419ad |
| M10M-2.12.8.0 | 3 | 39 | 1 | {'OTHER': 1} | e0d771e8772ac62aa519fb53a4e15c7995b1e00c63555d2fb3eb8ef0d8a53978 |
| M10M-2.12.8.0 | 4 | 40 | 1 | {'OTHER': 1} | fa5fac2782c6f0a1db1653576c311621a0d898da0945f62c04e179462481832f |
| M10M-2.12.8.0 | 5 | 41 | 1 | {'OTHER': 1} | 18887bcacf66843106573117387ccece7ec5489fad1dac9fcc3c63d85c314356 |
| M10M-2.12.8.0 | 6 | 42 | 1 | {'OTHER': 1} | 08ccf0aeb61d211fcb28acce40aa05e02abb78e72ae8bf04b8eb53ec231b7a94 |
| M10M-3.21.2.50 | 0 | 36 | 1 | {'OTHER': 1} | 9374eda49d1ac00848b1bb801fcd32022de0d3476a724ed0490bc55c1d7f86e5 |
| M10M-3.21.2.50 | 1 | 37 | 1 | {'OTHER': 1} | 8297ad0f8849c49333ec42ff6240de9465c165f00e3ed0524e3820b14d8975a2 |
| M10M-3.21.2.50 | 2 | 38 | 1 | {'OTHER': 1} | 6db0fb4d290e78ce7ad617d7831458e00dd8a8ca6c40d2189988d90eba0419ad |
| M10M-3.21.2.50 | 3 | 39 | 1 | {'OTHER': 1} | e0d771e8772ac62aa519fb53a4e15c7995b1e00c63555d2fb3eb8ef0d8a53978 |
| M10M-3.21.2.50 | 4 | 40 | 1 | {'OTHER': 1} | fa5fac2782c6f0a1db1653576c311621a0d898da0945f62c04e179462481832f |
| M10M-3.21.2.50 | 5 | 41 | 1 | {'OTHER': 1} | 18887bcacf66843106573117387ccece7ec5489fad1dac9fcc3c63d85c314356 |
| M10M-3.21.2.50 | 6 | 42 | 1 | {'OTHER': 1} | 08ccf0aeb61d211fcb28acce40aa05e02abb78e72ae8bf04b8eb53ec231b7a94 |

## Decision boundary

- A changed ordinal is not enough; only a changed key-resolved payload can affect that exact runtime selector key.
- Prioritize changed STILL keys first for the saved-still renderer.
- STILLLINK/SLIVE/SMAGNI differences are useful controls but should not be substituted for STILL behavior.
- Do not change the Android renderer until the selected 0x16/0x18 payload fields are mapped to the setter/MMIO arithmetic.
