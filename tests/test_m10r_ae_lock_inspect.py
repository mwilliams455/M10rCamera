from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from m10r_ae_lock_inspect import extract, img_data_offset, img_offset  # noqa: E402


CTRL = ROOT / "firmware" / "sections" / "090_CTRL-System.bin"
IMG = ROOT / "firmware" / "sections" / "092_IMG-System.bin"


class AddressMappingTest(unittest.TestCase):
    def test_img_prefix_mapping(self) -> None:
        self.assertEqual(img_offset(0x42000000), 4)
        self.assertEqual(img_offset(0x421C26FC), 0x1C2700)
        self.assertEqual(img_offset(0x421BD5D4), 0x1BD5D8)

    def test_img_initialized_data_mapping(self) -> None:
        self.assertEqual(img_data_offset(0x40000000), 4)
        self.assertEqual(img_data_offset(0x4096945C), 0x969460)


class LockContractTest(unittest.TestCase):
    def test_ambient_light_validity_bit_and_ae_lock_contract(self) -> None:
        result = extract(CTRL, IMG)

        calibration = result["ambient_light_calibration"]
        self.assertEqual(calibration["validity_flags_offset"], "0x79")
        self.assertEqual(calibration["ambient_light_valid_mask"], "0x01")
        self.assertIn("Ambient light not calibrated", calibration["missing_diagnostic"])

        lock = result["ae_lock"]
        self.assertEqual(
            lock["img_events"]["lock"], {"id": "0xae", "name": "EXT_AE_LOCK"}
        )
        self.assertEqual(
            lock["img_events"]["unlock"],
            {"id": "0xaf", "name": "EXT_AE_UNLOCK"},
        )
        self.assertEqual(lock["ipc"]["command_id"], "0x12")
        self.assertEqual(lock["ipc"]["packet_size"], 3)
        self.assertEqual(lock["ipc"]["lock_payload"], 1)
        self.assertEqual(lock["ipc"]["unlock_payload"], 0)
        self.assertEqual(lock["ctrl_lock_byte_va"], "0x2001ad6e")
        self.assertEqual(lock["cached_calculation_bv_va"], "0x2000012a")
        self.assertIn("reuses the prior cached Bv", lock["update_rule"])

    def test_release_detents_and_external_ae_actions_are_separate(self) -> None:
        lock = extract(CTRL, IMG)["ae_lock"]

        release = lock["physical_release"]
        self.assertEqual(release["record_index"], 13)
        self.assertEqual(
            release["raw_state_to_event"],
            {
                "1": {"id": "0xd6", "name": "K_Release_1"},
                "3": {"id": "0xd7", "name": "K_Release_2"},
                "2": {"id": "0xd5", "name": "K_Release_0"},
            },
        )
        self.assertIn(
            "independent external actions",
            lock["external_actions"]["classification"],
        )
        self.assertIn("do not post events", lock["negative_result"]["classification"])
