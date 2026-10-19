#!/usr/bin/env python3
"""Extract firmware-proven M10-R B2Y tone and differential-gamma assets.

Input is the extracted IMG calibration section:
  074_IMG_Calibration_Data_data_calib_B2Y.bin.bin

The parser/layout and active upload sizes are taken from the frozen M10-R
firmware research on branch m10r-color-science-trace.

This tool deliberately does NOT guess unresolved hardware details. It emits:
  * tone_low_q15.u32le       (10,240 uint32 Q15 gains)
  * tone_medium_q15.u32le    (10,240 uint32 Q15 gains; default still branch)
  * tone_high_q15.u32le      (10,240 uint32 Q15 gains)
  * dg_main_u8.bin           (2,048 x 16 byte differential groups)
  * dg_fl_u16le.bin          (2,048 uint16 coarse anchors)
  * dg_expanded_u16le.bin    (32,768 uint16 exact table-coordinate curve)
  * manifest.json

Frozen functional models referenced by the manifest:
  default still contrast enum 2 -> MEDIUM
  tone first-parity index = x >> 1, Q15 unity = 0x8000
  DG coordinate: coarse=x>>4, fine=x&15,
                 y=FL[coarse]+sum(DG[coarse][1..fine])

The exact live B2Y signal normalization and integer rounding around tone remain
separate open questions; this extractor does not encode guesses for them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SECTION_PREFIX = 4
RECORD_HEADER_OFF = SECTION_PREFIX + 0x10
RECORD_STRIDE = 0xA90

ID_TONE_TBL0 = 0x19
ID_DG_MAIN = 0x1C
ID_DG_FL = 0x1D

TONE_ACTIVE_BYTES = 0xA000
TONE_ENTRIES = TONE_ACTIVE_BYTES // 4
DG_MAIN_ACTIVE_BYTES = 0x8000
DG_GROUPS = 2048
DG_GROUP_SIZE = 16
DG_FL_ACTIVE_BYTES = 0x1000
DG_FL_ENTRIES = DG_FL_ACTIVE_BYTES // 2
DG_EXPANDED_ENTRIES = DG_GROUPS * DG_GROUP_SIZE


@dataclass(frozen=True)
class Record:
    index: int
    record_id: int
    rel_offset: int
    size: int
    payload_offset: int


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_records(data: bytes) -> list[Record]:
    if len(data) < RECORD_HEADER_OFF:
        raise ValueError("B2Y section is too small")
    count = u32(data, SECTION_PREFIX + 8)
    payload_base = RECORD_HEADER_OFF + count * RECORD_STRIDE
    if payload_base > len(data):
        raise ValueError(
            f"record table overruns section: count={count}, payload_base={payload_base:#x}, size={len(data):#x}"
        )

    out: list[Record] = []
    for i in range(count):
        off = RECORD_HEADER_OFF + i * RECORD_STRIDE
        rid = u32(data, off)
        rel = u32(data, off + 4)
        size = u32(data, off + 8)
        payload = payload_base + rel
        if payload < payload_base or payload + size > len(data):
            raise ValueError(
                f"record {i} id={rid:#x} payload out of bounds: off={payload:#x} size={size:#x}"
            )
        out.append(Record(i, rid, rel, size, payload))
    return out


def occurrences(records: Iterable[Record], rid: int) -> list[Record]:
    return [r for r in records if r.record_id == rid]


def active_blob(data: bytes, rec: Record, size: int, label: str) -> bytes:
    if rec.size < size:
        raise ValueError(
            f"{label} record {rec.index} too small: record={rec.size:#x}, required active={size:#x}"
        )
    return data[rec.payload_offset : rec.payload_offset + size]


def unpack_u32(blob: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(blob)//4}I", blob))


def unpack_u16(blob: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(blob)//2}H", blob))


def expand_differential_gamma(main: bytes, fl_blob: bytes) -> list[int]:
    if len(main) != DG_MAIN_ACTIVE_BYTES:
        raise ValueError(f"DG main must be {DG_MAIN_ACTIVE_BYTES:#x} bytes")
    if len(fl_blob) != DG_FL_ACTIVE_BYTES:
        raise ValueError(f"DG FL must be {DG_FL_ACTIVE_BYTES:#x} bytes")

    anchors = unpack_u16(fl_blob)
    if len(anchors) != DG_FL_ENTRIES:
        raise AssertionError("unexpected anchor count")

    expanded: list[int] = []
    for coarse in range(DG_GROUPS):
        group = main[coarse * DG_GROUP_SIZE : (coarse + 1) * DG_GROUP_SIZE]
        if group[0] != 0:
            raise ValueError(
                f"DG group {coarse} byte0={group[0]} but frozen encoding requires byte0=0"
            )
        value = anchors[coarse]
        expanded.append(value)
        for fine in range(1, DG_GROUP_SIZE):
            value += group[fine]
            if value > 0xFFFF:
                raise ValueError(f"DG reconstruction overflow at coarse={coarse}, fine={fine}")
            expanded.append(value)

    if len(expanded) != DG_EXPANDED_ENTRIES:
        raise AssertionError("unexpected expanded DG count")
    if any(a > b for a, b in zip(expanded, expanded[1:])):
        raise ValueError("expanded DG curve is not monotonic")

    # Frozen v1.88 relationship: next anchor is the current interval's 16th
    # implicit step. The 15 stored fine increments may only use floor/ceil
    # increments; the boundary residual completes the interval.
    for i in range(DG_GROUPS - 1):
        delta = anchors[i + 1] - anchors[i]
        if delta < 0:
            raise ValueError(f"FL anchors decrease at interval {i}")
        group = main[i * DG_GROUP_SIZE : (i + 1) * DG_GROUP_SIZE]
        stored = sum(group[1:])
        residual = anchors[i + 1] - (anchors[i] + stored)
        q, rem = divmod(delta, 16)
        allowed = {q, q + (1 if rem else 0)}
        if residual not in allowed:
            raise ValueError(
                f"DG interval {i} violates frozen quotient/remainder encoding: delta={delta}, residual={residual}"
            )
        if any(step not in allowed for step in group[1:]):
            raise ValueError(
                f"DG interval {i} has stored increment outside floor/ceil set {sorted(allowed)}"
            )

    return expanded


def pack_u16(values: Iterable[int]) -> bytes:
    vals = list(values)
    return struct.pack(f"<{len(vals)}H", *vals)


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("b2y_section", type=Path, help="extracted data_calib_B2Y.bin section")
    ap.add_argument("out_dir", type=Path, help="output directory")
    args = ap.parse_args()

    data = args.b2y_section.read_bytes()
    records = parse_records(data)

    tone = occurrences(records, ID_TONE_TBL0)
    if len(tone) < 3:
        raise ValueError(f"expected >=3 ID 0x19 tone occurrences, found {len(tone)}")
    dg_main_records = occurrences(records, ID_DG_MAIN)
    dg_fl_records = occurrences(records, ID_DG_FL)
    if len(dg_main_records) != 1:
        raise ValueError(f"expected exactly one ID 0x1C record, found {len(dg_main_records)}")
    if len(dg_fl_records) != 1:
        raise ValueError(f"expected exactly one ID 0x1D record, found {len(dg_fl_records)}")

    tone_blobs = {
        "low": active_blob(data, tone[0], TONE_ACTIVE_BYTES, "tone LOW"),
        "medium": active_blob(data, tone[1], TONE_ACTIVE_BYTES, "tone MEDIUM"),
        "high": active_blob(data, tone[2], TONE_ACTIVE_BYTES, "tone HIGH"),
    }
    dg_main = active_blob(data, dg_main_records[0], DG_MAIN_ACTIVE_BYTES, "DG main")
    dg_fl = active_blob(data, dg_fl_records[0], DG_FL_ACTIVE_BYTES, "DG FL")
    expanded = expand_differential_gamma(dg_main, dg_fl)
    expanded_blob = pack_u16(expanded)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    for name, blob in tone_blobs.items():
        write(out / f"tone_{name}_q15.u32le", blob)
    write(out / "dg_main_u8.bin", dg_main)
    write(out / "dg_fl_u16le.bin", dg_fl)
    write(out / "dg_expanded_u16le.bin", expanded_blob)

    tone_values = {name: unpack_u32(blob) for name, blob in tone_blobs.items()}
    manifest = {
        "format": "m10r-b2y-assets-v1",
        "source_sha256": sha256(data),
        "record_count": len(records),
        "default_still_contrast": {
            "enum": 2,
            "name": "MEDIUM",
            "suffix": "_CONTRAST:MEDIUM",
            "firmware_status": "frozen",
        },
        "tone": {
            "encoding": "uint32 little-endian Q15 gain",
            "unity": 0x8000,
            "active_entries": TONE_ENTRIES,
            "first_parity_index": "x >> 1",
            "exact_live_rounding": "open",
            "tables": {
                name: {
                    "file": f"tone_{name}_q15.u32le",
                    "sha256": sha256(blob),
                    "min": min(tone_values[name]),
                    "max": max(tone_values[name]),
                    "unique": len(set(tone_values[name])),
                }
                for name, blob in tone_blobs.items()
            },
        },
        "differential_gamma": {
            "encoding": "2048 uint16 anchors + 2048x16 uint8 differential groups",
            "coordinate_formula": "coarse=x>>4; fine=x&15; y=FL[coarse]+sum(DG[coarse][1..fine])",
            "main_file": "dg_main_u8.bin",
            "main_sha256": sha256(dg_main),
            "fl_file": "dg_fl_u16le.bin",
            "fl_sha256": sha256(dg_fl),
            "expanded_file": "dg_expanded_u16le.bin",
            "expanded_sha256": sha256(expanded_blob),
            "expanded_entries": len(expanded),
            "expanded_min": min(expanded),
            "expanded_max": max(expanded),
            "expanded_monotonic": True,
        },
        "frozen_references": [
            "research/M10R_v189_DIFFERENTIAL_GAMMA_ENCODING_FROZEN.md",
            "research/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md",
            "research/M10R_v198_CONTRAST_ENUM_TONE_SELECTION_FROZEN.md",
            "research/M10R_v206_DEFAULT_STILL_CONTRAST_MEDIUM_FROZEN.md",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
