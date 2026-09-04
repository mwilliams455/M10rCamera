import unittest

from tools.m10r_meter_cadence import (
    BASE_TICK_MS,
    EVENT_FRESH_METER,
    EVENT_RECALCULATE,
    METER_EVENT_PERIOD_MS,
    NEGATIVE_BV_HOLD_MS,
    MeterCadenceState,
    event_requests_fresh_meter,
    event_requests_recalculation,
    first_detent_event_mask,
)


class MeterCadenceTests(unittest.TestCase):
    def test_recovered_constants(self):
        self.assertEqual(BASE_TICK_MS, 10)
        self.assertEqual(METER_EVENT_PERIOD_MS, 100)
        self.assertEqual(NEGATIVE_BV_HOLD_MS, 300)

    def test_stopped_timer_emits_no_meter_events(self):
        state = MeterCadenceState()
        self.assertEqual([state.timer_tick() for _ in range(20)], [0] * 20)

    def test_active_timer_posts_bit0_every_tenth_tick(self):
        state = MeterCadenceState()
        state.start()
        masks = [state.timer_tick() for _ in range(20)]
        self.assertEqual([i + 1 for i, m in enumerate(masks) if m], [10, 20])
        self.assertTrue(all(m == EVENT_FRESH_METER for m in masks if m))

    def test_first_detent_is_recalculate_only(self):
        mask = first_detent_event_mask()
        self.assertEqual(mask, EVENT_RECALCULATE)
        self.assertFalse(event_requests_fresh_meter(mask))
        self.assertTrue(event_requests_recalculation(mask))

    def test_negative_bv_arms_300ms_latch(self):
        state = MeterCadenceState(timer_active=True)
        self.assertTrue(state.arm_negative_bv_hold(-1))
        self.assertTrue(state.negative_bv_latch)
        self.assertEqual(state.negative_bv_remaining_ms, 300)
        self.assertFalse(state.traditional_refresh_allowed)

    def test_nonnegative_bv_does_not_arm_latch(self):
        state = MeterCadenceState()
        self.assertFalse(state.arm_negative_bv_hold(0))
        self.assertFalse(state.negative_bv_latch)

    def test_expiry_clears_latch_but_does_not_synthesize_meter_event(self):
        state = MeterCadenceState(timer_active=True)
        state.arm_negative_bv_hold(-1)
        state.elapse(299)
        self.assertTrue(state.negative_bv_latch)
        state.elapse(1)
        self.assertFalse(state.negative_bv_latch)
        self.assertTrue(state.traditional_refresh_allowed)
        # Expiry itself has no event-return surface; the next periodic bit0 tick
        # is what can cause a new traditional measurement.

    def test_next_periodic_refresh_is_within_100ms_after_expiry(self):
        state = MeterCadenceState(timer_active=True, tick_count=0)
        state.arm_negative_bv_hold(-1)
        state.elapse(300)
        seen = None
        for ticks in range(1, 11):
            if event_requests_fresh_meter(state.timer_tick()):
                seen = ticks * BASE_TICK_MS
                break
        self.assertEqual(seen, 100)


if __name__ == "__main__":
    unittest.main()
