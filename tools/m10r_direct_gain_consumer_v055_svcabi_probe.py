#!/usr/bin/env python3
"""Characterize IMG-SAM7 SVC #7/#6 from structurally valid Thumb wrappers.

This is a behavioral ABI probe for the only remaining v0.55 caveat.  The
0x20020090-derived r2 value is merely live when the target helper enters and
executes SVC #7.  Rather than decode mixed SAM7 bytes as ARM handler code, this
probe asks whether real Thumb functions invoke SVC #7 immediately after their
prologue with r0-r3 *unprepared*, then save SVC7's r0 result and later restore
that token immediately before SVC #6.

If this pattern is common, SVC #7 cannot reasonably have a normal r2 argument
contract: it is entered with arbitrary enclosing-function argument state.  All
reported locations are IMG-SAM7 section offsets; the section has no proven
runtime base.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import re
from collections import Counter

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB

from m10r_direct_gain_consumer_v055 import load_sections

SECTION_INDEX = "100"
TARGET_HELPER_SVC7_OFF = 0x4D11A
MAX_PAIR_INSNS = 96
MAX_PROLOGUE_BACK = 5

SAVE_RE = re.compile(r"^(r(?:[4-9]|1[01])),\s*r0$")
RESTORE_RE_TEMPLATE = r"^r0,\s*{}$"


def compact(s: str) -> str:
    return s.replace(" ", "").lower()


def is_svc(ins, number: int) -> bool:
    if ins.mnemonic != "svc":
        return False
    return ins.op_str.strip().lower() in {f"#{number}", f"#0x{number:x}"}


def is_push_lr(ins) -> bool:
    return ins.mnemonic == "push" and "lr" in ins.op_str.lower()


def writes_reg_text(ins, reg: str) -> bool:
    """Conservative text-level destination test for ordinary Thumb forms."""
    if ins.mnemonic in {"cmp", "cmn", "tst", "teq", "str", "strb", "strh", "strd", "push", "svc", "b", "bl", "blx", "bx", "cbz", "cbnz"}:
        return False
    first = compact(ins.op_str).split(",", 1)[0]
    if first == reg:
        return True
    if first.startswith("{") and reg in first:
        return True
    return False


def reads_reg_text(ins, reg: str) -> bool:
    text = compact(ins.op_str)
    if reg not in text:
        return False
    # A plain destination-only MOV/MOVS clobber is not a read.
    if ins.mnemonic.startswith("mov") and text.startswith(reg + ",") and text.split(",", 1)[1] != reg:
        return False
    return True


def find_token_pair(insns, i: int):
    """Find svc7 -> save r0 -> restore r0 -> svc6 before function return."""
    saved = None
    save_i = None
    for j in range(i + 1, min(len(insns), i + 8)):
        ins = insns[j]
        if ins.mnemonic.startswith("mov"):
            m = SAVE_RE.match(ins.op_str.strip().lower())
            if m:
                saved, save_i = m.group(1), j
                break
        if ins.mnemonic == "pop" and "pc" in ins.op_str.lower():
            return None
    if saved is None:
        return None

    restore_i = None
    svc6_i = None
    restore_re = re.compile(RESTORE_RE_TEMPLATE.format(re.escape(saved)))
    for j in range(save_i + 1, min(len(insns), i + MAX_PAIR_INSNS)):
        ins = insns[j]
        if ins.mnemonic.startswith("mov") and restore_re.match(ins.op_str.strip().lower()):
            restore_i = j
            continue
        if restore_i is not None and is_svc(ins, 6):
            svc6_i = j
            break
        if ins.mnemonic == "pop" and "pc" in ins.op_str.lower():
            break
    if svc6_i is None:
        return None
    return saved, save_i, restore_i, svc6_i


def find_near_prologue(insns, i: int):
    for j in range(i - 1, max(-1, i - MAX_PROLOGUE_BACK - 1), -1):
        ins = insns[j]
        if is_push_lr(ins):
            return j
        if ins.mnemonic in {"pop", "bx"} or (ins.mnemonic.startswith("b") and ins.mnemonic not in {"bic", "bics"}):
            break
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    args = ap.parse_args()

    sec = next((s for s in load_sections(args.sections) if s.index == SECTION_INDEX), None)
    if sec is None:
        raise SystemExit("IMG-SAM7 section 100 not found")

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    md.skipdata = True
    insns = list(md.disasm(sec.data, sec.analysis_base))

    svc7_indices = [i for i, ins in enumerate(insns) if is_svc(ins, 7)]
    svc6_indices = [i for i, ins in enumerate(insns) if is_svc(ins, 6)]
    pairs = []
    prologue_pairs = []
    unprepared = Counter()
    first_post_r2 = Counter()
    examples = []
    target = None

    for i in svc7_indices:
        pair = find_token_pair(insns, i)
        if pair is None:
            continue
        saved, save_i, restore_i, svc6_i = pair
        pairs.append(i)
        p = find_near_prologue(insns, i)
        prologue = p is not None
        prep = {r: False for r in ("r0", "r1", "r2", "r3")}
        if prologue:
            prologue_pairs.append(i)
            for j in range(p + 1, i):
                for r in prep:
                    if writes_reg_text(insns[j], r):
                        prep[r] = True
            for r, was_prepared in prep.items():
                if not was_prepared:
                    unprepared[r] += 1

        first_r2_action = "NONE"
        first_r2_text = None
        for j in range(i + 1, min(len(insns), svc6_i + 1)):
            if "r2" not in compact(insns[j].op_str):
                continue
            if writes_reg_text(insns[j], "r2") and not reads_reg_text(insns[j], "r2"):
                first_r2_action = "CLOBBER"
            else:
                first_r2_action = "READ_OR_TRANSFORM"
            first_r2_text = f"{insns[j].mnemonic} {insns[j].op_str}"
            break
        first_post_r2[first_r2_action] += 1

        off = insns[i].address - sec.analysis_base
        record = {
            "offset": off,
            "saved": saved,
            "prologue": prologue,
            "prologue_offset": (insns[p].address - sec.analysis_base) if prologue else None,
            "prepared": prep,
            "first_r2_action": first_r2_action,
            "first_r2_text": first_r2_text,
            "svc6_offset": insns[svc6_i].address - sec.analysis_base,
        }
        if off == TARGET_HELPER_SVC7_OFF:
            target = record
        if prologue and len(examples) < 24:
            examples.append(record)

    print(f"SVCABI_SECTION={sec.label}")
    print(f"SVCABI_RUNTIME_BASE_KNOWN={int(sec.runtime_base is not None)}")
    print(f"SVCABI_THUMB_INSNS={len(insns)}")
    print(f"SVCABI_SVC7_COUNT={len(svc7_indices)}")
    print(f"SVCABI_SVC6_COUNT={len(svc6_indices)}")
    print(f"SVCABI_TOKEN_PAIR_COUNT={len(pairs)}")
    print(f"SVCABI_NEAR_PROLOGUE_PAIR_COUNT={len(prologue_pairs)}")
    for r in ("r0", "r1", "r2", "r3"):
        print(f"SVCABI_PROLOGUE_{r.upper()}_UNPREPARED={unprepared[r]}")
    for k in ("CLOBBER", "READ_OR_TRANSFORM", "NONE"):
        print(f"SVCABI_FIRST_POST_R2_{k}={first_post_r2[k]}")

    # A near-prologue SVC7 with no r2 preparation means the SVC sees the
    # enclosing function's arbitrary incoming r2. Multiple independent examples
    # are strong behavioral evidence against an r2-argument ABI.
    r2_unprepared_ratio = (unprepared["r2"] / len(prologue_pairs)) if prologue_pairs else 0.0
    print(f"SVCABI_PROLOGUE_R2_UNPREPARED_RATIO={r2_unprepared_ratio:.6f}")

    for n, rec in enumerate(examples):
        print(
            f"SVCABI_EXAMPLE[{n}]=svc7+0x{rec['offset']:x};"
            f"prologue+0x{rec['prologue_offset']:x};save={rec['saved']};"
            f"r0prep={int(rec['prepared']['r0'])};r1prep={int(rec['prepared']['r1'])};"
            f"r2prep={int(rec['prepared']['r2'])};r3prep={int(rec['prepared']['r3'])};"
            f"postr2={rec['first_r2_action']};svc6+0x{rec['svc6_offset']:x}"
        )

    if target is None:
        print("SVCABI_TARGET_HELPER=NOT_STRUCTURALLY_MATCHED")
    else:
        print("SVCABI_TARGET_HELPER=STRUCTURALLY_MATCHED")
        print(f"SVCABI_TARGET_HELPER_SVC7_OFFSET=0x{target['offset']:x}")
        print(f"SVCABI_TARGET_HELPER_NEAR_PROLOGUE={int(target['prologue'])}")
        print(f"SVCABI_TARGET_HELPER_R2_PREPARED={int(target['prepared']['r2'])}")
        print(f"SVCABI_TARGET_HELPER_FIRST_POST_R2={target['first_r2_action']}")
        print(f"SVCABI_TARGET_HELPER_FIRST_POST_R2_INSN={target['first_r2_text']}")

    if len(prologue_pairs) >= 8 and unprepared["r2"] >= 8 and r2_unprepared_ratio >= 0.75 and target is not None and not target["prepared"]["r2"]:
        print("SVCABI_R2_ARGUMENT_EVIDENCE=CONTRADICTED_BY_WRAPPER_ABI")
    else:
        print("SVCABI_R2_ARGUMENT_EVIDENCE=UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
