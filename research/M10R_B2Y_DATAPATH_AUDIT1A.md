# M10-R B2Y DATAPATH AUDIT1A — configuration facts and observable limits

Date: 2026-09-07
Base: `m10r-capture1b` at `3b1e86b5055a21b548d56b23bd47f9dc66c57012`
Research branch: `m10r-b2y-datapath-audit1a`

## Result

**The exact live pixel datapath is still unresolved. This audit closes several
configuration details and proves why some proposed image tests cannot close
the remaining questions.** It does not promote another photographic renderer.

| Requested question | Established result | Remaining uncertainty |
| --- | --- | --- |
| Signal feeding MEDIUM and DG | Tone has three separately programmed 12-bit parameters, `1024, 2661, 410`, distinct from the final YC conversion coefficients. | A weighted intensity is a plausible tone-coordinate source. Channel assignment, normalization, active selector and physical location are not proven. DG's source must be resolved independently. |
| MEDIUM versus DG order | Prior v2.21 JPEG/DNG evidence supports MEDIUM→DG for first-parity rendering. | No recovered mux or block definition proves the physical edge. CPU call order cannot establish it. |
| Input scaling | STILL shift descriptor `[2,1]` programs `0x20020088` to `0x102` from a zero seed; live-view `[4,1]` gives `0x104`. | Shift direction, bit-8 meaning and propagation into the tone coordinate remain unknown. Neither 16383 nor 32767 is a proven normalized-white coordinate. |
| Limits/clamps | Four tone register words `0x2002086C..78` contain paired `0x3FFF` values. Low fields accept 15 bits and high fields 16 bits. | These are not eight proven 14-bit pixel clamps with known stage positions. Sign interpretation and sequencing remain open. |
| Q15 rounding | Explicit nonnegative truncate, half-up and ties-even candidates have been reproduced. | The CPU helper only programs hardware; it does not execute the pixel multiply. No hardware rounding rule was recovered. |
| Android implementation | Added a Java integer reference with exact assets and mandatory candidate choices, verified against independent integer calculations. | It is not connected to the active renderer and is not an exact Leica datapath or a new APK. |

## Sources and reproducibility

Canonical input firmware:

`M10-R-30.22.23.34-Customer.FW`

SHA-256:

`ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

Fresh extraction used the existing unpacker in
`.github/workflows/m10r-v135-wb-mode-switch.yml`, `tools/m10r_sections.py`, and
`tools/m10r_b2y_assets.py`. The upload lengths and both recovered asset hashes
were verified again; no calibrated bytes were changed.

| Extracted section | SHA-256 |
| --- | --- |
| `092_IMG-System.bin` | `53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4` |
| `074_IMG_Calibration_Data_data_calib_B2Y.bin.bin` | `ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b` |

Primary new artifacts:

- `tools/m10r_b2y_register_audit1a.py`
- `research/M10R_B2Y_REGISTER_AUDIT1A.json`
- `tools/m10r_b2y_scalar_audit1a.py`
- `research/M10R_B2Y_SCALAR_AUDIT1A.json`
- `reference/android/com/particlesdevs/photoncamera/m10r/M10RB2YScalarOracle.java`
- `tests/java/com/particlesdevs/photoncamera/m10r/B2YScalarProbe.java`

The register audit executes the actual bounded ARM/Thumb programmers in Unicorn
2.1.4 with synthetic MMIO storage. It does **not** emulate B2Y pixel hardware.
The tone byte-copy helper at `0x4204F2EC` is intercepted to record the requested
destination, size and source hash, copy those bytes, and return. An idle status
bit is supplied explicitly. Every other instruction must remain inside the
selected programmer. Results from synthetic descriptor probes establish CPU
packing behavior, not validity of those descriptor values on physical hardware.

## 1. Tone has a distinct three-field parameter set

Record ID `0x08`, record index 133, payload offset `0xA76D4`, is shared by
STILL/STILLLINK/SLIVE/SMAGNI LOW/MEDIUM/HIGH keys. Its fields are written by
the ARM helper `0x420D3C1C`:

| Descriptor offset | Value | Register field | Relevant firmware writes |
| --- | --- | --- | --- |
| `+0x1C` | `0x400` / 1024 | `0x20020808[11:0]` | `0x420D3D68..3D80` |
| `+0x20` | `0xA65` / 2661 | `0x20020808[27:16]` | `0x420D3D9C..3DB8` |
| `+0x24` | `0x19A` / 410 | `0x2002080C[11:0]` | `0x420D3DDC..3DF4` |

Thus zero-seeded registers become `0x0A650400` and `0x0000019A`.
All-ones synthetic values leave only 12 bits in each field. The sum is 4095.

**Inference, not a recovered equation:** if these are RGB coefficients in the
listed order and Q12, they correspond to approximately
`0.25, 0.649658203125, 0.10009765625`. Their sum is `4095/4096`, not exactly one.
Do not silently renormalize to 4095, add a rounding bias, assign RGB ordering,
or replace the current Rec.709 proxy with this formula as a hardware fact.
The selected mode could alter their use or choose another source.

There is a separately named YC conversion selector at `0x42154EC8`, ID `0x0C`,
calling `0x420D456C`. Its first three parameters are `0x4C8,0x963,0x1D5`
(1224,2403,469), summing to 4096. The familiar approximately 0.299/0.587/0.114
weights are a separate configuration, not evidence that tone consumes final Y.

**Do not assume that MEDIUM and DG use the same signal.** A shared intensity
coordinate driving a gain applied to RGB, followed by component-wise DG, remains
a possible architecture. A single DG asset does not distinguish one Y lookup
from repeated use of the same curve on three components. This possibility has
not been proved or enabled as a new renderer.

The tone descriptor also contains 18-bit/26-bit/16-bit parameter fields,
`0x5000`, `0x2CA0`, and signed-looking `0xFFFF8000` values. Their presence is
another reason not to equate the complete tone block with an unqualified
`x * table[x>>1]` formula.

## 2. Concrete upstream shift control

`img_b2y_select_shift_paraset` starts at `0x42154938`. It selects ID `0x03`
at `0x4215496A..6E` and calls Thumb helper `0x420D35E0` at `0x4215498A`.

| Mode keys | Descriptor | CPU programming |
| --- | --- | --- |
| STILL / STILLLINK | `[2,1]` | register low nibble = 2; bit 8 = 1 |
| SLIVE / SMAGNI | `[4,1]` | register low nibble = 4; bit 8 = 1 |

Exact register update:

```text
reg[0x20020088] =
    (old & ~0x10F) | (descriptor[0] & 0xF)
                   | ((descriptor[1] & 1) << 8)
