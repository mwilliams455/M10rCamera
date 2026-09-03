#!/usr/bin/env python3
"""Offline Leica M10-R aperture-priority AE oracle (research milestone v0.1).

This reproduces the production control-type-0 A-mode path recovered from the
CTRL-System image. Values are signed Q8.8 APEX unless a name ends in ``_iso``.
It intentionally models exposure allocation, not rendering or raw metering.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP


Q8 = 256
SV_STEP_Q8 = 0x0055
TV_MIN_Q8 = -0x0700
TV_MAX_Q8 = 0x0C00

# Absolute pointers in CTRL-System after accounting for the four-byte section
# prefix: ISO 0x0803A3B8, SV 0x0803B8CC, correction 0x0803B65C.
ISO_STATES = (
    3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 32, 40, 50, 64, 80, 100,
    125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600,
    2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000, 12500, 16000,
    20000, 25000, 32000, 40000, 50000, 64000, 80000, 100000, 125000,
    160000, 200000, 250000, 320000, 400000,
)

SV_STATES_Q8 = (
    0x0000, 0x0055, 0x00AE, 0x0100, 0x0155, 0x01AE, 0x0200, 0x0255,
    0x02AE, 0x0300, 0x0355, 0x03AE, 0x0400, 0x0455, 0x04AE, 0x0500,
    0x0555, 0x05AE, 0x0600, 0x0655, 0x06AE, 0x0700, 0x0755, 0x07AE,
    0x0800, 0x0855, 0x08AE, 0x0900, 0x0955, 0x09AE, 0x0A00, 0x0A55,
    0x0AAE, 0x0B00, 0x0B55, 0x0BAE, 0x0C00, 0x0C55, 0x0CAE, 0x0D00,
    0x0D55, 0x0DAE, 0x0E00, 0x0E55, 0x0EAE, 0x0F00, 0x0F55, 0x0FAE,
    0x1000, 0x1055, 0x10AE, 0x1100,
)

SV_CORRECTIONS_Q8 = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    27, 37, 39, 29, 31, 39, 47, 28, 40, 42, 29, 32, 37, 36, 31,
    44, 39, 33, 31, 24, 15, 6, 0, 6, 39, 48, 39, 39, 48, 39, 39,
    0, 0, 0, 0, 0, 0,
)

PRODUCTION_TABLE_FIRST = ISO_STATES.index(100)
PRODUCTION_TABLE_SIZE = 29
PRODUCTION_ISO_STATES = ISO_STATES[
    PRODUCTION_TABLE_FIRST : PRODUCTION_TABLE_FIRST + PRODUCTION_TABLE_SIZE
]
PRODUCTION_SV_STATES_Q8 = SV_STATES_Q8[
    PRODUCTION_TABLE_FIRST : PRODUCTION_TABLE_FIRST + PRODUCTION_TABLE_SIZE
]


def s16(value: int) -> int:
    """Return the signed 16-bit interpretation used by the firmware."""
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def ev_to_q8(value: float | str | Decimal) -> int:
    """Convert decimal EV to Q8.8, rounding halves away from zero."""
    scaled = Decimal(str(value)) * Q8
    return s16(int(scaled.to_integral_value(rounding=ROUND_HALF_UP)))


def q8_to_ev(value: int) -> float:
    return s16(value) / Q8


def iso_to_sv_q8(iso: int) -> int:
    """Firmware ISO->SV ceiling lookup (0x0801C898)."""
    if iso <= 0:
        raise ValueError("ISO must be positive")
    for state_iso, state_sv in zip(ISO_STATES, SV_STATES_Q8):
        if state_iso >= iso:
            return state_sv
    return SV_STATES_Q8[-1]


def sv_index(sv_q8: int) -> int:
    """Index calculation used for SV correction/ISO lookup.

    The binary converts Q8.8 to EV, divides by the double constant 0.333, and
    converts to integer. The valid production domain is non-negative.
    """
    sv_q8 = s16(sv_q8)
    if sv_q8 < 0:
        return 0
    if sv_q8 > 0x1100:
        return 0
    index = int((sv_q8 / Q8) / 0.333)
    return min(index, len(ISO_STATES) - 1)


def sv_to_iso(sv_q8: int) -> int:
    return ISO_STATES[sv_index(sv_q8)]


def sv_correction_q8(sv_q8: int) -> int:
    return SV_CORRECTIONS_Q8[sv_index(sv_q8)]


def round_q8_to_step(value_q8: int, step_q8: int) -> int:
    """Instruction-faithful port of the Q8.8 step helper at 0x080214A8."""
    value_q8 = s16(value_q8)
    step_q8 = s16(step_q8)
    if step_q8 <= 0:
        raise ValueError("step_q8 must be positive")

    negative = value_q8 < 0
    value = -value_q8 if negative else value_q8
    step = step_q8

    if step > Q8:
        step %= Q8
    if 0x81 <= step <= 0xFF:
        step %= 0x80
    if step == 0:
        return s16(-value if negative else value)

    remainder = value % Q8
    if remainder == 0xFF:
        value += 1
    elif remainder % step:
        if remainder % step < (step >> 1):
            while (value % Q8) % step:
                value -= 1
        else:
            while (value % Q8) % step:
                value += 1

    return s16(-value if negative else value)


def clamp(value: int, lower: int, upper: int) -> int:
    if lower > upper:
        raise ValueError("lower limit exceeds upper limit")
    return min(max(s16(value), s16(lower)), s16(upper))


@dataclass(frozen=True)
class AModeResult:
    tv_q8: int
    av_q8: int
    sv_q8: int
    dev_q8: int
    iso: int
    shutter_seconds: float
    target_ev_q8: int
    initial_correction_q8: int
    final_correction_q8: int
    auto_iso_activated: bool
    auto_iso_steps: int
    tv_iso_reached: bool
    sv_lower_bound_hit: bool
    sv_upper_bound_hit: bool
    tv_lower_bound_hit: bool
    tv_upper_bound_hit: bool
    constraint_reason: str

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        for name in (
            "tv_q8", "av_q8", "sv_q8", "dev_q8", "target_ev_q8",
            "initial_correction_q8", "final_correction_q8",
        ):
            data[name.removesuffix("_q8") + "_ev"] = q8_to_ev(data[name])
        return data


def solve_a_mode(
    *,
    bv_q8: int,
    av_q8: int,
    override_q8: int = 0,
    exposure_correction_q8: int = 0,
    tv_iso_q8: int,
    auto_iso: bool = True,
    sv_q8: int | None = None,
    sv_min_q8: int = 0x0500,
    sv_max_q8: int = 0x0E00,
    tv_min_q8: int = TV_MIN_Q8,
    tv_max_q8: int = TV_MAX_Q8,
    bracket_adjustment_q8: int = 0,
) -> AModeResult:
    """Solve the recovered production A-mode branch.

    Production control type 0 uses the 0x55 step helper, not the optional
    table-walk helper used by control types 1 and 3.
    """
    av = clamp(av_q8, 0, 0x0C00)
    sv_min = s16(sv_min_q8)
    sv_max = s16(sv_max_q8)
    if sv_min > sv_max:
        raise ValueError("SV minimum exceeds SV maximum")

    selected_sv = sv_min if auto_iso else (sv_q8 if sv_q8 is not None else sv_min)
    selected_sv = clamp(selected_sv, sv_min, sv_max)
    initial_correction = sv_correction_q8(selected_sv)
    target = s16(
        s16(bv_q8)
        + selected_sv
        - s16(override_q8)
        - s16(exposure_correction_q8)
        - initial_correction
    )
    requested_tv = s16(target - av)
    final_tv = requested_tv
    final_sv = selected_sv
    moves = 0

    if auto_iso:
        final_sv = round_q8_to_step(selected_sv, SV_STEP_Q8)
        while (
            requested_tv < s16(tv_iso_q8)
            and final_sv <= s16(sv_max - SV_STEP_Q8)
        ):
            final_sv = round_q8_to_step(final_sv + SV_STEP_Q8, SV_STEP_Q8)
            final_tv = s16(final_tv + SV_STEP_Q8)
            requested_tv = s16(requested_tv + SV_STEP_Q8)
            moves += 1

    final_tv = s16(final_tv - s16(bracket_adjustment_q8))
    unclamped_tv = final_tv
    final_tv = clamp(final_tv, tv_min_q8, tv_max_q8)
    final_correction = sv_correction_q8(final_sv)
    dev = s16(
        s16(bv_q8)
        + final_sv
        - final_tv
        - av
        - s16(override_q8)
        - s16(exposure_correction_q8)
        - final_correction
    )

    tv_iso_reached = bool(auto_iso and requested_tv >= s16(tv_iso_q8))
    sv_upper = bool(auto_iso and requested_tv < s16(tv_iso_q8))
    tv_lower = unclamped_tv < s16(tv_min_q8)
    tv_upper = unclamped_tv > s16(tv_max_q8)

    if not auto_iso:
        reason = "auto_iso_disabled"
    elif moves == 0 and requested_tv >= s16(tv_iso_q8):
        reason = "tv_iso_already_satisfied"
    elif sv_upper:
        reason = "sv_max_before_tv_iso"
    else:
        reason = "sv_raised_to_tv_iso"
    if tv_lower:
        reason += "+tv_min_clamp"
    elif tv_upper:
        reason += "+tv_max_clamp"

    return AModeResult(
        tv_q8=final_tv,
        av_q8=av,
        sv_q8=final_sv,
        dev_q8=dev,
        iso=sv_to_iso(final_sv),
        shutter_seconds=2.0 ** (-q8_to_ev(final_tv)),
        target_ev_q8=target,
        initial_correction_q8=initial_correction,
        final_correction_q8=final_correction,
        auto_iso_activated=moves > 0,
        auto_iso_steps=moves,
        tv_iso_reached=tv_iso_reached,
        sv_lower_bound_hit=final_sv <= round_q8_to_step(sv_min, SV_STEP_Q8),
        sv_upper_bound_hit=sv_upper,
        tv_lower_bound_hit=tv_lower,
        tv_upper_bound_hit=tv_upper,
        constraint_reason=reason,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bv", type=float, required=True, help="scene BV in EV")
    parser.add_argument("--av", type=float, required=True, help="aperture AV in EV")
    parser.add_argument("--tv-iso", type=float, required=True, help="Auto-ISO TV boundary in EV")
    parser.add_argument("--override", type=float, default=0.0, help="Leica Override in EV")
    parser.add_argument("--exposure-comp", type=float, default=0.0, help="exposure correction in EV")
    parser.add_argument("--iso", type=int, default=100, help="fixed ISO when Auto ISO is off")
    parser.add_argument("--sv-min-iso", type=int, default=100)
    parser.add_argument("--sv-max-iso", type=int, default=50000)
    parser.add_argument("--tv-min", type=float, default=-7.0)
    parser.add_argument("--tv-max", type=float, default=12.0)
    parser.add_argument("--bracket-adjustment", type=float, default=0.0)
    parser.add_argument("--auto-iso", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = solve_a_mode(
        bv_q8=ev_to_q8(args.bv),
        av_q8=ev_to_q8(args.av),
        override_q8=ev_to_q8(args.override),
        exposure_correction_q8=ev_to_q8(args.exposure_comp),
        tv_iso_q8=ev_to_q8(args.tv_iso),
        auto_iso=args.auto_iso,
        sv_q8=iso_to_sv_q8(args.iso),
        sv_min_q8=iso_to_sv_q8(args.sv_min_iso),
        sv_max_q8=iso_to_sv_q8(args.sv_max_iso),
        tv_min_q8=ev_to_q8(args.tv_min),
        tv_max_q8=ev_to_q8(args.tv_max),
        bracket_adjustment_q8=ev_to_q8(args.bracket_adjustment),
    )
    print(json.dumps(result.public_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
