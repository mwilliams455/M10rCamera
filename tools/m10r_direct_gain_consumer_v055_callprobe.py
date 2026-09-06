#!/usr/bin/env python3
"""Bounded probe for the only unresolved v0.55 call-argument sink.

Besides listing the exact caller/callee, this pass characterizes IMG-SAM7's
SVC #7 / SVC #6 usage.  The target callee executes SVC #7 before clobbering
incoming r2, so the exception boundary must be modeled rather than silently
ignored.  A repeated save-r0 / restore-r0 pairing around SVC #7/#6 is reported
as firmware evidence for a token-style critical-section guard ABI.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import re

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB

from m10r_direct_gain_consumer_v055 import load_sections

SECTION_INDEX = "100"
CALLER_OFFSET = 0x4FB02
CALL_ANALYSIS_TARGET = 0x6286D118
CALLEE_BYTES = 0x280
CALLER_BEFORE = 0x30
CALLER_AFTER = 0x40
PAIR_LOOKAHEAD = 96

MOV_SAVE_RE = re.compile(r"^(r(?:[4-9]|1[01])),\s*r0$")


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


def characterize_svc_pairs(sec) -> None:
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    md.skipdata = True
    insns = list(md.disasm(sec.data, sec.analysis_base))
    svc7_idx = [i for i, ins in enumerate(insns) if ins.mnemonic == "svc" and ins.op_str.strip() in {"#7", "#0x7"}]
    svc6_idx = [i for i, ins in enumerate(insns) if ins.mnemonic == "svc" and ins.op_str.strip() in {"#6", "#0x6"}]

    pairs = []
    for idx in svc7_idx:
        saved = None
        save_i = None
        # The observed wrappers save SVC7's return token from r0 into a callee-saved register.
        for j in range(idx + 1, min(len(insns), idx + 8)):
            ins = insns[j]
            if ins.mnemonic.startswith("mov"):
                m = MOV_SAVE_RE.match(ins.op_str.replace(" ", ""))
                if m:
                    saved, save_i = m.group(1), j
                    break
            if ins.mnemonic in {"pop", "bx"}:
                break
        if saved is None:
            continue

        restore = None
        svc6 = None
        for j in range(save_i + 1, min(len(insns), idx + PAIR_LOOKAHEAD)):
            ins = insns[j]
            if ins.mnemonic.startswith("mov") and ins.op_str.replace(" ", "") == f"r0,{saved}":
                restore = j
                continue
            if restore is not None and ins.mnemonic == "svc" and ins.op_str.strip() in {"#6", "#0x6"}:
                svc6 = j
                break
            if ins.mnemonic == "pop" and "pc" in ins.op_str:
                break
        if restore is not None and svc6 is not None:
            pairs.append((idx, saved, restore, svc6))

    print("\n=== SVC ABI CHARACTERIZATION ===")
    print(f"SVC7_COUNT={len(svc7_idx)}")
    print(f"SVC6_COUNT={len(svc6_idx)}")
    print(f"SVC7_TOKEN_PAIR_COUNT={len(pairs)}")
    print(f"SVC7_TOKEN_PAIR_COVERAGE={len(pairs)}/{len(svc7_idx)}")
    for n, (idx, saved, restore, svc6) in enumerate(pairs[:64]):
        a = insns[idx].address - sec.analysis_base
        r = insns[restore].address - sec.analysis_base
        s = insns[svc6].address - sec.analysis_base
        print(f"SVC7_TOKEN_PAIR[{n}]=svc7+0x{a:x};save={saved};restore+0x{r:x};svc6+0x{s:x}")

    target_idx = next((i for i, ins in enumerate(insns) if ins.address == CALL_ANALYSIS_TARGET), None)
    if target_idx is not None:
        target_svc = next((i for i in range(target_idx, min(len(insns), target_idx + 8)) if insns[i].mnemonic == "svc"), None)
        first_r2 = None
        if target_svc is not None:
            for i in range(target_svc + 1, min(len(insns), target_svc + 16)):
                compact = insns[i].op_str.replace(" ", "")
                if compact.startswith("r2,") or ",r2" in compact or compact == "r2":
                    first_r2 = i
                    break
        print(f"TARGET_CALLEE_ENTRY_OFFSET=0x{CALL_ANALYSIS_TARGET - sec.analysis_base:x}")
        if target_svc is not None:
            print(f"TARGET_CALLEE_SVC={insns[target_svc].mnemonic} {insns[target_svc].op_str}")
        if first_r2 is not None:
            ins = insns[first_r2]
            off = ins.address - sec.analysis_base
            compact = ins.op_str.replace(" ", "")
            clobber = ins.mnemonic.startswith("mov") and compact.startswith("r2,")
            print(f"TARGET_CALLEE_FIRST_POST_SVC_R2_OFFSET=0x{off:x}")
            print(f"TARGET_CALLEE_FIRST_POST_SVC_R2_INSN={ins.mnemonic} {ins.op_str}")
            print(f"TARGET_CALLEE_FIRST_POST_SVC_R2_ACTION={'CLOBBER' if clobber else 'READ_OR_TRANSFORM'}")


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
    characterize_svc_pairs(sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
