#!/usr/bin/env python3
"""Verify M10-R CTRL-System load mapping and extract exposure tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


IMAGE_BASE = 0x08000000
PAYLOAD_PREFIX = 4
TABLE_SIZE = 52


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def va_offset(address: int) -> int:
    return PAYLOAD_PREFIX + address - IMAGE_BASE


def extract(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < PAYLOAD_PREFIX + 8:
        raise ValueError("CTRL-System payload is too small")

    initial_sp = u32(data, PAYLOAD_PREFIX)
    reset_vector = u32(data, PAYLOAD_PREFIX + 4)
    if not 0x20000000 <= initial_sp < 0x30000000:
        raise ValueError("expected vector table at file offset +4")
    if not (reset_vector & 1) or not IMAGE_BASE <= (reset_vector & ~1) < 0x09000000:
        raise ValueError("reset vector is not a Thumb address in the CTRL image")

    iso_va = 0x0803A3B8
    sv_va = 0x0803B8CC
    correction_va = 0x0803B65C
    iso = struct.unpack_from(f"<{TABLE_SIZE}I", data, va_offset(iso_va))
    sv = struct.unpack_from(f"<{TABLE_SIZE}h", data, va_offset(sv_va))
    corrections = struct.unpack_from(
        f"<{TABLE_SIZE}h", data, va_offset(correction_va)
    )

    rows = [
        {
            "index": index,
            "iso": state_iso,
            "sv_q8": state_sv,
            "sv_ev": state_sv / 256.0,
            "correction_q8": correction,
            "correction_ev": correction / 256.0,
        }
        for index, (state_iso, state_sv, correction) in enumerate(
            zip(iso, sv, corrections)
        )
    ]
    return {
        "file": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "payload_prefix_bytes": PAYLOAD_PREFIX,
        "image_base": f"0x{IMAGE_BASE:08x}",
        "initial_sp": f"0x{initial_sp:08x}",
        "reset_vector": f"0x{reset_vector:08x}",
        "tables": {
            "iso_va": f"0x{iso_va:08x}",
            "sv_va": f"0x{sv_va:08x}",
            "correction_va": f"0x{correction_va:08x}",
            "engineering_state_count": TABLE_SIZE,
            "production_slice": {"first_index": 15, "count": 29},
            "rows": rows,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctrl_system", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.ctrl_system), indent=2))


if __name__ == "__main__":
    main()
