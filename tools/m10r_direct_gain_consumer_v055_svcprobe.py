#!/usr/bin/env python3
"""Trace IMG-SAM7 exception vectors and the SVC/SWI handler for v0.55.

Goal: close the only remaining caveat in the direct-gain investigation.  The
0x20020090-derived value is live in r2 when a caller enters IMG-SAM7+0x4d118,
but the callee's first ordinary post-SVC use of r2 is an unconditional clobber.
This probe follows the firmware's exception-vector evidence instead of assuming
what SVC #7 does.

Unknown IMG-SAM7 runtime base is preserved: all locations are section offsets or
synthetic analysis addresses, never claimed as genuine firmware VAs.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import struct
from typing import Optional

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

from m10r_direct_gain_consumer_v055 import load_sections

SECTION_INDEX = "100"
VECTOR_BYTES = 0x100
HANDLER_BYTES = 0x900
MAX_VECTOR_TARGETS = 16


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def dump_words(sec, start: int, size: int, tag: str) -> None:
    end = min(len(sec.data), start + size)
    for off in range(start, end - 3, 4):
        print(f"{tag}_WORD +0x{off:06x}=0x{u32(sec.data, off):08x}")


def arm_listing(sec, start: int, size: int, tag: str) -> list:
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    end = min(len(sec.data), start + size)
    insns = list(md.disasm(sec.data[start:end], sec.analysis_base + start))
    for ins in insns:
        off = ins.address - sec.analysis_base
        print(f"{tag} +0x{off:06x} 0x{ins.address:08x} {bytes(ins.bytes).hex():<10} {ins.mnemonic:<8} {ins.op_str}")
    print(f"{tag}_INSNS={len(insns)}")
    return insns


def thumb_listing(sec, start: int, size: int, tag: str) -> list:
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    end = min(len(sec.data), start + size)
    insns = list(md.disasm(sec.data[start:end], sec.analysis_base + start))
    for ins in insns:
        off = ins.address - sec.analysis_base
        print(f"{tag} +0x{off:06x} 0x{ins.address:08x} {bytes(ins.bytes).hex():<10} {ins.mnemonic:<8} {ins.op_str}")
    print(f"{tag}_INSNS={len(insns)}")
    return insns


def resolve_vector_target(sec, ins) -> Optional[int]:
    """Resolve common ARM vector forms: B/BL imm and LDR pc,[pc,#disp]."""
    try:
        ops = list(ins.operands)
    except Exception:
        return None
    mn = ins.mnemonic.lower()
    if mn in {"b", "bl"} and ops and ops[0].type == ARM_OP_IMM:
        return int(ops[0].imm)
    if mn == "ldr" and len(ops) >= 2:
        dst, src = ops[0], ops[1]
        if getattr(dst, "reg", 0) and ins.reg_name(dst.reg) == "pc" and src.type == ARM_OP_MEM:
            mem = src.mem
            if mem.base == ARM_REG_PC or ins.reg_name(mem.base) == "pc":
                # ARM state PC reads current instruction address + 8.
                lit_addr = ins.address + 8 + int(mem.disp)
                lit_off = lit_addr - sec.analysis_base
                if 0 <= lit_off <= len(sec.data) - 4:
                    return u32(sec.data, lit_off)
    return None


def scan_swi_service_dispatch(sec, start_off: int, size: int, tag: str) -> None:
    """Look for handler instructions that recover SWI immediate or inspect r0-r3.

    This is intentionally descriptive rather than speculative: it reports
    register mentions, SPSR/CPSR access, LR adjustment, and memory loads around
    a bounded handler candidate.
    """
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    end = min(len(sec.data), start_off + size)
    insns = list(md.disasm(sec.data[start_off:end], sec.analysis_base + start_off))
    r2_mentions = []
    svc_decode_hints = []
    control_hints = []
    for ins in insns:
        text = f"{ins.mnemonic} {ins.op_str}".strip().lower()
        off = ins.address - sec.analysis_base
        if "r2" in text:
            r2_mentions.append((off, text))
        if "lr" in text and ("ldr" in ins.mnemonic or "sub" in ins.mnemonic or "add" in ins.mnemonic):
            svc_decode_hints.append((off, text))
        if any(x in text for x in ("spsr", "cpsr", "msr", "mrs")):
            control_hints.append((off, text))
    print(f"{tag}_R2_MENTIONS={len(r2_mentions)}")
    for off, text in r2_mentions[:80]:
        print(f"{tag}_R2 +0x{off:x} {text}")
    print(f"{tag}_LR_DECODE_HINTS={len(svc_decode_hints)}")
    for off, text in svc_decode_hints[:80]:
        print(f"{tag}_LR +0x{off:x} {text}")
    print(f"{tag}_PSR_HINTS={len(control_hints)}")
    for off, text in control_hints[:80]:
        print(f"{tag}_PSR +0x{off:x} {text}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    args = ap.parse_args()

    sections = load_sections(args.sections)
    sec = next((s for s in sections if s.index == SECTION_INDEX), None)
    if sec is None:
        raise SystemExit("IMG-SAM7 section 100 not found")

    print(f"SVCPROBE_SECTION={sec.label}")
    print(f"SVCPROBE_RUNTIME_BASE_KNOWN={int(sec.runtime_base is not None)}")
    print(f"SVCPROBE_ANALYSIS_BASE=0x{sec.analysis_base:08x}")
    print(f"SVCPROBE_SIZE=0x{len(sec.data):x}")

    print("\n=== FIRST WORDS ===")
    dump_words(sec, 0, VECTOR_BYTES, "VECTOR")
    print("\n=== ARM VECTOR DISASSEMBLY ===")
    vectors = arm_listing(sec, 0, VECTOR_BYTES, "VECTOR_ARM")

    candidates = []
    # ARM7 exception vectors are at offsets 0x00..0x1c; SWI/SVC is +0x08.
    for ins in vectors:
        off = ins.address - sec.analysis_base
        if off > 0x1c:
            break
        target = resolve_vector_target(sec, ins)
        if target is not None:
            target_off = target - sec.analysis_base
            print(f"VECTOR_TARGET +0x{off:02x}=0x{target:08x};offset=0x{target_off:x}")
            if 0 <= target_off < len(sec.data):
                candidates.append((off, target_off))

    swi = next(((voff, toff) for voff, toff in candidates if voff == 0x08), None)
    if swi is None:
        print("SWI_VECTOR_RESOLUTION=UNRESOLVED")
        # Search the first 0x400 bytes in ARM and Thumb as a coverage aid.
        print("\n=== THUMB START FALLBACK ===")
        thumb_listing(sec, 0, 0x400, "START_THUMB")
        return 0

    vector_off, handler_off = swi
    print(f"SWI_VECTOR_RESOLUTION=RESOLVED")
    print(f"SWI_VECTOR_OFFSET=0x{vector_off:x}")
    print(f"SWI_HANDLER_OFFSET=0x{handler_off:x}")
    print("\n=== SWI HANDLER ARM LISTING ===")
    arm_listing(sec, handler_off, HANDLER_BYTES, "SWI_ARM")
    scan_swi_service_dispatch(sec, handler_off, HANDLER_BYTES, "SWI_SCAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
