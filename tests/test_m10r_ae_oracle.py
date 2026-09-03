import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "tools" / "m10r_ae_oracle.py"
SPEC = importlib.util.spec_from_file_location("m10r_ae_oracle", MODULE_PATH)
assert SPEC and SPEC.loader
oracle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)


class TablesTest(unittest.TestCase):
    def test_engineering_tables_align(self):
        self.assertEqual(52, len(oracle.ISO_STATES))
        self.assertEqual(52, len(oracle.SV_STATES_Q8))
        self.assertEqual(52, len(oracle.SV_CORRECTIONS_Q8))
        self.assertEqual(0x0500, oracle.iso_to_sv_q8(100))
        self.assertEqual(0x05AE, oracle.iso_to_sv_q8(160))
        self.assertEqual(0x0E00, oracle.iso_to_sv_q8(50000))

    def test_production_slice_is_29_states(self):
        self.assertEqual(29, len(oracle.PRODUCTION_ISO_STATES))
        self.assertEqual(100, oracle.PRODUCTION_ISO_STATES[0])
        self.assertEqual(64000, oracle.PRODUCTION_ISO_STATES[-1])

    def test_corrected_calibration_alignment(self):
        self.assertEqual(27, oracle.sv_correction_q8(0x0500))
        self.assertEqual(37, oracle.sv_correction_q8(0x0555))
        self.assertEqual(39, oracle.sv_correction_q8(0x0E00))


class StepHelperTest(unittest.TestCase):
    def test_production_third_stop_cycle(self):
        self.assertEqual(0x0555, oracle.round_q8_to_step(0x0555, 0x55))
        self.assertEqual(0x05AA, oracle.round_q8_to_step(0x05AE, 0x55))
        self.assertEqual(0x0600, oracle.round_q8_to_step(0x05FF, 0x55))


class AModeTest(unittest.TestCase):
    def test_bright_scene_does_not_activate_auto_iso(self):
        result = oracle.solve_a_mode(
            bv_q8=oracle.ev_to_q8(6),
            av_q8=oracle.ev_to_q8(4),
            tv_iso_q8=oracle.ev_to_q8(6),
        )
        self.assertFalse(result.auto_iso_activated)
        self.assertEqual(100, result.iso)
        self.assertEqual(0x06E5, result.tv_q8)
        self.assertEqual("tv_iso_already_satisfied", result.constraint_reason)

    def test_dark_scene_advances_sv_in_production_steps(self):
        result = oracle.solve_a_mode(
            bv_q8=oracle.ev_to_q8(0),
            av_q8=oracle.ev_to_q8(4),
            tv_iso_q8=oracle.ev_to_q8(6),
        )
        self.assertTrue(result.auto_iso_activated)
        self.assertEqual(16, result.auto_iso_steps)
        self.assertEqual(0x0A55, result.sv_q8)
        self.assertEqual(4000, result.iso)
        self.assertEqual(0x0635, result.tv_q8)
        self.assertTrue(result.tv_iso_reached)

    def test_sv_max_can_prevent_tv_iso_boundary(self):
        result = oracle.solve_a_mode(
            bv_q8=oracle.ev_to_q8(-5),
            av_q8=oracle.ev_to_q8(4),
            tv_iso_q8=oracle.ev_to_q8(6),
            sv_max_q8=oracle.iso_to_sv_q8(50000),
        )
        self.assertEqual(27, result.auto_iso_steps)
        self.assertEqual(50000, result.iso)
        self.assertTrue(result.sv_upper_bound_hit)
        self.assertEqual("sv_max_before_tv_iso", result.constraint_reason)


if __name__ == "__main__":
    unittest.main()
