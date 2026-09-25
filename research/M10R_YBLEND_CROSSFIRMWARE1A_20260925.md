# M10-R Y_BLEND CROSSFIRMWARE1A — CALIBRATION + DRIVER STABLE ACROSS THREE RELEASES

Date: 2026-09-25

Repository: `mwilliams455/M10rCamera`

Research branch: `m10r-yblend-crossfirmware1a`

Successful Actions run: `36176600904`

Validated source commit: `8f32483143a9b0c1f6825b20eab6a0d36f59b1eb`

Artifact: `M10R-YBLEND-CROSSFIRMWARE1A-RESULTS` (ID `10882737252`)

## Scope

This pass compares Y BLEND calibration and the original IMG Y BLEND register programmer across three independently downloaded M10-R firmware releases:

- 20.20.47.37
- 30.22.11.52
- 30.22.23.34

This is firmware/calibration evidence. It does not recover the B2Y hardware pixel equation and does not change renderer/capture code.

## 1. Firmware and decoded images are genuinely different

Firmware SHA256:

- 20.20.47.37: `141f0b5fcffe315372bc2c673a3dfa371eab84198d46d6de26016ec0958d77b2`
- 30.22.11.52: `1dd1dd2109bcf0d1b5bee3cc787e15a876974d38ec5877216dadd451d192c896`
- 30.22.23.34: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

Decoded firmware SHA256 values also differ. IMG-System differs between 20.20.47.37 and the 30.22 generation.

Therefore equality below is not caused by accidentally comparing the same firmware file.

## 2. Entire B2Y calibration section is byte-identical

All three firmware versions contain the exact same B2Y calibration section:

`ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b`

This is stronger than record-level equality: the complete extracted `IMG Calibration Data/data/calib/B2Y.bin` is unchanged.

## 3. Y BLEND record 0x0D is byte-identical

All three versions:

```
[0, 32, 16383, 16383, 16383, 16383]
```

Payload SHA256:

`cab40e527bfbe6b8a5cd0450a668f46d5d6569ee8405e89fdf7e1455f1492b50`

It occurs at the active record offset `0x131874` and trailing duplicate/default offset `0x1349b4` in every compared release.

## 4. YC CONVERSION record 0x0C is also byte-identical

Matrix in all three:

```
 1224,  2403,   469
 -691, -1357,  2048
 2048, -1715,  -333
```

Tail values remain six `0x3FFF` values.

Record SHA256:

`bbf2a327fe94fcac3ae2a4d526cf430fe43d20999daecdfcdf6e4d74baece54f`

## 5. SAM7 image is byte-identical

The complete extracted IMG-SAM7 section is identical across the three releases:

`c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae`

Thus the SAM7 YCC/Y BLEND programmer does not change across this release span.

## 6. IMG Y BLEND code relocates but its driver bytes are identical

20.20.47.37:

- selector function: `0x151F10`
- record lookup call: `0x151F44 -> 0x19DFE0`
- Y BLEND driver call: `0x151F60 -> 0xD1A70`

30.22.11.52 / 30.22.23.34:

- selector function: `0x154E18`
- record lookup call: `0x154E4C -> 0x1A0FC4`
- Y BLEND driver call: `0x154E68 -> 0xD4480`

Despite relocation, the first 0xF0 bytes of the recovered Y BLEND driver have the same SHA256 in all three:

`632bbc8e6573b7ba2e2b924cf2d087e0950698dce10c31dd109509a71cea11af`

This is direct code identity, not merely equivalent output.

## 7. Original driver execution is identical

The dynamically located original Thumb driver was executed for each firmware.

Normal record produces in every release:

- `0x2002092C = 0x00002000`
- `0x20020930 = 0x3FFF3FFF`
- `0x20020934 = 0x3FFF3FFF`

Fallback produces in every release:

- `0x2002092C = 0x00000000`
- `0x20020930 = 0x80007FFF`
- `0x20020934 = 0x80007FFF`

Bit-15 mutations: zero.

## 8. Constraint established

Across three distinct M10-R firmware releases:

- B2Y calibration is unchanged;
- Y BLEND record is unchanged;
- YC CONVERSION record is unchanged;
- SAM7 implementation is unchanged;
- IMG Y BLEND driver code is byte-identical after relocation;
- normal/fallback execution behavior is unchanged.

This strongly constrains Y BLEND as a stable hardware configuration for this M10-R generation, rather than a scene-dependent or firmware-generation-specific photographic tuning coefficient.

It still does **not** establish what p1=32 means numerically inside the ASIC, nor the meaning of the paired 0x3FFF values.

## 9. Earliest 10.20.27.20 attempt

Firmware 10.20.27.20 is documented publicly, but the archived direct firmware URLs tested in CI were no longer retrievable. It is not included in the validated equality set above.

Do not treat the failed download as evidence about that firmware's calibration.

## 10. Next discriminator

The highest-value next comparison is the M10 Monochrom (Typ 6376), which is hardware-adjacent but has a fundamentally different monochrome imaging path.

If the same Y BLEND/YCC configuration is present there, that would further argue against treating the record as a model-specific color-look or skin tuning control. If it differs, the exact field deltas become useful semantic evidence.

No renderer k-change should be promoted from this cross-firmware result.
