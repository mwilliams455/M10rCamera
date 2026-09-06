#!/usr/bin/env python3
"""M10-R v0.63 semantic/dataflow probe for B2Y MMIO page 0x20020780.

This probe follows v0.62. It does not treat 0x3fff as a pixel limit by
numerology. Instead it enumerates code owners that materialize addresses on
the 0x200207xx MMIO page, reconstructs exact effective addresses through a
small Thumb register-value tracker, and inventories all observed reads/writes
of the three live v0.62 target words:

    0x2002078c (+0x0c)
    0x20020790 (+0x10)
    0x20020794 (+0x14)

For each access it emits owner, operation, instruction context, direct string
references, direct callees, and conservative source-expression provenance for
writes. The probe is intentionally evidence-producing rather than semantic-by-
constant: its automatic verdict remains unresolved until field meaning is
established from names/dataflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import sys
from typing import Dict, List, Optional, Tuple, Union

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import derive_mapping, get_img_section, read_cstr_va, u32

MMIO_BASE = 0x20020780
TARGETS = (MMIO_BASE + 0x0C, MMIO_BASE + 0x10, MMIO_BASE + 0x14)
TARGET_SET = set(TARGETS)
PAGE_LO = 0x20020700
PAGE_HI = 0x20020800
CENTRAL_OWNER = 0x42154F84
WB_SETTER = 0x420D4380
OWNER_BACK = 0x900
FUNC_MAX = 0x1400
POOL_SCAN_RADIUS = 0x1400
Value = Union[int, str]
DATA: bytes = b""
BIAS: int = 0


@dataclass
class Access:
    owner: int
    owner_end: int
    ins_index: int
    ins_addr: int
    kind: str
    width: str
    address: int
    source: str


def litrefs(ins, data: bytes, bias: int) -> List[Tuple[int, int]]:
    out = []
    try:
        ops = list(ins.operands)
    except Exception:
        return out
    for op in ops:
        if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
            p = ((ins.address + 4) & ~3) + int(op.mem.disp)
            v = u32(data, p - bias)
            if v is not None:
                out.append((p, v))
    return out


def branch_target(ins) -> Optional[int]:
    if ins.mnemonic.lower() not in ("bl", "blx", "b", "b.w"):
        return None
    try:
        for op in ins.operands:
            if op.type == ARM_OP_IMM:
                return int(op.imm) & 0xFFFFFFFF
    except Exception:
        pass
    return None


def adr_target(ins) -> Optional[int]:
    if ins.mnemonic.lower() != "adr":
        return None
    try:
        ops = list(ins.operands)
        if len(ops) >= 2 and ops[1].type == ARM_OP_IMM:
            v = int(ops[1].imm) & 0xFFFFFFFF
            if v >= 0x10000000:
                return v
    except Exception:
        pass
    parts = ins.op_str.split("#")
    if len(parts) != 2:
        return None
    try:
        imm = int(parts[1], 0)
    except ValueError:
        return None
    return ((ins.address + 4) & ~3) + imm


def reg_name(ins, op) -> Optional[str]:
    if op.type != ARM_OP_REG:
        return None
    try:
        return ins.reg_name(op.reg)
    except Exception:
        return None


def nearest_push(md, data: bytes, bias: int, xref: int, back: int = OWNER_BACK) -> Optional[int]:
    lo = max(bias, xref - back)
    if lo & 1:
        lo += 1
    found = []
    for va in range(lo, xref, 2):
        off = va - bias
        ins = next(md.disasm(data[off:off + 4], va, count=1), None)
        if ins and ins.mnemonic.lower() == "push" and "lr" in ins.op_str.lower():
            found.append(va)
    return found[-1] if found else None


def decode_function(md, data: bytes, bias: int, start: int, maxlen: int = FUNC_MAX):
    off = start - bias
    if off < 0 or off >= len(data):
        return [], start
    seq = []
    for ins in md.disasm(data[off:min(len(data), off + maxlen)], start):
        seq.append(ins)
        m = ins.mnemonic.lower()
        op = ins.op_str.lower()
        if (m == "pop" and "pc" in op) or (m == "bx" and op.strip() == "lr"):
            return seq, ins.address + ins.size
    return seq, (seq[-1].address + seq[-1].size if seq else start)


def find_page_literal_pools(data: bytes, bias: int) -> List[Tuple[int, int]]:
    out = []
    for off in range(0, len(data) - 3, 4):
        v = struct.unpack_from("<I", data, off)[0]
        if PAGE_LO <= v < PAGE_HI:
            out.append((bias + off, v))
    return out


def xrefs_to_pool(md, data: bytes, bias: int, pool_va: int) -> List[int]:
    out = []
    lo = max(bias, pool_va - POOL_SCAN_RADIUS)
    hi = min(bias + len(data) - 4, pool_va + POOL_SCAN_RADIUS)
    if lo & 1:
        lo += 1
    for va in range(lo, hi + 1, 2):
        off = va - bias
        ins = next(md.disasm(data[off:off + 4], va, count=1), None)
        if not ins:
            continue
        if any(p == pool_va for p, _ in litrefs(ins, data, bias)):
            out.append(va)
    return out


def fmt_value(v: Optional[Value]) -> str:
    if v is None:
        return "UNKNOWN"
    if isinstance(v, int):
        return f"0x{v & 0xffffffff:08x}"
    return v


def const_bin(op: str, a: Value, b: Value) -> Value:
    if isinstance(a, int) and isinstance(b, int):
        if op == "+": return (a + b) & 0xFFFFFFFF
        if op == "-": return (a - b) & 0xFFFFFFFF
        if op == "&": return a & b
        if op == "|": return a | b
    return f"({fmt_value(a)}{op}{fmt_value(b)})"


def const_shift(op: str, a: Value, n: int) -> Value:
    if isinstance(a, int):
        if op == "<<": return (a << n) & 0xFFFFFFFF
        return (a & 0xFFFFFFFF) >> n
    return f"({fmt_value(a)}{op}{n})"


def mem_width(mnemonic: str) -> str:
    m = mnemonic.lower()
    if m.endswith("b"): return "8"
    if m.endswith("h"): return "16"
    return "32"


def eff_addr(ins, memop, regs: Dict[str, Value]) -> Optional[int]:
    try:
        base = ins.reg_name(memop.mem.base) if memop.mem.base else None
        idx = ins.reg_name(memop.mem.index) if memop.mem.index else None
    except Exception:
        return None
    if not base or base == "pc":
        return None
    bv = regs.get(base)
    if not isinstance(bv, int):
        return None
    out = bv + int(memop.mem.disp)
    if idx:
        iv = regs.get(idx)
        if not isinstance(iv, int):
            return None
        out += iv
    return out & 0xFFFFFFFF


def set_unknown_written_regs(ins, regs: Dict[str, Value]) -> None:
    try:
        _, wr = ins.regs_access()
        for rid in wr:
            rn = ins.reg_name(rid)
            if rn and rn not in ("sp", "pc"):
                regs[rn] = f"DEF@0x{ins.address:08x}"
    except Exception:
        pass


def trace_function(seq, owner: int, owner_end: int):
    regs: Dict[str, Value] = {f"r{i}": f"ARG{i}" for i in range(13)}
    accesses: List[Access] = []
    calls = []
    direct_strings = []
    page_literals = []

    for idx, ins in enumerate(seq):
        m = ins.mnemonic.lower()
        try:
            ops = list(ins.operands)
        except Exception:
            ops = []

        bt = branch_target(ins)
        if m in ("bl", "blx") and bt is not None:
            calls.append((ins.address, bt))
            for rn in ("r0", "r1", "r2", "r3", "r12"):
                regs[rn] = f"CALLCLOBBER@0x{ins.address:08x}"
            continue

        lrs = litrefs(ins, DATA, BIAS)
        if lrs:
            for _, v in lrs:
                if PAGE_LO <= v < PAGE_HI:
                    page_literals.append((ins.address, v))
                s = read_cstr_va(DATA, BIAS, v) if BIAS <= v < BIAS + len(DATA) else None
                if s:
                    direct_strings.append((ins.address, s))
            if m.startswith("ldr") and ops and ops[0].type == ARM_OP_REG:
                dst = reg_name(ins, ops[0])
                if dst:
                    regs[dst] = lrs[0][1]
            continue

        at = adr_target(ins)
        if at is not None:
            s = read_cstr_va(DATA, BIAS, at)
            if s:
                direct_strings.append((ins.address, s))

        if (m.startswith("ldr") or m.startswith("str")) and len(ops) >= 2 and ops[1].type == ARM_OP_MEM:
            ea = eff_addr(ins, ops[1], regs)
            if ea is not None and PAGE_LO <= ea < PAGE_HI:
                kind = "READ" if m.startswith("ldr") else "WRITE"
                src = "-"
                if kind == "WRITE" and ops[0].type == ARM_OP_REG:
                    src_reg = reg_name(ins, ops[0])
                    src = f"{src_reg}:{fmt_value(regs.get(src_reg))}"
                accesses.append(Access(owner, owner_end, idx, ins.address, kind, mem_width(m), ea, src))
            if m.startswith("ldr") and ops[0].type == ARM_OP_REG:
                dst = reg_name(ins, ops[0])
                if dst:
                    regs[dst] = f"MEM{mem_width(m)}[0x{ea:08x}]" if ea is not None else f"LOAD@0x{ins.address:08x}"
            continue

        modeled = False
        if m in ("mov", "movs", "mov.w", "movs.w") and len(ops) >= 2 and ops[0].type == ARM_OP_REG:
            dst = reg_name(ins, ops[0])
            if dst:
                if ops[1].type == ARM_OP_REG:
                    src = reg_name(ins, ops[1]); regs[dst] = regs.get(src, f"{src}:UNKNOWN"); modeled = True
                elif ops[1].type == ARM_OP_IMM:
                    regs[dst] = int(ops[1].imm) & 0xFFFFFFFF; modeled = True

        if not modeled and m in ("add", "adds", "add.w", "adds.w", "sub", "subs", "sub.w", "subs.w") and ops and ops[0].type == ARM_OP_REG:
            dst = reg_name(ins, ops[0]); sign = "+" if m.startswith("add") else "-"
            if dst:
                if len(ops) == 2:
                    a = regs.get(dst, f"{dst}:UNKNOWN")
                    if ops[1].type == ARM_OP_IMM: b: Value = int(ops[1].imm)
                    elif ops[1].type == ARM_OP_REG:
                        rr = reg_name(ins, ops[1]); b = regs.get(rr, f"{rr}:UNKNOWN")
                    else: b = "UNKNOWN"
                else:
                    if ops[1].type == ARM_OP_REG:
                        rr = reg_name(ins, ops[1]); a = regs.get(rr, f"{rr}:UNKNOWN")
                    elif ops[1].type == ARM_OP_IMM: a = int(ops[1].imm)
                    else: a = "UNKNOWN"
                    if len(ops) > 2 and ops[2].type == ARM_OP_IMM: b = int(ops[2].imm)
                    elif len(ops) > 2 and ops[2].type == ARM_OP_REG:
                        rr = reg_name(ins, ops[2]); b = regs.get(rr, f"{rr}:UNKNOWN")
                    else: b = "UNKNOWN"
                regs[dst] = const_bin(sign, a, b); modeled = True

        if not modeled and m in ("lsls", "lsl", "lsl.w", "lsrs", "lsr", "lsr.w") and ops and ops[0].type == ARM_OP_REG:
            dst = reg_name(ins, ops[0])
            if dst:
                if len(ops) == 2:
                    a = regs.get(dst, f"{dst}:UNKNOWN"); n = int(ops[1].imm) if ops[1].type == ARM_OP_IMM else 0
                elif len(ops) >= 3:
                    rr = reg_name(ins, ops[1]) if ops[1].type == ARM_OP_REG else None
                    a = regs.get(rr, f"{rr}:UNKNOWN") if rr else "UNKNOWN"; n = int(ops[2].imm) if ops[2].type == ARM_OP_IMM else 0
                else: a, n = "UNKNOWN", 0
                regs[dst] = const_shift("<<" if m.startswith("lsl") else ">>", a, n); modeled = True

        if not modeled and m in ("ands", "and", "orrs", "orr") and ops and ops[0].type == ARM_OP_REG:
            dst = reg_name(ins, ops[0])
            if dst:
                if len(ops) == 2:
                    a = regs.get(dst, f"{dst}:UNKNOWN")
                    if ops[1].type == ARM_OP_REG:
                        rr = reg_name(ins, ops[1]); b = regs.get(rr, f"{rr}:UNKNOWN")
                    elif ops[1].type == ARM_OP_IMM: b = int(ops[1].imm)
                    else: b = "UNKNOWN"
                else:
                    rr1 = reg_name(ins, ops[1]) if len(ops) > 1 and ops[1].type == ARM_OP_REG else None
                    a = regs.get(rr1, f"{rr1}:UNKNOWN") if rr1 else "UNKNOWN"
                    if len(ops) > 2 and ops[2].type == ARM_OP_REG:
                        rr2 = reg_name(ins, ops[2]); b = regs.get(rr2, f"{rr2}:UNKNOWN")
                    elif len(ops) > 2 and ops[2].type == ARM_OP_IMM: b = int(ops[2].imm)
                    else: b = "UNKNOWN"
                regs[dst] = const_bin("&" if m.startswith("and") else "|", a, b); modeled = True

        if not modeled:
            set_unknown_written_regs(ins, regs)

    return accesses, calls, direct_strings, page_literals


def print_context(seq, idx: int, radius: int = 6) -> None:
    lo = max(0, idx - radius); hi = min(len(seq), idx + radius + 1)
    for j in range(lo, hi):
        ins = seq[j]; mark = ">>" if j == idx else "  "
        print(f"V063_CONTEXT={mark}|0x{ins.address:08x}|{ins.mnemonic}|{ins.op_str}")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} sections_dir")
    imgs = get_img_section(Path(sys.argv[1]))
    print(f"V063_IMG_SECTIONS={len(imgs)}")
    if len(imgs) != 1:
        print("OVERALL_VERDICT=B2Y_20780_FIELD_SEMANTICS_UNRESOLVED"); return 0

    global DATA, BIAS
    row, DATA = imgs[0]; _, BIAS = derive_mapping(DATA)
    if BIAS is None:
        print("OVERALL_VERDICT=B2Y_20780_FIELD_SEMANTICS_UNRESOLVED"); return 0
    print(f"V063_MAP_BIAS=0x{BIAS:08x}")
    print(f"V063_SECTION={row['index']}:{row['name']}")
    print(f"V063_MMIO_BASE=0x{MMIO_BASE:08x}")
    print("V063_TARGETS=" + ",".join(f"0x{x:08x}" for x in TARGETS))

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
    pools = find_page_literal_pools(DATA, BIAS)
    print(f"V063_PAGE_LITERAL_POOLS={len(pools)}")
    for p, v in pools: print(f"V063_PAGE_POOL=0x{p:08x}->0x{v:08x}")

    seed_xrefs = []
    for pool_va, pool_val in pools:
        for x in xrefs_to_pool(md, DATA, BIAS, pool_va): seed_xrefs.append((x, pool_va, pool_val))
    seed_xrefs = sorted(set(seed_xrefs))
    print(f"V063_PAGE_CODE_XREFS={len(seed_xrefs)}")
    for x, p, v in seed_xrefs: print(f"V063_PAGE_XREF=0x{x:08x}|pool=0x{p:08x}|value=0x{v:08x}")

    owners = {}
    for x, p, v in seed_xrefs:
        st = nearest_push(md, DATA, BIAS, x)
        print(f"V063_XREF_OWNER=0x{x:08x}|start={'-' if st is None else f'0x{st:08x}'}")
        if st is not None: owners.setdefault(st, []).append((x, p, v))
    print(f"V063_OWNER_FUNCTIONS={len(owners)}")

    all_accesses = []; owner_data = {}
    for st in sorted(owners):
        seq, en = decode_function(md, DATA, BIAS, st)
        accesses, calls, strings, page_lits = trace_function(seq, st, en)
        owner_data[st] = (seq, en, accesses, calls, strings, page_lits); all_accesses.extend(accesses)
        target_accesses = [a for a in accesses if a.address in TARGET_SET]
        print(f"\n=== V063_OWNER 0x{st:08x}-0x{en:08x} ===")
        print(f"V063_OWNER_SUMMARY=start=0x{st:08x}|end=0x{en:08x}|seed_xrefs={len(owners[st])}|page_accesses={len(accesses)}|target_accesses={len(target_accesses)}|is_v062_central={int(st==CENTRAL_OWNER)}")
        for a, t in calls:
            print(f"V063_CALL=owner=0x{st:08x}|0x{a:08x}->0x{t:08x}|relation={'WB_SETTER' if t==WB_SETTER else '-'}")
        for a, s in strings: print(f"V063_DIRECT_STRING=owner=0x{st:08x}|0x{a:08x}|{s}")
        for a, v in page_lits: print(f"V063_OWNER_PAGE_LITERAL=owner=0x{st:08x}|0x{a:08x}|0x{v:08x}")
        for ac in target_accesses:
            print(f"V063_TARGET_ACCESS=owner=0x{st:08x}|ins=0x{ac.ins_addr:08x}|{ac.kind}{ac.width}|addr=0x{ac.address:08x}|offset=+0x{ac.address-MMIO_BASE:02x}|source={ac.source}")
            print_context(seq, ac.ins_index)

    for t in TARGETS:
        rr = [a for a in all_accesses if a.address == t and a.kind == "READ"]
        ww = [a for a in all_accesses if a.address == t and a.kind == "WRITE"]
        owners_t = sorted(set(a.owner for a in all_accesses if a.address == t))
        print(f"V063_TARGET_COUNT=addr=0x{t:08x}|offset=+0x{t-MMIO_BASE:02x}|reads={len(rr)}|writes={len(ww)}|owners={len(owners_t)}|owner_list={','.join(f'0x{x:08x}' for x in owners_t) or '-'}")
        for a in ww:
            print(f"V063_WRITE_PROVENANCE=addr=0x{t:08x}|owner=0x{a.owner:08x}|ins=0x{a.ins_addr:08x}|source={a.source}")

    relevant_owners = sorted(set(a.owner for a in all_accesses if a.address in TARGET_SET))
    external = [x for x in relevant_owners if x != CENTRAL_OWNER]
    print("V063_RELEVANT_OWNERS=" + (",".join(f"0x{x:08x}" for x in relevant_owners) or "-"))
    print("V063_EXTERNAL_TARGET_OWNERS=" + (",".join(f"0x{x:08x}" for x in external) or "-"))
    central_calls = owner_data.get(CENTRAL_OWNER, ([], 0, [], [], [], []))[3]
    print(f"V063_CENTRAL_OWNER_CALLS_WB_SETTER={int(any(t == WB_SETTER for _, t in central_calls))}")

    if not relevant_owners:
        print("OVERALL_VERDICT=B2Y_20780_FIELD_SEMANTICS_UNRESOLVED_NO_EXACT_TARGET_ACCESS")
    else:
        print("OVERALL_VERDICT=B2Y_20780_FIELD_SEMANTICS_UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
