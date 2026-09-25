# M10-R Y_BLEND CROSSMODEL1A — M10-R / M10 MONOCHROM INVARIANT CORE

Date: 2026-09-25

Repository: `mwilliams455/M10rCamera`

Research branch: `m10r-yblend-crossmodel1a`

Successful Actions run: `36177432922`

Validated source commit: `779af17a2e48a86e9736f64586859092ec1cffee`

Artifact: `M10R-YBLEND-CROSSMODEL1A-RESULTS` (ID `10883340196`)

## Scope

This pass compares the actual B2Y Y BLEND / YC CONVERSION configuration between:

- Leica M10-R firmware 20.20.47.37
- Leica M10 Monochrom firmware 2.12.8.0
- Leica M10 Monochrom firmware 3.21.2.50

The comparison uses independently downloaded firmware images, the same verified M10-family unpacker, structural B2Y identification where early firmware lacks full section-path names, dynamic Y BLEND selector/driver recovery, and execution of the original Thumb register programmer.

This is firmware/calibration evidence. It does not recover the ISP pixel equation and does not modify renderer/capture code.

## 1. The full B2Y calibration is model/version dependent

B2Y SHA256:

- M10-R 20.20.47.37:
  `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b`
- M10 Monochrom 2.12.8.0:
  `03962ff3588c6331e95d77d3068ca2b5a95b3bfa504143aa5412a97fd7dca817`
- M10 Monochrom 3.21.2.50:
  `c73ca157b8f49783a6331e9c80025301de94ad4c01e615d9818d3b8942121588`

Therefore the full B2Y calibration is not shared wholesale between M10-R and M10 Monochrom, and the Monochrom B2Y calibration itself changed between the two tested releases.

This provides a useful control: the comparison is sensitive enough to see real B2Y calibration changes.

## 2. Actual Y BLEND record 0x0D is nevertheless byte-identical

All three tested firmware images contain:

```
[0, 32, 16383, 16383, 16383, 16383]
```

Payload SHA256:

`cab40e527bfbe6b8a5cd0450a668f46d5d6569ee8405e89fdf7e1455f1492b50`

Thus the two six-bit controls and four paired-field values are identical between the color M10-R and the monochrome M10 Monochrom, despite the surrounding B2Y calibration being different.

## 3. YC CONVERSION record 0x0C is also byte-identical

All three use the exact same record:

```
 1224,  2403,   469
 -691, -1357,  2048
 2048, -1715,  -333
```

with six trailing `0x3FFF` values.

Payload SHA256:

`bbf2a327fe94fcac3ae2a4d526cf430fe43d20999daecdfcdf6e4d74baece54f`

## 4. SAM7 implementation is byte-identical

All three extracted IMG-SAM7 sections have SHA256:

`c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae`

So the SAM7 YCC/Y BLEND programming implementation is shared exactly across the tested M10-R / M10 Monochrom firmware.

## 5. IMG Y BLEND driver is byte-identical after relocation

Recovered driver offsets differ by firmware:

- M10-R 20.20.47.37: `0xD1A70`
- M10 Monochrom 2.12.8.0: `0xD104C`
- M10 Monochrom 3.21.2.50: `0xD1930`

But the first `0xF0` bytes of each recovered driver have the same SHA256:

`632bbc8e6573b7ba2e2b924cf2d087e0950698dce10c31dd109509a71cea11af`

This is exact code identity after relocation.

## 6. Original driver execution is identical

For all three firmware images, executing the dynamically recovered original Thumb driver with the exact record produces:

Normal:

- `0x2002092C = 0x00002000`
- `0x20020930 = 0x3FFF3FFF`
- `0x20020934 = 0x3FFF3FFF`

Fallback:

- `0x2002092C = 0x00000000`
- `0x20020930 = 0x80007FFF`
- `0x20020934 = 0x80007FFF`

Bit-15 mutations: zero.

## 7. Strong constraint

The tested evidence now separates two facts:

1. **B2Y calibration can and does vary by model/version.**
2. **Y BLEND record 0x0D, YC CONVERSION record 0x0C, the SAM7 implementation, and the IMG Y BLEND driver remain exact invariants across those changes.**

Therefore Y BLEND should no longer be treated as a plausible M10-R-specific color-look or skin-tuning knob.

It remains possible—and likely—that Y BLEND is an important generic hardware operation whose exact arithmetic must still be replicated. But changing an arbitrary Android global `k` is not equivalent to recovering Leica's model-specific photographic color behavior.

## 8. Renderer implication

Keep the architectural correction that moved CC1 to the recovered post-Yc boundary.

Do not promote the experimental `k=0.45` probe as Leica behavior.

The remaining M10-R skin/color mismatch should now be investigated by:

- recovering the actual generic Y BLEND pixel operation; and
- separately tracing B2Y records that **do** differ between M10-R and M10 Monochrom / between Monochrom releases.

The latter is now especially valuable because this comparison has a built-in control: record 0x0C/0x0D are invariant while other B2Y content changes.

## 9. Next task

Create a record-by-record B2Y cross-model diff:

- enumerate record IDs, sizes, payload hashes, and duplicate groups;
- identify which common records differ between M10-R and M10 Monochrom;
- map those differing records back to the existing selector inventory and named B2Y controls;
- prioritize differences associated with CC0/CC1, tone, DG, output color, chroma suppression, or other photographic color stages;
- keep Y BLEND / YC CONVERSION marked as invariant controls.

This should narrow the remaining photographic color problem without another arbitrary renderer tuning pass.
