import unittest

from tools.m10r_aperture_estimator import (
    CANONICAL_FNUMBER_Q8,
    apply_raw_deadband,
    av_q8_to_fnumber_q8,
    estimate_aperture,
    fnumber_q8_to_x1000,
    quantize_half_stop_down,
    raw_aperture_candidate_q8,
    threshold_remap_q8,
)


class ApertureEstimatorTests(unittest.TestCase):
    def test_normal_candidate_is_external_minus_ttl_plus_av0(self):
        self.assertEqual(
            raw_aperture_candidate_q8(
                bv_ext_q8=0x0800,
                ttl_bv_q8=0x0600,
                av0_q8=0x0500,
            ),
            0x0700,
        )

    def test_negative_candidate_clamps_to_zero(self):
        self.assertEqual(
            raw_aperture_candidate_q8(
                bv_ext_q8=0,
                ttl_bv_q8=0x0800,
                av0_q8=0x0500,
            ),
            0,
        )

    def test_override_forces_av4(self):
        self.assertEqual(
            raw_aperture_candidate_q8(
                bv_ext_q8=0,
                ttl_bv_q8=0,
                av0_q8=0,
                force_reference=True,
            ),
            0x0400,
        )

    def test_deadband_edges_are_retained(self):
        prior = 0x0500
        self.assertEqual(apply_raw_deadband(prior + 0x41, prior), (prior, False))
        self.assertEqual(apply_raw_deadband(prior - 0x41, prior), (prior, False))
        self.assertEqual(apply_raw_deadband(prior + 0x42, prior), (prior + 0x42, True))
        self.assertEqual(apply_raw_deadband(prior - 0x42, prior), (prior - 0x42, True))

    def test_quantization_floors_to_half_stop(self):
        self.assertEqual(quantize_half_stop_down(0x05FF), 0x0580)
        self.assertEqual(quantize_half_stop_down(0x0600), 0x0600)

    def test_canonical_av5_is_f56(self):
        # Av=5.0 is half-stop index 10 and maps to the firmware's canonical 5.6.
        self.assertEqual(av_q8_to_fnumber_q8(0x0500), CANONICAL_FNUMBER_Q8[10])
        self.assertEqual(fnumber_q8_to_x1000(CANONICAL_FNUMBER_Q8[10]), 5600)

    def test_canonical_half_stop_series(self):
        expected_x1000 = (
            1000, 1200, 1400, 1700, 2000,
            2400, 2800, 3400, 4000, 4800,
            5600, 6800, 8000, 9500, 11000,
            13000, 16000, 19000, 22000, 27000,
            32000, 38000, 45000, 54000, 64000,
        )
        self.assertEqual(
            tuple(fnumber_q8_to_x1000(v) for v in CANONICAL_FNUMBER_Q8),
            expected_x1000,
        )

    def test_threshold_remap_returns_half_stop_index(self):
        thresholds = [i * 0x80 for i in range(22)]
        self.assertEqual(threshold_remap_q8(0x0300, thresholds), 0x0300)
        self.assertEqual(threshold_remap_q8(0x0320, thresholds), 0x0380)

    def test_end_to_end_no_remap(self):
        # BvExt 8 - TTL Bv 8 + AV0 5 -> Av5 -> f/5.6.
        result = estimate_aperture(
            bv_ext_q8=0x0800,
            ttl_bv_q8=0x0800,
            av0_q8=0x0500,
            prior_raw_q8=0,
        )
        self.assertEqual(result.av_q8, 0x0500)
        self.assertEqual(result.fnumber_x1000, 5600)
        self.assertTrue(result.deadband_updated)

    def test_default_upper_bound_is_av12(self):
        result = estimate_aperture(
            bv_ext_q8=0x3000,
            ttl_bv_q8=0,
            av0_q8=0x0500,
            prior_raw_q8=0,
        )
        self.assertEqual(result.av_q8, 0x0C00)
        self.assertTrue(result.upper_bound_hit)
        self.assertEqual(result.fnumber_x1000, 64000)


if __name__ == "__main__":
    unittest.main()
