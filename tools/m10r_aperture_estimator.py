#!/usr/bin/env python3
"""Executable model of the recovered M10-R ambient/TTL aperture estimator.

The M10-R estimates working aperture by comparing the front external ambient
brightness coordinate (BvExt) with the through-lens brightness coordinate and
adding the calibrated AV0 reference.  All exposure coordinates are signed
Q8.8 APEX values.

The optional remap table is runtime-configurable firmware state, so callers may
supply the recovered threshold array.  Omitting it models the estimator before
that optional remap stage.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

Q8 = 256
HALF_STOP_Q8 = 0x80
RAW_DEADBAND_Q8 = 0x41  # update only outside +/-65 counts
DEFAULT_AV_MIN_Q8 = 0x0000
DEFAULT_AV_MAX_Q8 = 0x0C00

# Firmware half-stop table at 0x0803D310.  Values are Q8.8 f-numbers and use
# Leica/camera canonical labels rather than the exact mathematical sqrt(2)
# sequence.
CANONICAL_FNUMBER_Q8 = (
    0x0100, 0x0133, 0x0166, 0x01B3, 0x0200,
    0x0266, 0x02CD, 0x0366, 0x0400, 0x04CD,
    0x059A, 0x06CD, 0x0800, 0x0980, 0x0B00,
    0x0D00, 0x1000, 0x1300, 0x1600, 0x1B00,
    0x2000, 0x2600, 0x2D00, 0x3600, 0x4000,
)


@dataclass(frozen=True)
class ApertureEstimate:
    raw_candidate_q8: int
    filtered_raw_q8: int
    quantized_q8: int
    remapped_q8: int
    av_q8: int
    fnumber_q8: int
    fnumber_x1000: int
    deadband_updated: bool
    remap_used: bool
    lower_bound_hit: bool
    upper_bound_hit: bool

    @property
    def av_ev(self) -> float:
        return self.av_q8 / Q8

    @property
    def fnumber(self) -> float:
        return self.fnumber_x1000 / 1000.0


def s16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def clamp(value: int, lower: int, upper: int) -> int:
    if lower > upper:
        raise ValueError("lower bound exceeds upper bound")
    return min(max(int(value), int(lower)), int(upper))


def raw_aperture_candidate_q8(
    *,
    bv_ext_q8: int,
    ttl_bv_q8: int,
    av0_q8: int,
    force_reference: bool = False,
) -> int:
    """Recover the pre-filter Av estimate used by 0x0800F98C.

    Normal path:
        BvExt - TTL_Bv + AV0

    Either firmware override flag forces 0x0400 (Av=4) instead.
    Negative normal-path values are clamped to zero before temporal filtering.
    """
    if force_reference:
        return 0x0400
    return max(0, s16(bv_ext_q8) - s16(ttl_bv_q8) + s16(av0_q8))


def apply_raw_deadband(candidate_q8: int, prior_raw_q8: int) -> tuple[int, bool]:
    """Apply the persistent +/-0x41-count aperture-estimate deadband.

    The firmware updates only when candidate > prior+65 or candidate < prior-65.
    Equality at either edge retains the prior value.
    """
    candidate = int(candidate_q8)
    prior = int(prior_raw_q8)
    if candidate > prior + RAW_DEADBAND_Q8 or candidate < prior - RAW_DEADBAND_Q8:
        return candidate, True
    return prior, False


def quantize_half_stop_down(av_q8: int) -> int:
    """Firmware `BICS value,#0x7f` stage after non-negative filtering."""
    if av_q8 < 0:
        raise ValueError("aperture estimate must be non-negative before quantization")
    return int(av_q8) & ~0x7F


def threshold_remap_q8(av_q8: int, thresholds_q8: Sequence[int]) -> int:
    """Map a quantized Av through the optional firmware threshold table.

    The consumer tests threshold indices 0..21 and returns index*0x80 for the
    first threshold >= input.  A supplied table must therefore contain at
    least 22 entries when this stage is enabled.
    """
    if len(thresholds_q8) < 22:
        raise ValueError("firmware aperture remap requires at least 22 thresholds")
    value = s16(av_q8)
    index = 0
    while True:
        threshold = s16(int(thresholds_q8[index]))
        if threshold >= value or index >= 0x15:
            return index * HALF_STOP_Q8
        index += 1


def av_q8_to_fnumber_q8(av_q8: int) -> int:
    """Model the core Av->f-number conversion at 0x0801CBFC.

    Exact half-stop Av values use the canonical firmware lookup table.  Other
    values use f=2^(Av/2) and are represented as Q8.8 before final display/
    metadata rounding.
    """
    av = int(av_q8)
    if av < 0:
        av = 0

    if av % HALF_STOP_Q8 == 0:
        idx = av // HALF_STOP_Q8
        if 0 <= idx < len(CANONICAL_FNUMBER_Q8):
            return CANONICAL_FNUMBER_Q8[idx]

    f = 2.0 ** ((av / Q8) / 2.0)
    # Firmware converts the floating result back to a fixed-point integer.
    # Positive conversion is truncating at this stage.
    return max(0, min(0xFFFF, int(f * Q8)))


def fnumber_q8_to_x1000(fnumber_q8: int) -> int:
    """Return the firmware's rounded human/metadata f-number representation.

    The converter scales the real f-number by 1000 and rounds to the nearest
    100, yielding values such as 1400, 2800, 5600, 11000, ...
    """
    raw = int((int(fnumber_q8) / Q8) * 1000.0)
    remainder = raw % 100
    return raw - remainder + (100 if remainder >= 50 else 0)


def estimate_aperture(
    *,
    bv_ext_q8: int,
    ttl_bv_q8: int,
    av0_q8: int,
    prior_raw_q8: int,
    force_reference: bool = False,
    remap_enabled: bool = False,
    remap_thresholds_q8: Sequence[int] | None = None,
    av_min_q8: int = DEFAULT_AV_MIN_Q8,
    av_max_q8: int = DEFAULT_AV_MAX_Q8,
) -> ApertureEstimate:
    candidate = raw_aperture_candidate_q8(
        bv_ext_q8=bv_ext_q8,
        ttl_bv_q8=ttl_bv_q8,
        av0_q8=av0_q8,
        force_reference=force_reference,
    )
    filtered, updated = apply_raw_deadband(candidate, prior_raw_q8)
    quantized = quantize_half_stop_down(filtered)

    if remap_enabled:
        if remap_thresholds_q8 is None:
            raise ValueError("remap thresholds are required when remap is enabled")
        remapped = threshold_remap_q8(quantized, remap_thresholds_q8)
    else:
        remapped = quantized

    bounded = clamp(remapped, av_min_q8, av_max_q8)
    f_q8 = av_q8_to_fnumber_q8(bounded)
    f_x1000 = fnumber_q8_to_x1000(f_q8)
    return ApertureEstimate(
        raw_candidate_q8=candidate,
        filtered_raw_q8=filtered,
        quantized_q8=quantized,
        remapped_q8=remapped,
        av_q8=bounded,
        fnumber_q8=f_q8,
        fnumber_x1000=f_x1000,
        deadband_updated=updated,
        remap_used=bool(remap_enabled),
        lower_bound_hit=remapped < av_min_q8,
        upper_bound_hit=remapped > av_max_q8,
    )
