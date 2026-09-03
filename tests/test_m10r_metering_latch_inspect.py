from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from m10r_metering_latch_inspect import extract, thumb_bl_target  # noqa: E402


CTRL = ROOT / "firmware" / "sections" / "090_CTRL-System.bin"
IMG = ROOT / "firmware" / "sections" / "092_IMG-System.bin"


class ThumbBlDecodeTest(unittest.TestCase):
    def test_known_receiver_bl(self) -> None:
        encoded = bytes.fromhex("0bf0bafc")
        self.assertEqual(thumb_bl_target(encoded, 0, 0x080024A0), 0x0800DE18)


class MeteringLatchOrderingTest(unittest.TestCase):
    def test_lock_command_is_committed_before_exposure_update_event(self) -> None:
        result = extract(CTRL, IMG)["ctrl_lock_to_calculator"]
        calls = result["ordered_calls"]
        self.assertEqual(calls[0]["target"], "0x0800de18")
        self.assertIn("commit AE-lock", calls[0]["meaning"])
        self.assertEqual(calls[1]["target"], "0x0800dc4a")
        self.assertEqual(result["event_post"]["mask"], "0x02")
        self.assertEqual(result["event_post"]["per_task_event_sender"], "0x0801cf26")

    def test_event_two_drives_builder_then_calculator(self) -> None:
        result = extract(CTRL, IMG)["ctrl_lock_to_calculator"]
        self.assertEqual(result["event_consumer"]["bit"], 1)
        self.assertEqual(result["event_consumer"]["builder"], "0x0800d91c")
        self.assertEqual(result["builder"]["lock_snapshot_va"], "0x0800da62")
        self.assertEqual(result["builder"]["calculator_call_va"], "0x0800db78")
        self.assertEqual(result["builder"]["calculator"], "0x080203b4")

    def test_lock_triggered_pass_cannot_refresh_cached_bv(self) -> None:
        boundary = extract(CTRL, IMG)["latch_boundary"]
        self.assertFalse(boundary["lock_triggered_pass_can_refresh_cached_bv"])
        self.assertIn("AE_lock=1", boundary["reason"])
        self.assertIn("previously-started unlocked", boundary["remaining_race"])
        self.assertIn("provisional", boundary["oracle_status"])

    def test_bstm_child_first_and_exposure_start_ordering(self) -> None:
        ordering = extract(CTRL, IMG)["img_ordering"]
        self.assertIn("before the current state's transitions", ordering["bstm"]["classification"])
        ext = ordering["external_exposure_start"]
        self.assertEqual(ext["event"], {"id": "0xd6", "name": "K_Release_1"})
        self.assertEqual(ext["first_call"], "0x421bc9e8")
        self.assertEqual(ext["second_call"], "0x421bf23c")
        self.assertIn("before", ext["classification"])


if __name__ == "__main__":
    unittest.main()
