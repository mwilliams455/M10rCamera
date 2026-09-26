# M10-R B2Y CROSSMODEL-DIFF1A

Record-by-record M10-R vs M10 Monochrom B2Y calibration diff.

This pass is research-only. It does not alter the Android renderer, exposure, POSTYC1A, WB, tone, GAMUT1A, TONECAL1A, JPEG quality, or Y_BLEND k.

## Provenance

| Firmware | FW SHA256 | Decoded SHA256 | B2Y SHA256 | Records |
|---|---|---|---|---:|
| M10R-20.20.47.37 | `141f0b5fcffe315372bc2c673a3dfa371eab84198d46d6de26016ec0958d77b2` | `6731016c83e1d368a20a13a7c8fb34963246b4a6c253a1088866f3267ae0c75d` | `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b` | 168 |
| M10M-2.12.8.0 | `214d7c51709094a9d5a0435b88dbcd6109cba992c675aa8756d50932eeefd72f` | `7b0d09442cf7e282bc6afa6eccc23101eaaed0739e55976c5542ae9dd0f5814c` | `03962ff3588c6331e95d77d3068ca2b5a95b3bfa504143aa5412a97fd7dca817` | 142 |
| M10M-3.21.2.50 | `8d83001acf6ec613830cc3f8d23a0afed7ae0d3176be902f74069788b0881b23` | `2ab1d9f2731c5815250d07af77a02422f1d34cff9e49f389c8510049c3d69e55` | `c73ca157b8f49783a6331e9c80025301de94ad4c01e615d9818d3b8942121588` | 142 |

## Summary

- Exact-equal aligned records: **49**
- Changed aligned records: **82**
- Keys with one or more missing/added occurrences: **48**
- Structural alignment warnings: **10**

## Invariant controls

- `0x0c#0` **yc_conversion** — `exact_equal`; M10-R vs latest Monochrom: `exact_equal`.
- `0x0d#0` **y_blend** — `exact_equal`; M10-R vs latest Monochrom: `exact_equal`.

## Highest-priority differing records

