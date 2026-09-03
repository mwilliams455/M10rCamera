import unittest

from tools.m10r_traditional_meter import (
    MeterCalibration,
    adc_to_bv_q8,
    average_adc_samples,
    low_light_threshold_q8,
    measure_traditional,
    tlog_from_adc,
    update_meter_status,
)


class TraditionalMeterTests(unittest.TestCase):
    def setUp(self):
        # Synthetic ordered ADC anchors chosen only to verify the recovered
        # coordinate mapping. Actual M10-R values are per-body calibration.
        self.cal = MeterCalibration(
            c0_neg2ev=1000,
            c1_0ev=2000,
            c2_pos3ev=3000,
            c3_pos10ev=4000,
            normal_offset_q8=0,
            tlog_reference_adc=5000,
        )

    def test_anchor_coordinates_are_exact(self):
        self.assertEqual(adc_to_bv_q8(1000, self.cal), -512)
        self.assertEqual(adc_to_bv_q8(2000, self.cal), 0)
        self.assertEqual(adc_to_bv_q8(3000, self.cal), 768)
        self.assertEqual(adc_to_bv_q8(4000, self.cal), 2560)

    def test_piecewise_midpoints(self):
        self.assertEqual(adc_to_bv_q8(1500, self.cal), -256)
        self.assertEqual(adc_to_bv_q8(2500, self.cal), 384)
        self.assertEqual(adc_to_bv_q8(3500, self.cal), 1664)

    def test_outer_segments_extrapolate(self):
        self.assertLess(adc_to_bv_q8(500, self.cal), -512)
        self.assertGreater(adc_to_bv_q8(4500, self.cal), 2560)

    def test_tlog_reference_is_200_and_clamps(self):
        self.assertEqual(tlog_from_adc(5000, 5000), 200)
        self.assertEqual(tlog_from_adc(100000, 5000), -400)
        self.assertEqual(tlog_from_adc(-100000, 5000), 800)

    def test_temperature_band_thresholds(self):
        self.assertEqual(low_light_threshold_q8(-81), -128)
        self.assertEqual(low_light_threshold_q8(-80), -256)
        self.assertEqual(low_light_threshold_q8(19), -256)
        self.assertEqual(low_light_threshold_q8(20), -512)
        self.assertEqual(low_light_threshold_q8(279), -512)
        self.assertEqual(low_light_threshold_q8(280), -128)
        self.assertEqual(low_light_threshold_q8(349), -128)
        self.assertEqual(low_light_threshold_q8(350), 0)

    def test_status_hysteresis(self):
        # Tlog=200 => threshold=-512, clear threshold=-384.
        self.assertEqual(update_meter_status(200, -513, 0), 1)
        self.assertEqual(update_meter_status(200, -500, 1), 1)
        self.assertEqual(update_meter_status(200, -384, 1), 1)
        self.assertEqual(update_meter_status(200, -383, 1), 0)

    def test_production_average_requires_ten_samples(self):
        self.assertEqual(average_adc_samples([1000] * 10), 1000)
        with self.assertRaises(ValueError):
            average_adc_samples([1000] * 9)

    def test_normal_offset_is_applied_after_mapping(self):
        cal = MeterCalibration(
            c0_neg2ev=1000,
            c1_0ev=2000,
            c2_pos3ev=3000,
            c3_pos10ev=4000,
            normal_offset_q8=64,
            tlog_reference_adc=5000,
        )
        result = measure_traditional(5000, [2000] * 10, cal)
        self.assertEqual(result.tlog, 200)
        self.assertEqual(result.mapped_bv_q8, 0)
        self.assertEqual(result.traditional_bv_q8, 64)


if __name__ == "__main__":
    unittest.main()
