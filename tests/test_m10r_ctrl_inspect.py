import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[1] / "tools" / "m10r_ctrl_inspect.py"
SPEC = importlib.util.spec_from_file_location("m10r_ctrl_inspect", MODULE_PATH)
assert SPEC and SPEC.loader
inspect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inspect
SPEC.loader.exec_module(inspect)


class AddressMappingTest(unittest.TestCase):
    def test_absolute_va_maps_after_prefix(self):
        self.assertEqual(4, inspect.va_offset(0x08000000))
        self.assertEqual(0x3A3BC, inspect.va_offset(0x0803A3B8))

    def test_rejects_unprefixed_vector_table(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.bin"
            path.write_bytes(struct.pack("<III", 0x20002208, 0x0804B03D, 0))
            with self.assertRaisesRegex(ValueError, "offset \\+4"):
                inspect.extract(path)


if __name__ == "__main__":
    unittest.main()