| Priority | Key | Asset | Selector/name mapping | All-three | M10-R vs M10M 3.21.2.50 | Sizes |
|---|---|---|---|---|---|---|
| P0_MODEL_COLOR | `0x06#0` | - | colorcorrection0 | changed | changed | M10R-20.20.47.37:64, M10M-2.12.8.0:64, M10M-3.21.2.50:64 |
| P0_MODEL_COLOR | `0x0a#0` | - | colorcorrection1 | changed | changed | M10R-20.20.47.37:68, M10M-2.12.8.0:68, M10M-3.21.2.50:68 |
| P1_CHROMA_SHAPING | `0x16#2` | - | color_dif_lpf | changed | changed | M10R-20.20.47.37:32, M10M-2.12.8.0:32, M10M-3.21.2.50:32 |
| P1_CHROMA_SHAPING | `0x16#3` | - | color_dif_lpf | changed | changed | M10R-20.20.47.37:32, M10M-2.12.8.0:32, M10M-3.21.2.50:32 |
| P1_CHROMA_SHAPING | `0x18#0` | - | color_dif_suppression | changed | changed | M10R-20.20.47.37:144, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_CHROMA_SHAPING | `0x18#1` | - | color_dif_suppression | changed | changed | M10R-20.20.47.37:144, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_CHROMA_SHAPING | `0x18#2` | - | color_dif_suppression | changed | changed | M10R-20.20.47.37:144, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_CHROMA_SHAPING | `0x18#3` | - | color_dif_suppression | changed | changed | M10R-20.20.47.37:144, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_CHROMA_SHAPING | `0x18#4` | - | color_dif_suppression | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_CHROMA_SHAPING | `0x18#5` | - | color_dif_suppression | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_CHROMA_SHAPING | `0x18#6` | - | color_dif_suppression | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:144, M10M-3.21.2.50:144 |
| P1_TONE_DG | `0x08#0` | - | tone_control | changed | changed | M10R-20.20.47.37:176, M10M-2.12.8.0:176, M10M-3.21.2.50:176 |
| P1_TONE_DG | `0x19#0` | tone_low | tone_control | missing_or_added | missing | M10R-20.20.47.37:81920, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P1_TONE_DG | `0x19#1` | tone_medium | tone_control | missing_or_added | missing | M10R-20.20.47.37:81920, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P1_TONE_DG | `0x19#2` | tone_high | tone_control | missing_or_added | missing | M10R-20.20.47.37:81920, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P1_TONE_DG | `0x1a#0` | - | tone_control | missing_or_added | missing | M10R-20.20.47.37:81920, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P1_TONE_DG | `0x1a#1` | - | tone_control | missing_or_added | missing | M10R-20.20.47.37:81920, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P1_TONE_DG | `0x1a#2` | - | tone_control | missing_or_added | missing | M10R-20.20.47.37:81920, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P1_TONE_DG | `0x1c#0` | dg_main | edge_synthesis | changed | changed | M10R-20.20.47.37:65536, M10M-2.12.8.0:65536, M10M-3.21.2.50:65536 |
| P1_TONE_DG | `0x1c#1` | dg_main | edge_synthesis | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:65536, M10M-3.21.2.50:65536 |
| P1_TONE_DG | `0x1c#2` | dg_main | edge_synthesis | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:65536, M10M-3.21.2.50:65536 |
| P1_TONE_DG | `0x1d#0` | dg_fl_anchors | edge_synthesis | changed | changed | M10R-20.20.47.37:8192, M10M-2.12.8.0:8192, M10M-3.21.2.50:8192 |
| P1_TONE_DG | `0x1d#1` | dg_fl_anchors | edge_synthesis | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:8192, M10M-3.21.2.50:8192 |
| P1_TONE_DG | `0x1d#2` | dg_fl_anchors | edge_synthesis | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:8192, M10M-3.21.2.50:8192 |
| P2_OTHER | `0x05#0` | - | interploation | changed | changed | M10R-20.20.47.37:36, M10M-2.12.8.0:36, M10M-3.21.2.50:36 |
| P2_OTHER | `0x05#1` | - | interploation | missing_or_added | missing | M10R-20.20.47.37:36, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#0` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#1` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#2` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#3` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#4` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#5` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#6` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#7` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#8` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#9` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#10` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#11` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#12` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#13` | - | offset | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x0e#14` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#15` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#16` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#17` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#18` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#19` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#20` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#21` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#22` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#23` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#24` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#25` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#26` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#27` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#28` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#29` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#30` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#31` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#32` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#33` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#34` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0e#35` | - | offset | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x0f#7` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#8` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#9` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#10` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#11` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#12` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#13` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#14` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#15` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#16` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#17` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#18` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#19` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#20` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#21` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#22` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#23` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#24` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#25` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#26` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#27` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#28` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#29` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#30` | - | interploation | changed | changed | M10R-20.20.47.37:424, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#31` | - | interploation | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#32` | - | interploation | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#33` | - | interploation | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x0f#34` | - | interploation | missing_or_added | added | M10R-20.20.47.37:-, M10M-2.12.8.0:424, M10M-3.21.2.50:424 |
| P2_OTHER | `0x10#7` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#8` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#9` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#10` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#11` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#12` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#13` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#14` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#15` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#16` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#17` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#18` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#19` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x10#20` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:420, M10M-2.12.8.0:420, M10M-3.21.2.50:420 |
| P2_OTHER | `0x11#0` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#1` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#2` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#3` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#4` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#5` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#6` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#7` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#8` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#9` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#10` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#12` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#13` | - | edge_synthesis | changed | changed | M10R-20.20.47.37:84, M10M-2.12.8.0:84, M10M-3.21.2.50:84 |
| P2_OTHER | `0x11#14` | - | edge_synthesis | missing_or_added | missing | M10R-20.20.47.37:84, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x1e#0` | - | interploation | changed | changed | M10R-20.20.47.37:32768, M10M-2.12.8.0:32768, M10M-3.21.2.50:32768 |
| P2_OTHER | `0x1f#0` | - | interploation | changed | changed | M10R-20.20.47.37:32768, M10M-2.12.8.0:32768, M10M-3.21.2.50:32768 |
| P2_OTHER | `0x22#0` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:32768, M10M-2.12.8.0:32768, M10M-3.21.2.50:32768 |
| P2_OTHER | `0x23#0` | - | UNKNOWN | changed | changed | M10R-20.20.47.37:32768, M10M-2.12.8.0:32768, M10M-3.21.2.50:32768 |
| P2_OTHER | `0x26#0` | - | subpre_light | changed | changed | M10R-20.20.47.37:28, M10M-2.12.8.0:28, M10M-3.21.2.50:28 |
| P2_OTHER | `0x26#1` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x26#2` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x26#3` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x26#4` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x26#5` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x26#6` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |
| P2_OTHER | `0x26#7` | - | subpre_light | missing_or_added | missing | M10R-20.20.47.37:28, M10M-2.12.8.0:-, M10M-3.21.2.50:- |

## Structural alignment checks

Occurrence-ordinal alignment needs manual review for: `0x05`, `0x0e`, `0x0f`, `0x11`, `0x18`, `0x19`, `0x1a`, `0x1c`, `0x1d`, `0x26`.

## Interpretation boundary

- A changed calibration record is evidence of model/version-specific B2Y state, not proof of its pixel arithmetic.
- CC0/CC1 or output-color differences have highest value for the remaining skin/color mismatch.
- Tone/DG differences are retained as separate tone hypotheses rather than being used to explain color by default.
- Y_BLEND and YC CONVERSION remain invariant controls and are not promoted as model-specific color knobs.
- No renderer change should be made until a differing record's selector/driver/runtime stage is traced and an offline reproduction is supported.

## Next unresolved work

1. Trace the highest-priority changed CC/output/chroma records through selector -> setter/driver -> registers.
2. Determine whether each changed payload is copied directly, transformed, or selected conditionally.
3. For tone/DG changes, compare decoded tables independently from color-control hypotheses.
4. Reproduce any recovered control offline on existing captures before creating another Android renderer candidate.
