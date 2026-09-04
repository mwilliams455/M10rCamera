#!/usr/bin/env python3
"""Executable state model for the recovered M10-R traditional-meter cadence.

Research milestone v0.12.

The production CTRL path uses a 10 ms re-armed timer callback. Every tenth
callback posts event bit 0 to the AE event consumer, giving the normal
traditional-meter refresh request a 100 ms (10 Hz) cadence while that timer is
active.  First-detent AE lock posts event bit 1 only and therefore does not
force a fresh traditional-meter sample.

A separate low-light transition rule arms a 300 ms negative-Bv latch. While the
latch is set, the normal non-live-view final-Bv selector holds the previous
final Bv and skips the traditional selector-5 measurement. Timer expiry clears
the latch; the next ordinary bit-0 event can then sample again.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_TICK_MS = 10
METER_EVENT_PERIOD_MS = 100
NEGATIVE_BV_HOLD_MS = 300

EVENT_FRESH_METER = 0x01
EVENT_RECALCULATE = 0x02


@dataclass
class MeterCadenceState:
    """Minimal production-state model for cadence and the negative-Bv gate."""

    timer_active: bool = False
    tick_count: int = 0
    negative_bv_latch: bool = False
    negative_bv_remaining_ms: int = 0

    def start(self) -> None:
        """Enter the control state that enables the 10 ms periodic timer."""
        self.timer_active = True

    def stop(self) -> None:
        """Leave the control state that owns the 10 ms periodic timer."""
        self.timer_active = False

    def timer_tick(self) -> int:
        """Run one recovered 10 ms periodic callback and return AE event bits.

        The firmware increments its counter once per callback and posts event
        bit 0 when (tick_count * 10) modulo 100 is zero.  Other housekeeping
        cadences in the same callback are deliberately outside this model.
        """
        if not self.timer_active:
            return 0
        self.tick_count += 1
        return EVENT_FRESH_METER if (self.tick_count * BASE_TICK_MS) % METER_EVENT_PERIOD_MS == 0 else 0

    def arm_negative_bv_hold(self, traditional_bv_q8: int) -> bool:
        """Model 0x0800E16C: arm a 300 ms hold only for negative traditional Bv."""
        if int(traditional_bv_q8) < 0:
            self.negative_bv_latch = True
            self.negative_bv_remaining_ms = NEGATIVE_BV_HOLD_MS
            return True
        return False

    def elapse(self, milliseconds: int) -> None:
        """Advance only the one-shot negative-Bv timer.

        The real timer is non-blocking and its callback clears the latch.  This
        helper intentionally does not synthesize a fresh-meter event on expiry;
        firmware does not do that either.
        """
        if milliseconds < 0:
            raise ValueError("milliseconds must be non-negative")
        if not self.negative_bv_latch:
            return
        self.negative_bv_remaining_ms = max(0, self.negative_bv_remaining_ms - milliseconds)
        if self.negative_bv_remaining_ms == 0:
            self.negative_bv_latch = False

    @property
    def traditional_refresh_allowed(self) -> bool:
        """Normal non-LV selector may perform selector-5 sampling when clear."""
        return not self.negative_bv_latch


def first_detent_event_mask() -> int:
    """AE-lock receiver's downstream event mask: recalculate only, no sample."""
    return EVENT_RECALCULATE


def event_requests_fresh_meter(mask: int) -> bool:
    return bool(int(mask) & EVENT_FRESH_METER)


def event_requests_recalculation(mask: int) -> bool:
    return bool(int(mask) & EVENT_RECALCULATE)
