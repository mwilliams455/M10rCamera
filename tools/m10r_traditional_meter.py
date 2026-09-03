#!/usr/bin/env python3
"""Executable model of the recovered M10-R traditional/rangefinder meter.

The firmware-defined coordinate is Q8.8 EV. Raw ADC calibration anchors are
body-specific and therefore supplied as parameters rather than hard-coded.

Recovered production path:
  * ADC selector 4 -> ADC input 5 -> Tlog coordinate
  * ADC selector 5 -> ADC input 6 -> ten-sample average
  * three piecewise-linear regions anchored at -2/0/+3/+10 EV
  * signed normal-mode offset
  * Tlog-dependent low-light status hysteresis

See research/M10R_EXPOSURE_ENGINE_v0_10_TRADITIONAL_METER_ADC_AND_CALIBRATION.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

Q8 = 256


@dataclass(frozen=True)
class MeterCalibration:
    """Known fields from the 0x1C-byte runtime meter calibration record."""

    c0_neg2ev: int
    c1_0ev: int
    c2_pos3ev: int
    c3_pos10ev: int
    alternate_offset_q8: int = 0
    normal_offset_q8: int = 0
    tlog_reference_adc: int = 0

    @property
    def anchors(self) -> tuple[int, int, int, int]:
        return (
            self.c0_neg2ev,
            self.c1_0ev,
            self.c2_pos3ev,
            self.c3_pos10ev,
        )


@dataclass(frozen=True)
class TraditionalMeterResult:
    tlog: int
    adc_average: int
    mapped_bv_q8: int
    traditional_bv_q8: int
    status: int


def _trunc_div(numer: int, denom: int) -> int:
    """ARM SDIV-compatible signed integer division: truncate toward zero."""
    if denom == 0:
        raise ZeroDivisionError("meter calibration denominator is zero")
    sign = -1 if (numer < 0) ^ (denom < 0) else 1
    return sign * (abs(numer) // abs(denom))


def _int16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def adc_to_bv_q8(adc: int, calibration: MeterCalibration) -> int:
    """Model firmware routine 0x0802D320.

    Degenerate-anchor fallbacks intentionally match the recovered code rather
    than rejecting such records, although a valid production calibration is
    expected to have distinct ordered anchors.
    """
    c0, c1, c2, c3 = calibration.anchors
    adc = int(adc)

    if adc < c1:
        denominator = c1 - c0
        if denominator == 0:
            mapped = (adc - c1) * 0x0200
        else:
            mapped = _trunc_div((adc - c1) * 0x0200, denominator)
    elif adc < c2:
        denominator = c2 - c1
        if denominator == 0:
            mapped = (adc - c1) * 0x0300
        else:
            mapped = _trunc_div((adc - c1) * 0x0300, denominator)
    else:
        denominator = c3 - c2
        if denominator == 0:
            mapped = (adc - c2) * 0x0700 + 0x0300
        else:
            mapped = _trunc_div((adc - c2) * 0x0700, denominator) + 0x0300

    return _int16(mapped)


def tlog_from_adc(adc5: int, reference_adc: int) -> int:
    """Model firmware routine 0x0802D678.

    The recovered floating-point expression is:
        ((reference_adc - adc5) * 100 / 142.74) + 200.0
    followed by signed integer conversion and clamp [-400, 800].

    The physical interpretation of Tlog as temperature x10 C is a strong
    static inference, not a recovered symbol name.
    """
    value = ((int(reference_adc) - int(adc5)) * 100.0 / 142.74) + 200.0
    tlog = math.trunc(value)
    return max(-400, min(800, tlog))


def low_light_threshold_q8(tlog: int) -> int:
    """Recovered Tlog-dependent lower validity threshold."""
    if tlog < -80:
        return -128
    if tlog < 20:
        return -256
    if tlog < 280:
        return -512
    if tlog < 350:
        return -128
    return 0


def update_meter_status(tlog: int, traditional_bv_q8: int, prior_status: int) -> int:
    """Model firmware routine 0x0802D3D0.

    Status sets below the lower threshold, clears only above threshold+128,
    and is retained inside that 0.5-EV hysteresis band.
    """
    threshold = low_light_threshold_q8(int(tlog))
    bv = _int16(int(traditional_bv_q8))
    if bv < threshold:
        return 1
    if bv > threshold + 128:
        return 0
    return 1 if prior_status else 0


def average_adc_samples(samples: Sequence[int] | Iterable[int]) -> int:
    values = [int(x) & 0xFFFF for x in samples]
    if len(values) != 10:
        raise ValueError("production traditional meter requires exactly 10 ADC samples")
    return sum(values) // 10


def measure_traditional(
    adc5_tlog: int,
    adc6_samples: Sequence[int] | Iterable[int],
    calibration: MeterCalibration,
    prior_status: int = 0,
) -> TraditionalMeterResult:
    """Run the recovered normal-mode selector-5 traditional meter model."""
    tlog = tlog_from_adc(adc5_tlog, calibration.tlog_reference_adc)
    adc_average = average_adc_samples(adc6_samples)
    mapped = adc_to_bv_q8(adc_average, calibration)
    traditional = _int16(mapped + int(calibration.normal_offset_q8))
    status = update_meter_status(tlog, traditional, prior_status)
    return TraditionalMeterResult(
        tlog=tlog,
        adc_average=adc_average,
        mapped_bv_q8=mapped,
        traditional_bv_q8=traditional,
        status=status,
    )
