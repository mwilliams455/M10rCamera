#!/usr/bin/env python3
"""Candidate-seeded SVC/SWI handler search in IMG-SAM7.

IMG-SAM7+0 is startup ARM code, not an exception vector table.  This pass scans
ARM-aligned code for semantic signatures expected in an SVC handler, especially
loads from LR just before the trapped instruction, SPSR handling, and exception
returns.  It reports bounded windows only; it does not assume a handler merely
from one mnemonic.
"""
from __future__ import annotations

from pathlib import Path
import argparse
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM

from m10r_direct_gain_consumer_v055 import load_sections

SECTION_INDEX = "100"
WINDOW_BEFORE = 0x80
WINDOW_AFTER = 0x180


def op_text(ins) -> str:
    return f"{ins.mnemonic} {ins.op_str}".strip().lower()


def is_lr_trap_load(ins) -> bool:
    if ins.mnemonic not in {"ldrb", "ldrh", "ldr"}:
        return False
    try:
        for op in ins.operands:
            if op.type == ARM_OP_MEM and ins.reg_name(op.mem.base) == "lr":
                # Thumb SVC immediate sits at LR-2; ARM SWI immediate at LR-4.
                if int(op.mem.disp) in {-2, -4}:
                    return True
    except Exception:
        pass
    return False


def candidate_kind(ins) -> list[str]:
    text = op_text(ins)
    kinds = []
    if is_lr_trap_load(ins):
        kinds.append("LR_TRAP_LOAD")
    if ins.mnemonic == "mrs" and "spsr" in text:
        kinds.append("MRS_SPSR")
    if ins.mnemonic == "msr" and "spsr" in text:
        kinds.append("MSR_SPSR")
    if ins.mnemonic in {"subs", "movs"} and text.startswith(("subs pc", "movs pc")):
        kinds.append("EXCEPTION_RETURN")
    if ins.mnemonic in {"ldmia", "ldm", "pop"} and "pc" in text and "^" in text:
        kinds.append("EXCEPTION_RETURN")
    return kinds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    args = ap.parse_args()

    sections = load_sections(args.sections)
    sec = next((s for s in sections if s.index == SECTION_INDEX), None)
    if sec is None:
        raise SystemExit("IMG-SAM7 section 100 not found")

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    md.skipdata = True

    insns = list(md.disasm(sec.data, sec.analysis_base))
    by_addr = {ins.address: i for i, ins in enumerate(insns)}
    candidates = defaultdict(set)
    for ins in insns:
        kinds = candidate_kind(ins)
        if kinds:
            off = ins.address - sec.analysis_base
            for k in kinds:
                candidates[off].add(k)

    print(f"SVCHANDLER_SECTION={sec.label}")
    print(f"SVCHANDLER_RUNTIME_BASE_KNOWN={int(sec.runtime_base is not None)}")
    print(f"SVCHANDLER_ARM_INSNS={len(insns)}")
    for kind in ("LR_TRAP_LOAD", "MRS_SPSR", "MSR_SPSR", "EXCEPTION_RETURN"):
        print(f"SVCHANDLER_{kind}_COUNT={sum(kind in ks for ks in candidates.values())}")

    # Cluster candidates into bounded windows and rank by semantic diversity.
    offsets = sorted(candidates)
    clusters = []
    for off in offsets:
        lo = max(0, off - WINDOW_BEFORE)
        hi = min(len(sec.data), off + WINDOW_AFTER)
        merged = False
        for c in clusters:
            if lo <= c[1] and hi >= c[0]:
                c[0] = min(c[0], lo)
                c[1] = max(c[1], hi)
                c[2].add(off)
                merged = True
                break
        if not merged:
            clusters.append([lo, hi, {off}])
    # transitive merge
    changed = True
    while changed:
        changed = False
        out = []
        for c in sorted(clusters):
            if out and c[0] <= out[-1][1]:
                out[-1][1] = max(out[-1][1], c[1])
                out[-1][2].update(c[2])
                changed = True
            else:
                out.append(c)
        clusters = out

    ranked = []
    for lo, hi, seeds in clusters:
        kinds = set()
        for s in seeds:
            kinds.update(candidates[s])
        score = 10 * int("LR_TRAP_LOAD" in kinds) + 4 * int("MRS_SPSR" in kinds) + 3 * int("MSR_SPSR" in kinds) + 2 * int("EXCEPTION_RETURN" in kinds) + len(kinds)
        ranked.append((score, lo, hi, seeds, kinds))
    ranked.sort(reverse=True)

    print(f"SVCHANDLER_CLUSTER_COUNT={len(ranked)}")
    for rank, (score, lo, hi, seeds, kinds) in enumerate(ranked[:24]):
        print(f"SVCHANDLER_CLUSTER[{rank}]=score={score};start=0x{lo:x};end=0x{hi:x};kinds={','.join(sorted(kinds))};seeds={','.join(hex(x) for x in sorted(seeds))}")
        for ins in md.disasm(sec.data[lo:hi], sec.analysis_base + lo):
            off = ins.address - sec.analysis_base
            marker = "*" if off in seeds else " "
            print(f"SVCHANDLER_WINDOW[{rank}] {marker}+0x{off:06x} {bytes(ins.bytes).hex():<10} {ins.mnemonic:<8} {ins.op_str}")

    # Hard summary: a high-confidence handler candidate needs direct trap-load
    # plus exception-state/return evidence in the same bounded cluster.
    strong = [r for r in ranked if "LR_TRAP_LOAD" in r[4] and ("MRS_SPSR" in r[4] or "MSR_SPSR" in r[4]) and "EXCEPTION_RETURN" in r[4]]
    print(f"SVCHANDLER_STRONG_CANDIDATES={len(strong)}")
    if strong:
        print(f"SVCHANDLER_BEST_START=0x{strong[0][1]:x}")
        print(f"SVCHANDLER_BEST_END=0x{strong[0][2]:x}")
        print("SVCHANDLER_VERDICT=CANDIDATE_FOUND")
    else:
        print("SVCHANDLER_VERDICT=UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
