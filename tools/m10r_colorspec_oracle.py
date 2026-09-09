#!/usr/bin/env python3
"""Executable first-parity oracle for the recovered Leica M10-R CA9 ColorSpec core.

This module implements only rules already frozen from firmware evidence.  It is
intentionally explicit about boundaries that are not yet byte-for-byte closed.

Frozen here:
  * DNG AsShotNeutral -> CA9 integer WB gains (empirical first-parity inverse)
  * DNG CM fixed-rational -> 3x3 profile matrix expansion
  * Leica reciprocal-temperature dual-illuminant matrix interpolation
  * Leica stored Bradford pair and chromatic adaptation construction
  * 3x3 matrix/vector algebra used by CA9
  * fixed Leica PCS<->internal-working-RGB matrices
  * default-still sRGB CC1 matrix
  * rendered-CC coefficient representation and explicit-scale quantization
  * rendered-CC finite coefficient rounding: nearest, ties away from zero
  * rendered-CC automatic scale search: scaleCode 0..3 in increasing order,
    accepting the first candidate whose rounded q coefficients all fit
    [-2048,+2047]

v2.69 evidence closure:
  * rounding is firmware-proven from 0x40012940 plus Thumb 0x400133D0;
  * the scale-search caller rounds before range testing and advances the scale
    code one-by-one, so rounding can affect both q coefficients and scaleCode.

Not silently invented here:
  * DNG illuminant-enum -> exact firmware T1/T2 parser bridge
  * complete xy->temperature table routine / NeutralToXY end-to-end driver
  * unresolved +0x26 rendered-record halfword
  * rendered-CC MAC/output fixed-point arithmetic after record decode

Those boundaries are parameters or separate future closures rather than SDK
assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Vector3 = tuple[float, float, float]
XY = tuple[float, float]

GAIN_MIN = 1
GAIN_MAX = 2000
ASN_SCALE = 256.0
CC_MIN = -2048
CC_MAX = 2047
RENDERED_CC_SCALE_CODES = (0, 1, 2, 3)

# Firmware-stored matrices; preserve stored precision rather than recomputing.
BRADFORD: Matrix3 = (
    (0.8951, 0.2664, -0.1614),
    (-0.7502, 1.7135, 0.0367),
    (0.0389, -0.0685, 1.0296),
)
BRADFORD_INV: Matrix3 = (
    (0.9869929, -0.1470543, 0.1599627),
    (0.4323053, 0.5183603, 0.0492912),
    (-0.0085287, 0.0400428, 0.9684867),
)
PCS_TO_INTERNAL: Matrix3 = (
    (1.3460, -0.2556, -0.0511),
    (-0.5446, 1.5082, 0.0205),
    (0.0000, 0.0000, 1.2123),
)
INTERNAL_TO_PCS: Matrix3 = (
    (0.7977, 0.1352, 0.0313),
    (0.2880, 0.7119, 0.0001),
    (0.0000, 0.0000, 0.8249),
)
# Default still path: sRGB. Stored field-1 internal-working-RGB -> sRGB.
DEFAULT_SRGB_CC1: Matrix3 = (
    (1.3895, -0.1693, -0.2202),
    (-0.2288, 1.2317, -0.0029),
    (-0.0176, -0.0963, 1.1139),
)
D50_XY: XY = (0.3457, 0.3585)
NEUTRAL_TO_XY_EPSILON = 1.0e-7
NEUTRAL_TO_XY_MAX_PASSES = 15
NEUTRAL_TO_XY_AVERAGE_PASS = 14


@dataclass(frozen=True)
class RenderedCCRecord:
    coeff: tuple[int, int, int, int, int, int, int, int, int]
    scale_code: int
    kelvin: int

    @property
    def denominator(self) -> int:
        return 1 << (9 - self.scale_code)

    def decoded_matrix(self) -> Matrix3:
        d = float(self.denominator)
        v = [x / d for x in self.coeff]
        return ((v[0], v[1], v[2]), (v[3], v[4], v[5]), (v[6], v[7], v[8]))


def _matrix3(m: Sequence[Sequence[float]]) -> Matrix3:
    if len(m) != 3 or any(len(row) != 3 for row in m):
        raise ValueError("expected 3x3 matrix")
    return tuple(tuple(float(v) for v in row) for row in m)  # type: ignore[return-value]


def matrix_from_fixed_rationals(coeff: Sequence[int], denominator: int) -> Matrix3:
    if len(coeff) != 9:
        raise ValueError("expected nine matrix coefficients")
    if denominator == 0:
        raise ValueError("matrix denominator must be non-zero")
    v = [float(x) / float(denominator) for x in coeff]
    return ((v[0], v[1], v[2]), (v[3], v[4], v[5]), (v[6], v[7], v[8]))


def mat_mul(a: Matrix3, b: Matrix3) -> Matrix3:
    return tuple(
        tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3))
        for r in range(3)
    )  # type: ignore[return-value]


def mat_vec_mul(a: Matrix3, v: Vector3) -> Vector3:
    return tuple(sum(a[r][k] * v[k] for k in range(3)) for r in range(3))  # type: ignore[return-value]


def mat_diag(v: Vector3) -> Matrix3:
    return ((v[0], 0.0, 0.0), (0.0, v[1], 0.0), (0.0, 0.0, v[2]))


def mat_det(m: Matrix3) -> float:
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def mat_inv(m: Matrix3) -> Matrix3:
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = mat_det(m)
    if not math.isfinite(det) or abs(det) <= 1.0e-15:
        raise ValueError("singular/invalid matrix")
    inv = (
        ((e * i - f * h), (c * h - b * i), (b * f - c * e)),
        ((f * g - d * i), (a * i - c * g), (c * d - a * f)),
        ((d * h - e * g), (b * g - a * h), (a * e - b * d)),
    )
    s = 1.0 / det
    return tuple(tuple(x * s for x in row) for row in inv)  # type: ignore[return-value]


def xyz_to_xy(xyz: Vector3) -> XY:
    total = xyz[0] + xyz[1] + xyz[2]
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("XYZ sum must be positive and finite")
    return (xyz[0] / total, xyz[1] / total)


def xy_to_xyz(xy: XY) -> Vector3:
    x, y = xy
    if y <= 0.0 or x < 0.0 or x + y > 1.0:
        raise ValueError("invalid xy chromaticity")
    # Firmware successful tail: Y=1, X=x/y, Z=(1-x-y)/y.
    return (x / y, 1.0, (1.0 - x - y) / y)


def recover_ca9_gains(as_shot_neutral: Sequence[float]) -> tuple[int, int, int]:
    if len(as_shot_neutral) != 3:
        raise ValueError("AsShotNeutral must contain three channels")
    out: list[int] = []
    for n in as_shot_neutral:
        if n <= 0.0 or not math.isfinite(n):
            raise ValueError("AsShotNeutral channels must be positive and finite")
        # Python round is ties-to-even. The validated M10-R reference samples are
        # far from half ties; this remains an empirical first-parity ASN inverse,
        # separate from the now-proven rendered-CC coefficient round helper.
        g = int(round(ASN_SCALE / n))
        out.append(min(GAIN_MAX, max(GAIN_MIN, g)))
    return (out[0], out[1], out[2])


def gains_to_firmware_neutral(gains: Sequence[int]) -> Vector3:
    if len(gains) != 3:
        raise ValueError("expected three gains")
    g = tuple(min(GAIN_MAX, max(GAIN_MIN, int(v))) for v in gains)
    return (ASN_SCALE / g[0], ASN_SCALE / g[1], ASN_SCALE / g[2])


def interpolate_matrix(t1: float, t2: float, m1: Matrix3, m2: Matrix3, current: float) -> Matrix3:
    if not all(math.isfinite(x) and x > 0.0 for x in (t1, t2, current)):
        raise ValueError("temperatures must be positive finite values")
    if t1 >= t2:
        raise ValueError("expected T1 < T2")
    if current <= t1:
        return m1
    if current >= t2:
        return m2
    g = (1.0 / current - 1.0 / t2) / (1.0 / t1 - 1.0 / t2)
    return tuple(
        tuple(g * m1[r][c] + (1.0 - g) * m2[r][c] for c in range(3))
        for r in range(3)
    )  # type: ignore[return-value]


def map_white_matrix(src_xy: XY, dst_xy: XY) -> Matrix3:
    """Leica MapWhiteMatrix using the firmware-stored Bradford pair."""
    src = mat_vec_mul(BRADFORD, xy_to_xyz(src_xy))
    dst = mat_vec_mul(BRADFORD, xy_to_xyz(dst_xy))
    if any(abs(v) <= 1.0e-15 for v in src):
        raise ValueError("source white produces zero Bradford component")
    ratios: Vector3 = (dst[0] / src[0], dst[1] / src[1], dst[2] / src[2])
    return mat_mul(BRADFORD_INV, mat_mul(mat_diag(ratios), BRADFORD))


def ca9_cc0_from_set_white(set_white_matrix: Matrix3, returned_gains: Vector3) -> Matrix3:
    """Frozen v2.32 CC0 constructor once SetWhiteXY has produced its matrix."""
    return mat_mul(PCS_TO_INTERNAL, mat_mul(set_white_matrix, mat_diag(returned_gains)))


def default_cc1() -> Matrix3:
    return DEFAULT_SRGB_CC1


def round_half_away_from_zero(v: float) -> int:
    """Firmware-proven finite CC coefficient rounding (v2.69)."""
    if not math.isfinite(v):
        raise ValueError("cannot quantize non-finite value")
    if v >= 0.0:
        return int(math.floor(v + 0.5))
    return int(math.ceil(v - 0.5))


def _rounded_cc_coeff(matrix: Matrix3, scale_code: int) -> tuple[int, int, int, int, int, int, int, int, int]:
    if int(scale_code) not in RENDERED_CC_SCALE_CODES:
        raise ValueError("rendered-CC scale_code must be one of 0,1,2,3")
    denominator = 1 << (9 - int(scale_code))
    flat = [matrix[r][c] for r in range(3) for c in range(3)]
    return tuple(round_half_away_from_zero(v * denominator) for v in flat)  # type: ignore[return-value]


def quantize_rendered_cc(matrix: Matrix3, scale_code: int, kelvin: int) -> RenderedCCRecord:
    """Build the proven fields of the 0x2C record at an explicit scale code.

    This preserves the historical oracle API: an explicitly requested scale is
    encoded and saturated to the recovered signed field range.  New code that
    wants firmware automatic scale selection should call select_rendered_cc_scale.
    """
    q0 = _rounded_cc_coeff(matrix, scale_code)
    q = tuple(min(CC_MAX, max(CC_MIN, x)) for x in q0)
    return RenderedCCRecord(q, int(scale_code), int(kelvin))  # type: ignore[arg-type]


def select_rendered_cc_scale(matrix: Matrix3, kelvin: int) -> RenderedCCRecord:
    """Firmware-proven increasing first-fit rendered-CC scale search.

    Each candidate is rounded first using 0x40012940's finite nearest/ties-away
    rule, then tested against [-2048,+2047].  The first fitting scaleCode wins.
    """
    for scale_code in RENDERED_CC_SCALE_CODES:
        q = _rounded_cc_coeff(matrix, scale_code)
        if min(q) >= CC_MIN and max(q) <= CC_MAX:
            return RenderedCCRecord(q, scale_code, int(kelvin))
    raise OverflowError("matrix cannot be represented by recovered rendered-CC scaleCode 0..3")


def max_abs_matrix_error(a: Matrix3, b: Matrix3) -> float:
    return max(abs(a[r][c] - b[r][c]) for r in range(3) for c in range(3))


def _identity() -> Matrix3:
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def self_check() -> dict[str, object]:
    # Stored Bradford inverse is intentionally truncated; do not demand exact I.
    bradford_err = max_abs_matrix_error(mat_mul(BRADFORD, BRADFORD_INV), _identity())
    working_err = max_abs_matrix_error(mat_mul(PCS_TO_INTERNAL, INTERNAL_TO_PCS), _identity())
    irec = select_rendered_cc_scale(_identity(), 0)
    later = select_rendered_cc_scale(((6.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), 0)
    return {
        "bradford_identity_max_abs": bradford_err,
        "working_pair_identity_max_abs": working_err,
        "default_output": "sRGB",
        "neutral_to_xy_epsilon": NEUTRAL_TO_XY_EPSILON,
        "neutral_to_xy_max_passes": NEUTRAL_TO_XY_MAX_PASSES,
        "rendered_cc_rounding": "PROVEN nearest/ties-away from zero for finite coefficients",
        "rendered_cc_scale_search": "PROVEN increasing first-fit scaleCode 0..3 after rounding/range test",
        "rendered_cc_identity_scale": irec.scale_code,
        "rendered_cc_forced_later_scale": later.scale_code,
        "status": "proven-core-executable; exact xy->temperature/NeutralToXY driver and CC MAC remain separate",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_check(), indent=2, sort_keys=True))
