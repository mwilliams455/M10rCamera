# WARMRED1A SUPERSEDED BY WARMRED1B

WARMRED1A completed its public-reference screen, but its implementation did not preserve the intended experiment boundary.

It recomputed the replacement colour path for every pixel and used its own red/warm selector only to change the opponent scale. Therefore non-target pixels no longer received exact RENDER1T output, and low/negative-luminance colour directions could form extremely large common-gain intermediates after removal of RENDER1T's existing saturation shoulder.

Evidence:
- public aggregate errors moved only modestly;
- however `max_linear_luma_error` reached ~5.7e8 to ~8.7e8 in the diagnostic, proving the implementation was not a valid exact-lightness/narrow-scope test.

WARMRED1A must not be interpreted as falsifying a targeted warm-highlight treatment.

WARMRED1B corrects the scope:
- exact RENDER1T output for every non-target pixel;
- only stable, red-peak, warm/highlight selected pixels are recomputed;
- selected pixels use an opponent ray around the existing linear lightness anchor;
- exact non-target equality is asserted;
- active-pixel linear-luminance preservation is gated;
- exposure, WB, source transform, MFM, Y_BLEND k, CC1, GAMUT1A and TONECAL1A remain unchanged.

No APK is authorized from WARMRED1A.
