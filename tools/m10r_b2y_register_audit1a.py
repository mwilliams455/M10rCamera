#!/usr/bin/env python3
"""Replay bounded M10-R *register programmers*, never emulate B2Y pixels.

Requires canonical extracted sections and unicorn. The only intercepted call
is the tone-table byte-copy helper; its arguments and source hashes are logged.
Synthetic descriptor probes establish packing masks, not legal hardware modes.
No shader, rounding, source-selector, or pipeline-order semantics are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import unicorn
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)
from m10r_b2y_assets import parse_records, occurrences

IMG_SHA = "53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4"
B2Y_SHA = "ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b"
CODE = 0x42000000
RAM = 0x10000000
DESC = RAM + 0x1000
TABLE0 = RAM + 0x2000
TABLE1 = RAM + 0xC000
RETURN = RAM + 0x1F000
MMIO = 0x20020000
MMIO_SIZE = 0x3000
TONE = 0x420D3C1C
COPY = 0x4204F2EC


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, expected):
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError(f"canonical section hash mismatch: {path.name}")
    return data


class Programmer:
    def __init__(self, img, table0, table1):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(CODE, (len(img) + 0xFFF) & ~0xFFF)
        self.uc.mem_write(CODE, img[4:])
        self.uc.mem_map(RAM, 0x20000)
        self.uc.mem_map(MMIO, MMIO_SIZE)
        self.uc.mem_map(0x20A00000, 0x20000)
        self.uc.mem_write(TABLE0, table0)
        self.uc.mem_write(TABLE1, table1)
        self.initial = self.uc.context_save()
        self.uc.hook_add(UC_HOOK_CODE, self.code)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=MMIO, end=MMIO + MMIO_SIZE - 1)

    def code(self, uc, address, size, unused):
        self.instructions += 1
        if address == COPY:
            dst, src, count = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if dst not in (0x20A00000, 0x20A0A000) or count != 0xA000:
                raise RuntimeError("unexpected byte-copy request")
            data = bytes(uc.mem_read(src, count))
            self.copies.append({"call_pc": hex(address), "destination": hex(dst), "bytes": count, "source_sha256": sha(data)})
            uc.mem_write(dst, data)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not self.allowed[0] <= address < self.allowed[1]:
            raise RuntimeError(f"execution escaped bounded programmer at {address:#x}")

    def write(self, uc, access, address, size, value, unused):
        self.writes.append({"pc": hex(uc.reg_read(UC_ARM_REG_PC)), "address": hex(address), "bytes": size, "value": hex(value)})

    def run(self, descriptor, start, end, *, thumb=False, seed=0, tone=False):
        uc = self.uc
        uc.context_restore(self.initial)
        uc.mem_write(MMIO, struct.pack("<I", seed) * (MMIO_SIZE // 4))
        # Simulate idle status only. Never claim other hardware status behavior.
        uc.mem_write(MMIO + 4, struct.pack("<I", seed & ~0x10))
        uc.mem_write(DESC, descriptor)
        uc.reg_write(UC_ARM_REG_SP, RAM + 0x1E000)
        uc.reg_write(UC_ARM_REG_LR, RETURN)
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3),
                              (DESC, TABLE0 if tone else 0, TABLE1 if tone else 0, 0)):
            uc.reg_write(reg, value)
        self.writes, self.copies, self.instructions = [], [], 0
        self.allowed = (start, end)
        uc.emu_start(start | int(thumb), RETURN, count=4000)
        if uc.reg_read(UC_ARM_REG_PC) != RETURN:
            raise RuntimeError("programmer failed to return within instruction budget")
        touched = sorted({int(w["address"], 16) + off for w in self.writes for off in range(0, w["bytes"], 4)})
        registers = {hex(a): f"0x{struct.unpack('<I', uc.mem_read(a, 4))[0]:08x}" for a in touched}
        return {"start": hex(start), "state": "Thumb" if thumb else "ARM", "seed": hex(seed),
                "instructions": self.instructions, "registers": registers,
                "writes": self.writes, "byte_copy_calls": self.copies}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sections", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    img = checked(args.sections / "092_IMG-System.bin", IMG_SHA)
    b2y = checked(args.sections / "074_IMG_Calibration_Data_data_calib_B2Y.bin.bin", B2Y_SHA)
    records = parse_records(b2y)

    def record(rid, n=0, size=None):
        r = occurrences(records, rid)[n]
        return b2y[r.payload_offset:r.payload_offset + (r.size if size is None else size)]

    tone = record(8)
    p = Programmer(img, record(0x19, 1, 0xA000), record(0x1A, 1, 0xA000))
    baseline = p.run(tone, TONE, 0x420D4298, tone=True)
    probes = []
    for offset in [0x1C, 0x20, 0x24, *range(0x78, 0x98, 4)]:
        for value in (0, 1, 0x4000, 0x8000, 0x10000, 0xFFFFFFFF):
            d = bytearray(tone)
            struct.pack_into("<I", d, offset, value)
            result = p.run(bytes(d), TONE, 0x420D4298, tone=True)
            delta = {a: v for a, v in result["registers"].items() if baseline["registers"][a] != v}
            probes.append({"descriptor_offset": hex(offset), "synthetic_value": hex(value), "changed_registers": delta})
    other = {}
    for name, rid, n, start, end in [
        ("shift_still", 3, 0, 0x420D35E0, 0x420D3636),
        ("shift_live", 3, 1, 0x420D35E0, 0x420D3636),
        ("dg_control", 0xB, 0, 0x420D15E8, 0x420D1644),
        ("yc_conversion", 0xC, 0, 0x420D456C, 0x420D47BC),
    ]:
        other[name] = p.run(record(rid, n), start, end, thumb=True)
    # Assert concrete observed writes, not inferred pixel semantics.
    assert baseline["registers"]["0x20020808"] == "0x0a650400"
    assert baseline["registers"]["0x2002080c"] == "0x0000019a"
    assert other["shift_still"]["registers"]["0x20020088"] == "0x00000102"
    assert other["shift_live"]["registers"]["0x20020088"] == "0x00000104"
    assert other["dg_control"]["registers"]["0x20020800"] == "0x03000000"
    assert [c["bytes"] for c in baseline["byte_copy_calls"]] == [0xA000, 0xA000]
    report = {
        "schema": "m10r.b2y.register_audit1a.v1", "unicorn_version": unicorn.__version__,
        "img_section_sha256": IMG_SHA, "b2y_section_sha256": B2Y_SHA,
        "scope": "CPU descriptor-to-MMIO replay; B2Y pixel hardware is NOT emulated",
        "interception": "0x4204f2ec byte-copy call: log request, copy source bytes, return via LR",
        "tone_descriptor_u32": [hex(x) for x in struct.unpack('<44I', tone)],
        "tone_baseline": baseline,
        "tone_all_ones_mmio_seed": p.run(tone, TONE, 0x420D4298, tone=True, seed=0xFFFFFFFF),
        "synthetic_packing_probes": probes,
        "other_programmers": other,
        "open": ["tone coefficient semantic names/channel order/denominator", "shift direction and bit8 meaning",
                 "tone/DG signal sources and physical order", "pixel clamp sequencing", "Q15 rounding", "DG output transfer semantics"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({"out": str(args.out), "packing_probes": len(probes), "tone_registers": baseline["registers"],
                      "other_registers": {k: v["registers"] for k, v in other.items()}}, indent=2))


if __name__ == "__main__":
    main()
