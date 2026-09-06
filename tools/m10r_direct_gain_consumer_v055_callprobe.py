#!/usr/bin/env python3
"""Bounded disassembly probe for the only unresolved v0.55 call-argument sink.

The strict v0.55 trace proves that MEM[0x20020090] is read at IMG-SAM7
+0x4fb02, bitfield-modified, stored back to the same address, and is still in
r2 when the caller executes BL to analysis address 0x6286d118.  This probe
recovers the callee entry from the same synthetic section mapping and prints a
small, exact-offset Thumb listing so the r2 parameter can be modeled next.
"""
from __future__ import annotations

from pathlib import Path
import argparse

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB

from m10r_direct_gain_consumer_v055 import load_sections

SECTION_INDEX = "100"
CALLER_OFFSET = 0x4FB02
CALL_ANALYSIS_TARGET = 0x6286D118
CALLEE_BYTES = 0x280
CALLER_BEFORE = 0x30
CALLER_AFTER = 0x40


def print_listing(md: Cs, sec, start_off: int, size: int, tag: str) -> None:
    start_off = max(0, start_off & ~1)
    end_off = min(len(sec.data), start_off + size)
    print(f"{tag}_SECTION={sec.label}")
    print(f"{tag}_START_OFFSET=0x{start_off:x}")
    print(f"{tag}_END_OFFSET=0x{end_off:x}")
    print(f"{tag}_ANALYSIS_START=0x{sec.analysis_base + start_off:08x}")
    count = 0
    for ins in md.disasm(sec.data[start_off:end_off], sec.analysis_base + start_off):
        off = ins.address - sec.analysis_base
        raw = bytes(ins.bytes).hex()
        print(f"{tag} +0x{off:06x} 0x{ins.address:08x} {raw:<10} {ins.mnemonic:<8} {ins.op_str}")
        count += 1
    print(f"{tag}_INSNS={count}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    args = ap.parse_args()

    sections = load_sections(args.sections)
    sec = next((s for s in sections if s.index == SECTION_INDEX), None)
    if sec is None:
        raise SystemExit("IMG-SAM7 section 100 not found")

    callee_off = CALL_ANALYSIS_TARGET - sec.analysis_base
    print(f"CALLPROBE_SECTION_ANALYSIS_BASE=0x{sec.analysis_base:08x}")
    print(f"CALLPROBE_CALLER_OFFSET=0x{CALLER_OFFSET:x}")
    print(f"CALLPROBE_CALL_TARGET_ANALYSIS=0x{CALL_ANALYSIS_TARGET:08x}")
    print(f"CALLPROBE_CALLEE_OFFSET=0x{callee_off:x}")
    if callee_off < 0 or callee_off >= len(sec.data):
        raise SystemExit("call target does not resolve inside IMG-SAM7")

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True

    print("\n=== CALLER CONTEXT ===")
    print_listing(md, sec, CALLER_OFFSET - CALLER_BEFORE, CALLER_BEFORE + CALLER_AFTER, "CALLER")
    print("\n=== CALLEE ENTRY ===")
    print_listing(md, sec, callee_off, CALLEE_BYTES, "CALLEE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