```

The low-level fallback writes the STILL values `[2,1]` too. These are real
configuration facts, but `2` must not be relabelled `>>2`, `<<2`, or `×4`
without evidence for the flag and shift semantics. There is no pixel shift
instruction in this programmer; its shifts pack the configuration word.

## 3. The “14-bit clamps” need precise wording

The tone descriptor `+0x78..+0x94` supplies eight `0x3FFF` values:

| Descriptor pair | Register | Accepted CPU payload bits |
| --- | --- | --- |
| `+0x78 / +0x7C` | `0x2002086C` | low field 15; high field 16 |
| `+0x80 / +0x84` | `0x20020870` | low field 15; high field 16 |
| `+0x88 / +0x8C` | `0x20020874` | low field 15; high field 16 |
| `+0x90 / +0x94` | `0x20020878` | low field 15; high field 16 |

For example, `+0x78=0xFFFFFFFF` produces `0x3FFF7FFF` at `0x2002086C`;
`+0x7C=0xFFFFFFFF` produces `0xFFFF3FFF`. These results follow the original
instructions at `0x420D40D8..41E4`, not a register-mask model written by us.

This establishes configured values and containers. It does not establish
signedness, semantic labels, a hardware input width of 14 bits, or whether any
limit is before/after multiplication or applies to a coordinate/component.

## 4. Saturation and tests that cannot discriminate

The expanded DG is exactly reproduced from all 2048 coarse anchors and their
fine increments at all 32768 addresses. First saturation is **14800 / 0x39D0**.
The previous values at 14796..14799 are 16382.

For the existing first-parity model, MEDIUM followed directly by DG first
saturates at **14710** under all three tested nonnegative rounding modes.
These thresholds are facts about the assets and the stated composition; they
are not a recovered normalization of real scene white.

Over every integer input `0..20479`, for MEDIUM→DG, the following yield
identical final output under each of the three rounding modes:

- no added 14-bit clamp;
- a 14-bit clamp on input;
- a 14-bit clamp after each stage;
- a 14-bit clamp on final output.

The plateau hides differences at these candidate clamp positions. Therefore
even noiseless neutral output samples of this scalar model cannot identify
the clamp sequence. Do not spend another image-fitting round selecting one
of these equivalent neutral curves and call it hardware proof. This finding
does not extend automatically to RGB-coupled, signed, bypassed or other-table
hardware paths.

Similarly, the table's address capacity does not justify mapping `[0,1]` onto
`[0,32767]`. Under the current direct composition the plateau would already be
reached near 0.449 of that chosen scale. Mapping to 16383 reaches it near 0.898.
Neither choice is proven. Renormalizing at 14800 is also unsupported and ignores
the distinct MEDIUM→DG saturation coordinate 14710.

## 5. Exact rounding candidates and their observability

For a nonnegative product `p = sample * Q15gain`, we implemented:

```text
truncate:  floor(p / 32768)
half-up:   floor((p + 16384) / 32768)
ties-even: nearest integer, with exactly-halfway results rounded to even
```

The Java multiply uses a 64-bit product and throws on an out-of-contract result.
It does not quietly clamp an invalid coordinate or reinterpret negative samples.
Signed paths would need their own explicitly recovered arithmetic contract.

| Comparison over 20480 MEDIUM scalar coordinates | Different outputs | Maximum delta |
| --- | --- | --- |
| Truncate vs half-up, after MEDIUM | 8442 | 1 |
| Truncate vs half-up, after DG | 4159 | 12 |
| Half-up vs ties-even, after MEDIUM | 2 | 1 |
| Half-up vs ties-even, after DG | 0 | 0 |

Exact halfway products occur at coordinates 4864, 10240 and 10368. At 4864,
half-up and ties-even agree. They differ at 10240 and 10368, but DG hides both
differences. Thus default scalar MEDIUM→DG output cannot distinguish these two
nearest-rounding conventions. Also, “only a one-code rounding effect” is true
at the tone output, not throughout the following DG stage.

## 6. What the three handoff addresses actually offer

- `0x42151F28`: mode-dependent geometry preparation. Visible branches write
  dimensions including 1920, 1080, 4096 and 2160 into the object. These are not
  tone coordinates. The inline switch table after the dispatch-helper call is
  data and must not be treated as pixel instructions.
- `0x4215220C`: a high-level mode/configuration programmer. It builds a stack
  descriptor, sets clock/interrupt controls, moves gains/matrices, and dispatches
  further configuration. Its call sequence is not the hardware pixel graph.
- `0x42160D40`: obtains an object from the `context+0x1D50+4*slot` table after
  ownership/descriptor checks. It is not a tone/DG pixel consumer.

These findings support moving the next investigation to the shift semantics,
tone-mode fields and a genuinely discriminating hardware observation, rather
than repeatedly scanning these entry points for a Q15 multiply.

## 7. Android reference and validation boundary

`M10RB2YScalarOracle` accepts the exact firmware asset bytes and validates both
SHA-256 hashes. It contains:

- exact expanded DG coordinate access;
- Q15 arithmetic with explicit rounding;
- `toneAt(sample, coordinate, rounding)` so a lookup coordinate can be distinct
  from the component receiving the gain;
- scalar order/clamp candidates with mandatory choices;
- strict input contracts and no implicit normalized-linear mapping or OETF.

Host verification compiled the reference to Java 8 with Eclipse ECJ 3.37.0 and
ran it on Java 17. It checked **585926 u16 outputs** against Python integer
calculations, all DG addresses against independent coarse/fine reconstruction,
and rejection of altered assets and invalid coordinates. The output stream hash:

`bafa9b29bc38c63f9533cb0c4cefa7e580b1b3c129e4536654de16277b921ab5`

This is software conformance to explicit candidates, **not** a hardware oracle
comparison. No Android APK build or device validation was performed for this
reference, and no active photographic patch or workflow was changed.

Reproduce with a JDK and Python `unicorn==2.1.4`:

```bash
python3 tools/m10r_b2y_register_audit1a.py /path/to/sections /tmp/register-audit.json
python3 tools/m10r_b2y_scalar_audit1a.py /path/to/assets /tmp/scalar-audit.json
```

On a JRE-only host, the second command accepts `--ecj-jar /path/to/ecj-3.37.0.jar`.
The existing firmware unpacker and extractor provide the input sections/assets.

## 8. Next evidence that would change the implementation

1. Resolve bit 8 and the low nibble of `0x20020088` from register definitions,
   a second diagnostic path that actually computes its semantics, or a
   controlled pre/post-shift hardware measurement.
2. Resolve tone `0x20020804` mode fields and the semantic assignments of the
   three 12-bit parameters. Establish the source before choosing weights or
   deciding where CC1 belongs relative to the nonlinear operations.
3. Trace DG's source independently. Compare nonneutral genuine Leica reference
   patches only after accounting for WB and CC0/CC1. A shared tone gain plus
   component-wise DG is a distinct hypothesis from both existing TONEDG1A/B.
4. For clamp/rounding precision, obtain an intermediate signal, a documented
   hardware rule, or a controlled path where the final DG plateau does not hide
   the differences. More neutral MEDIUM→DG JPEG fits cannot solve the proven
   observational equivalences.
5. Establish DG output transfer semantics. The current use of another sRGB
   transfer after DG is also an implementation assumption; neither this audit
   nor the earlier fitted nuisance gamma proves it correct or incorrect.

Once the signal, mapping and arithmetic are actually established, wire the
reference kernel into the Android renderer with independent stage vectors.
Preserve RGBORDER1A, SOURCECM1A, capture exposure, exact assets, sRGB output,
single-frame RAW and no-HDR behavior. Avoid using saturation or EV tuning to
stand in for the missing hardware interpretation.

## Prior research retained

- v1.89: exact DG coarse/fine representation.
- v1.92 and v2.11: Q15/index functional model, 10240 active tone entries,
  unresolved hardware arithmetic boundary.
- v2.09: physical ordering not established by programmer order.
- v2.14/v2.18: identical alternate tone banks and recovered nonlinear enables.
- v2.21: empirical MEDIUM→DG order for first-parity rendering.
- v2.32: firmware CC0/CC1 matrix roles; nonlinear placement still requires the
  separate physical-source evidence above.

No uncertain result in this audit is labelled frozen hardware behavior.
