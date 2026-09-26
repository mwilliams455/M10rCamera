# M10-R RENDER2C POSTYC1A REFERENCE1A — FAILED PHOTOGRAPHIC GATE

Date: 2026-09-26

Branch: `m10r-render2c-reference1a`

Workflow runs:
- initial neutral-invariant discovery: `36235468667`
- neutral-preserved rerun: `36235595573`

## Result

POSTYC1A is **not** an acceptable photographic baseline.

The first validation run exposed a concrete neutral-invariance bug: feeding post-Yc reconstructed `nr/ng/nb` into COLORRECON defeated the exact neutral bypass because the Yc round trip leaves tiny numerical channel differences. An exact grey ramp differed from S by up to 2 code values.

The rerun preserved the original pre-tone neutral selector while still using post-Yc colour direction for every non-neutral pixel. That removed the implementation ambiguity, but the public Leica colour gate then failed strongly.

## Public Leica regression

Ten unchanged public M10-R RAW/JPEG pairs were used. No private household RAWs were used.

Representative per-scene target-native DeltaE76:

| Scene | S | RENDER1T | POSTYC1A |
|---|---:|---:|---:|
| 01 | 5.5848 | 2.7078 | 9.6664 |
| 02 | 2.9311 | 1.7141 | 7.1639 |
| 03 | 7.9528 | 2.9388 | 15.9928 |
| 04 | 3.5640 | 2.1332 | 6.1678 |
| 05 | 10.9629 | 3.1174 | 20.0597 |
| 06 | 11.7334 | 3.0891 | 23.4662 |
| 07 | 5.3052 | 1.8871 | 8.0029 |
| 08 | 5.8014 | 2.1771 | 9.0388 |
| 09 | 3.9682 | 2.3896 | 2.9048 |
| 10 | 3.2175 | 2.0747 | 2.9639 |

All-reference target-native aggregate:

- S L* MAE: 0.409880
- POSTYC1A L* MAE: 0.406381
- S a*b* error: 6.059950
- POSTYC1A a*b* error: 10.512891
- S DeltaE76: 6.102141
- POSTYC1A DeltaE76: 10.542735

White-normalized aggregate:

- S L* MAE: 1.268650
- POSTYC1A L* MAE: 1.264295
- S a*b* error: 5.681113
- POSTYC1A a*b* error: 10.257734
- S DeltaE76: 5.981348
- POSTYC1A DeltaE76: 10.442383

The failure is primarily colour direction, not lightness.

## Decision

Do **not** promote RENDER2C POSTYC1A.

Do not build later skin corrections on POSTYC1A as the colour baseline.

RENDER1T's pre-tone colour direction remains the stronger public-reference colour path, despite its known private tungsten issue: its broad saturation-dependent highlight shoulder can over-darken warm skin.

The next candidate should therefore preserve RENDER1T's successful colour direction and lightness anchor while replacing only the broad saturation-dependent shoulder with a narrow warm/red-highlight treatment.

## Constraints for next candidate

- Keep k=0.35.
- Keep pre-tone RENDER1T colour direction.
- Keep the established S lightness anchor.
- Preserve exact neutrals.
- Do not change exposure, WB, source matrices, MFM, CC1, GAMUT1A or TONECAL1A.
- Do not use a global saturation reduction.
- Prefer a pre-gamut red-peak/opponent compression that preserves linear lightness and scales chroma only where the recovered CC1 would create the warm-highlight red excursion.
- Validate on the ten public Leica pairs before building an APK.

