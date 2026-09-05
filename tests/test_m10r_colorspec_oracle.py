import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).parents[1] / "tools" / "m10r_colorspec_oracle.py"
SPEC = importlib.util.spec_from_file_location("m10r_colorspec_oracle", MODULE_PATH)
assert SPEC and SPEC.loader
oracle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)


class AsShotNeutralTest(unittest.TestCase):
    SAMPLES = (
        ((0.2853957637, 1.0, 0.6564102564), (897, 256, 390)),
        ((0.2969837587, 1.0, 0.6289926290), (862, 256, 407)),
        ((0.2853957637, 1.0, 0.6530612245), (897, 256, 392)),
        ((0.2892655367, 1.0, 0.6213592233), (885, 256, 412)),
        ((0.2853957637, 1.0, 0.6614987080), (897, 256, 387)),
        ((0.2813186813, 1.0, 0.6614987080), (910, 256, 387)),
    )

    def test_six_verified_dng_samples_recover_exact_integer_gains(self):
        for neutral, gains in self.SAMPLES:
            self.assertEqual(gains, oracle.recover_ca9_gains(neutral))

    def test_round_trip_error_matches_empirical_boundary(self):
        maximum = 0.0
        for neutral, gains in self.SAMPLES:
            rebuilt = oracle.gains_to_firmware_neutral(gains)
            maximum = max(maximum, *(abs(a - b) for a, b in zip(neutral, rebuilt)))
        self.assertLess(maximum, 4.4e-11)

    def test_gain_clamp(self):
        self.assertEqual((2000, 256, 1), oracle.recover_ca9_gains((0.001, 1.0, 1000.0)))


class MatrixTest(unittest.TestCase):
    def assertMatrixAlmostEqual(self, a, b, places=10):
        for r in range(3):
            for c in range(3):
                self.assertAlmostEqual(a[r][c], b[r][c], places=places)

    def test_dng_fixed_matrix_expansion(self):
        m = oracle.matrix_from_fixed_rationals(
            (1024, 0, 0, 0, 512, 0, 0, 0, -256), 1024
        )
        self.assertEqual(((1.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, -0.25)), m)

    def test_matrix_inverse(self):
        m = ((2.0, 1.0, 0.0), (0.0, 3.0, 1.0), (1.0, 0.0, 4.0))
        inv = oracle.mat_inv(m)
        got = oracle.mat_mul(m, inv)
        self.assertMatrixAlmostEqual(got, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))

    def test_xyz_xy_roundtrip(self):
        xy = (0.3457, 0.3585)
        self.assertMatrixPointAlmostEqual(xy, oracle.xyz_to_xy(oracle.xy_to_xyz(xy)))

    def assertMatrixPointAlmostEqual(self, a, b, places=12):
        self.assertAlmostEqual(a[0], b[0], places=places)
        self.assertAlmostEqual(a[1], b[1], places=places)

    def test_bradford_identity_white_is_near_identity(self):
        got = oracle.map_white_matrix(oracle.D50_XY, oracle.D50_XY)
        identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        # Firmware inverse is stored at deliberately truncated precision.
        self.assertLess(oracle.max_abs_matrix_error(got, identity), 1.0e-6)


class InterpolationTest(unittest.TestCase):
    M1 = ((1.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 3.0))
    M2 = ((3.0, 0.0, 0.0), (0.0, 4.0, 0.0), (0.0, 0.0, 5.0))

    def test_boundary_selection(self):
        self.assertEqual(self.M1, oracle.interpolate_matrix(3000.0, 6000.0, self.M1, self.M2, 2500.0))
        self.assertEqual(self.M2, oracle.interpolate_matrix(3000.0, 6000.0, self.M1, self.M2, 6500.0))

    def test_reciprocal_temperature_midpoint(self):
        # Reciprocal midpoint of 3000 and 6000 is 4000 K, so g = 0.5.
        got = oracle.interpolate_matrix(3000.0, 6000.0, self.M1, self.M2, 4000.0)
        expected = ((2.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0))
        for r in range(3):
            for c in range(3):
                self.assertAlmostEqual(expected[r][c], got[r][c], places=14)


class WorkingSpaceTest(unittest.TestCase):
    def test_default_cc1_is_firmware_srgb_branch(self):
        self.assertEqual(oracle.DEFAULT_SRGB_CC1, oracle.default_cc1())
        self.assertEqual((1.3895, -0.1693, -0.2202), oracle.default_cc1()[0])

    def test_cc0_formula_order(self):
        identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        got = oracle.ca9_cc0_from_set_white(identity, (1.0, 1.0, 1.0))
        self.assertEqual(oracle.PCS_TO_INTERNAL, got)


class QuantizerTest(unittest.TestCase):
    def test_half_away_from_zero(self):
        self.assertEqual(2, oracle.round_half_away_from_zero(1.5))
        self.assertEqual(-2, oracle.round_half_away_from_zero(-1.5))
        self.assertEqual(1, oracle.round_half_away_from_zero(1.49))
        self.assertEqual(-1, oracle.round_half_away_from_zero(-1.49))

    def test_quantizer_denominator_and_clamp(self):
        m = ((1.0, -1.0, 10.0), (0.5, -0.5, 0.0), (0.25, -0.25, 2.0))
        rec = oracle.quantize_rendered_cc(m, scale_code=0, kelvin=5000)
        self.assertEqual(512, rec.denominator)
        self.assertEqual(512, rec.coeff[0])
        self.assertEqual(-512, rec.coeff[1])
        self.assertEqual(2047, rec.coeff[2])
        self.assertEqual(5000, rec.kelvin)

    def test_decode_is_quantized_matrix(self):
        m = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        rec = oracle.quantize_rendered_cc(m, scale_code=0, kelvin=5500)
        self.assertEqual(m, rec.decoded_matrix())


class StatusTest(unittest.TestCase):
    def test_self_check_reports_frozen_boundary(self):
        status = oracle.self_check()
        self.assertEqual("sRGB", status["default_output"])
        self.assertEqual(15, status["neutral_to_xy_max_passes"])
        self.assertLess(status["bradford_identity_max_abs"], 1.0e-6)


if __name__ == "__main__":
    unittest.main()
