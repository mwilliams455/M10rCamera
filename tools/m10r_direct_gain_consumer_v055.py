#!/usr/bin/env python3
"""M10-R v0.55 conservative direct-gain consumer trace.

This intentionally distinguishes an address *reference* from an actual memory
*dereference*.  The two investigated RAM addresses are not promoted to image
'gains' unless a load from the address is observed and the loaded provenance
reaches a downstream consumer.

The analysis is deliberately bounded and intra-basic-block.  Ambiguous control
flow is treated as unresolved rather than inferred across branches/calls.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import argparse
import csv
import json
import struct
from typing import Dict, Iterable, List, Optional, Set, Tuple

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC

TARGETS = (0x2002008C, 0x20020090)
MAX_SECTION_BYTES = 80_000_000
MAX_FORWARD_INSNS = 32

LOAD_PREFIXES = (
    "ldr", "ldrb", "ldrh", "ldrsb", "ldrsh", "ldrd",
    "vldr",
)
STORE_PREFIXES = (
    "str", "strb", "strh", "strd", "vstr",
)
COMPARE_PREFIXES = ("cmp", "cmn", "tst", "teq", "vcmp")
ARITH_PREFIXES = (
    "add", "sub", "rsb", "adc", "sbc", "mul", "mla", "mls", "sdiv", "udiv",
    "lsl", "lsr", "asr", "ror", "and", "orr", "eor", "bic", "mvn",
    "vadd", "vsub", "vmul", "vdiv", "vmla", "vmls", "vneg", "vabs",
)
CALL_PREFIXES = ("bl", "blx")
BRANCH_PREFIXES = ("b", "bx", "cbz", "cbnz", "tbb", "tbh")


@dataclass
class Section:
    index: str
    name: str
    base: int
    path: Path
    data: bytes

    @property
    def end(self) -> int:
        return self.base + len(self.data)

    def read_u32_va(self, va: int) -> Optional[int]:
        off = va - self.base
        if off < 0 or off + 4 > len(self.data):
            return None
        return struct.unpack_from("<I", self.data, off)[0]


@dataclass
class Access:
    target: int
    section: str
    instruction_va: int
    instruction: str
    access_kind: str
    loaded_or_destination_register: Optional[str] = None
    forward_slice: List[str] = field(default_factory=list)
    consumer_operations: List[str] = field(default_factory=list)
    terminal_sink: Optional[str] = None
    confidence: str = "HIGH"

    def as_dict(self) -> dict:
        return {
            "target_address": f"0x{self.target:08x}",
            "instruction_va": f"0x{self.instruction_va:08x}",
            "function_or_routine": self.section,
            "access_kind": self.access_kind,
            "instruction": self.instruction,
            "loaded_or_destination_register": self.loaded_or_destination_register,
            "forward_slice": self.forward_slice,
            "consumer_operations": self.consumer_operations,
            "terminal_sink": self.terminal_sink,
            "nearby_constants": [],
            "confidence": self.confidence,
        }


def load_sections(root: Path) -> List[Section]:
    rows = list(csv.DictReader((root / "sections.csv").open(encoding="utf-8")))
    out: List[Section] = []
    for row in rows:
        base = int(row["image_base"], 16)
        path = root / row["file"]
        data = path.read_bytes()
        if base == 0 or not data or len(data) > MAX_SECTION_BYTES:
            continue
        out.append(Section(row["index"], row["name"], base, path, data))
    return out


def reg_name(md: Cs, reg_id: int) -> Optional[str]:
    if not reg_id:
        return None
    try:
        return md.reg_name(reg_id)
    except Exception:
        return None


def instruction_text(ins) -> str:
    return f"{ins.address:08x}: {ins.mnemonic} {ins.op_str}".rstrip()


def is_call(mn: str) -> bool:
    return mn in CALL_PREFIXES


def is_control_break(mn: str) -> bool:
    if is_call(mn):
        return False
    if mn in ("bx", "cbz", "cbnz", "tbb", "tbh"):
        return True
    # Covers b, beq, bne, b.w, etc., without treating bic/bl as branches.
    return mn == "b" or mn.startswith("b.") or (
        mn.startswith("b") and len(mn) <= 4 and mn not in ("bic", "bfi", "bfc")
    )


def mnemonic_starts(mn: str, prefixes: Iterable[str]) -> bool:
    return any(mn == p or mn.startswith(p + ".") or mn.startswith(p) for p in prefixes)


def resolve_mem_address(ins, op, consts: Dict[str, int], section: Section, md: Cs) -> Optional[int]:
    mem = op.mem
    base_name = reg_name(md, mem.base)
    index_name = reg_name(md, mem.index)
    disp = int(mem.disp)

    if mem.base == ARM_REG_PC or base_name == "pc":
        # Thumb PC used for literal loads is Align(address + 4, 4).
        base = (ins.address + 4) & ~3
    elif base_name and base_name in consts:
        base = consts[base_name]
    elif not mem.base:
        base = 0
    else:
        return None

    if index_name:
        if index_name not in consts:
            return None
        idx = consts[index_name]
        # Capstone exposes shift details inconsistently across ARM aliases.  Only
        # accept unshifted index expressions; anything else stays unresolved.
        try:
            shift_type = op.shift.type
            shift_value = op.shift.value
        except Exception:
            shift_type = 0
            shift_value = 0
        if shift_type or shift_value:
            return None
        base += idx

    return (base + disp) & 0xFFFFFFFF


def source_regs(ins, md: Cs) -> Set[str]:
    regs: Set[str] = set()
    for op in getattr(ins, "operands", []):
        if op.type == ARM_OP_REG:
            name = reg_name(md, op.reg)
            if name:
                regs.add(name)
        elif op.type == ARM_OP_MEM:
            for rid in (op.mem.base, op.mem.index):
                name = reg_name(md, rid)
                if name:
                    regs.add(name)
    return regs


def destination_reg(ins, md: Cs) -> Optional[str]:
    ops = getattr(ins, "operands", [])
    if not ops or ops[0].type != ARM_OP_REG:
        return None
    return reg_name(md, ops[0].reg)


def apply_constant_transfer(ins, md: Cs, section: Section, consts: Dict[str, int]) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Return (dst, value, reason) for simple exact constant/address transfers."""
    mn = ins.mnemonic.lower()
    ops = getattr(ins, "operands", [])
    if not ops or ops[0].type != ARM_OP_REG:
        return None, None, None
    dst = reg_name(md, ops[0].reg)
    if not dst:
        return None, None, None

    if mn in ("mov", "movs") and len(ops) >= 2:
        if ops[1].type == ARM_OP_IMM:
            return dst, int(ops[1].imm) & 0xFFFFFFFF, mn
        if ops[1].type == ARM_OP_REG:
            src = reg_name(md, ops[1].reg)
            if src in consts:
                return dst, consts[src], mn

    if mn.startswith("movw") and len(ops) >= 2 and ops[1].type == ARM_OP_IMM:
        old = consts.get(dst, 0)
        return dst, (old & 0xFFFF0000) | (int(ops[1].imm) & 0xFFFF), "movw"

    if mn.startswith("movt") and len(ops) >= 2 and ops[1].type == ARM_OP_IMM:
        if dst not in consts:
            # We refuse to invent the low half if it was not established.
            return dst, None, "movt-low-unknown"
        return dst, (consts[dst] & 0xFFFF) | ((int(ops[1].imm) & 0xFFFF) << 16), "movt"

    if mn.startswith("adr") and len(ops) >= 2 and ops[1].type == ARM_OP_IMM:
        # Capstone normally materializes ADR's absolute target as an immediate.
        return dst, int(ops[1].imm) & 0xFFFFFFFF, "adr"

    if (mn.startswith("add") or mn.startswith("sub")) and len(ops) >= 3:
        if ops[1].type == ARM_OP_REG and ops[2].type == ARM_OP_IMM:
            src = reg_name(md, ops[1].reg)
            if src in consts:
                imm = int(ops[2].imm)
                value = consts[src] + imm if mn.startswith("add") else consts[src] - imm
                return dst, value & 0xFFFFFFFF, mn

    # LDR literal that loads a 32-bit address constant.  This is *address
    # construction*, not a dereference of that RAM address.
    if mn.startswith("ldr") and len(ops) >= 2 and ops[1].type == ARM_OP_MEM:
        addr = resolve_mem_address(ins, ops[1], consts, section, md)
        base_name = reg_name(md, ops[1].mem.base)
        if addr is not None and (ops[1].mem.base == ARM_REG_PC or base_name == "pc"):
            value = section.read_u32_va(addr)
            if value is not None:
                return dst, value, "ldr-literal"

    return dst, None, None


def clobbered_registers(ins, md: Cs) -> Set[str]:
    try:
        _read, write = ins.regs_access()
        return {md.reg_name(r) for r in write if md.reg_name(r)}
    except Exception:
        dst = destination_reg(ins, md)
        return {dst} if dst else set()


def analyze_section(section: Section, md: Cs, exact_literal_sites: Dict[int, List[Tuple[str, int]]]):
    accesses: Dict[int, List[Access]] = defaultdict(list)
    address_sites: Dict[int, Set[Tuple[str, int, str]]] = defaultdict(set)

    consts: Dict[str, int] = {}
    prov: Dict[str, Tuple[int, int]] = {}  # reg -> (target, age)
    active_access: Dict[Tuple[int, int], Access] = {}

    for ins in md.disasm(section.data, section.base):
        mn = ins.mnemonic.lower()
        text = instruction_text(ins)
        ops = getattr(ins, "operands", [])

        # Age loaded provenance and expire the bounded slice.
        for reg, (target, age) in list(prov.items()):
            age += 1
            if age > MAX_FORWARD_INSNS:
                prov.pop(reg, None)
            else:
                prov[reg] = (target, age)

        # Record consumers using the pre-instruction provenance state.
        prov_regs = {r: t for r, (t, _age) in prov.items()}
        used = source_regs(ins, md)
        used_prov = [(r, prov_regs[r]) for r in used if r in prov_regs]

        if used_prov and mnemonic_starts(mn, ARITH_PREFIXES):
            for reg, target in used_prov:
                for acc in accesses[target]:
                    if acc.loaded_or_destination_register == reg or reg in [x.split("=",1)[0] for x in acc.forward_slice if "=" in x]:
                        if text not in acc.consumer_operations:
                            acc.consumer_operations.append(text)
                            acc.forward_slice.append(text)
                            if acc.terminal_sink is None:
                                acc.terminal_sink = f"ARITHMETIC@0x{ins.address:08x}"

        if used_prov and mnemonic_starts(mn, COMPARE_PREFIXES):
            for reg, target in used_prov:
                for acc in accesses[target]:
                    if acc.terminal_sink is None:
                        acc.terminal_sink = f"COMPARE@0x{ins.address:08x}"
                    acc.forward_slice.append(text)

        if mnemonic_starts(mn, STORE_PREFIXES) and ops:
            # For stores operand 0 is the value being written.
            if ops[0].type == ARM_OP_REG:
                src = reg_name(md, ops[0].reg)
                if src in prov_regs:
                    target = prov_regs[src]
                    for acc in accesses[target]:
                        if acc.terminal_sink is None:
                            acc.terminal_sink = f"STORE@0x{ins.address:08x}"
                        acc.forward_slice.append(text)

        if is_call(mn):
            call_args = [(r, prov_regs[r]) for r in ("r0", "r1", "r2", "r3") if r in prov_regs]
            for reg, target in call_args:
                for acc in accesses[target]:
                    if acc.terminal_sink is None:
                        acc.terminal_sink = f"CALL_ARG_{reg.upper()}@0x{ins.address:08x}"
                    acc.forward_slice.append(text)

        # Resolve memory operands against constants that existed before this instruction.
        memory_resolutions: List[Tuple[int, object]] = []
        for op_index, op in enumerate(ops):
            if op.type == ARM_OP_MEM:
                addr = resolve_mem_address(ins, op, consts, section, md)
                if addr in TARGETS:
                    memory_resolutions.append((op_index, addr))

        for op_index, target in memory_resolutions:
            if mnemonic_starts(mn, LOAD_PREFIXES):
                dst = destination_reg(ins, md)
                acc = Access(
                    target=target,
                    section=f"section {section.index} {section.name}",
                    instruction_va=ins.address,
                    instruction=text,
                    access_kind="READ",
                    loaded_or_destination_register=dst,
                    forward_slice=[text],
                )
                accesses[target].append(acc)
                if dst:
                    prov[dst] = (target, 0)
                active_access[(target, ins.address)] = acc
            elif mnemonic_starts(mn, STORE_PREFIXES):
                accesses[target].append(Access(
                    target=target,
                    section=f"section {section.index} {section.name}",
                    instruction_va=ins.address,
                    instruction=text,
                    access_kind="WRITE",
                    forward_slice=[text],
                ))
            else:
                accesses[target].append(Access(
                    target=target,
                    section=f"section {section.index} {section.name}",
                    instruction_va=ins.address,
                    instruction=text,
                    access_kind="UNKNOWN/UNRESOLVED",
                    forward_slice=[text],
                    confidence="MEDIUM",
                ))

        # Propagate provenance through simple register copies / arithmetic outputs.
        dst = destination_reg(ins, md)
        if dst and mn in ("mov", "movs") and len(ops) >= 2 and ops[1].type == ARM_OP_REG:
            src = reg_name(md, ops[1].reg)
            if src in prov:
                prov[dst] = prov[src]
                target = prov[src][0]
                for acc in accesses[target]:
                    acc.forward_slice.append(f"{dst}={src} :: {text}")
        elif dst and used_prov and mnemonic_starts(mn, ARITH_PREFIXES):
            # Arithmetic result remains derived from the target value.
            # If multiple targets ever meet, mark ambiguity by dropping provenance.
            ts = {t for _r, t in used_prov}
            if len(ts) == 1:
                target = next(iter(ts))
                prov[dst] = (target, 0)
                for acc in accesses[target]:
                    acc.forward_slice.append(f"{dst}=derived :: {text}")
            else:
                prov.pop(dst, None)
        else:
            # Kill written provenance unless this instruction was the proven target load.
            loaded_dsts = {
                a.loaded_or_destination_register
                for target in TARGETS for a in accesses[target]
                if a.instruction_va == ins.address and a.access_kind == "READ"
            }
            for wr in clobbered_registers(ins, md):
                if wr not in loaded_dsts:
                    prov.pop(wr, None)

        # Track exact simple address construction after memory resolution.  This is
        # evidence of an address reference only, never itself a target READ.
        c_dst, c_value, c_reason = apply_constant_transfer(ins, md, section, consts)
        if c_dst:
            if c_value is None:
                consts.pop(c_dst, None)
            else:
                consts[c_dst] = c_value
                if c_value in TARGETS:
                    address_sites[c_value].add((f"section {section.index} {section.name}", ins.address, c_reason or "constant"))
        for wr in clobbered_registers(ins, md):
            if wr != c_dst:
                consts.pop(wr, None)

        # Calls are terminal for volatile-register provenance in this conservative pass.
        if is_call(mn):
            for r in ("r0", "r1", "r2", "r3", "r12", "lr"):
                consts.pop(r, None)
                prov.pop(r, None)

        if is_control_break(mn):
            consts.clear()
            prov.clear()

    return accesses, address_sites


def target_verdict(reads: List[Access], address_count: int, unresolved: List[Access]) -> str:
    if reads:
        if any(a.consumer_operations or (a.terminal_sink and not a.terminal_sink.startswith("COMPARE")) for a in reads):
            return "PROVEN_READ_WITH_CONSUMER"
        return "PROVEN_READ_NO_CONSUMER"
    if unresolved:
        return "AMBIGUOUS"
    if address_count:
        return "ADDRESS_ONLY"
    return "NO_REFERENCE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path, help="directory produced by tools/m10r_sections.py")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    sections = load_sections(args.sections)
    print(f"V055_SECTIONS_SCANNED={len(sections)}")
    print("V055_TARGETS=" + ",".join(f"0x{x:08x}" for x in TARGETS))
    print(f"V055_MAX_FORWARD_INSNS={MAX_FORWARD_INSNS}")

    # Raw exact little-endian occurrences are useful discovery evidence but remain
    # ADDRESS_ONLY unless executable code proves a dereference.
    literal_sites: Dict[int, List[Tuple[str, int]]] = defaultdict(list)
    for sec in sections:
        for target in TARGETS:
            needle = struct.pack("<I", target)
            pos = 0
            while True:
                pos = sec.data.find(needle, pos)
                if pos < 0:
                    break
                literal_sites[target].append((f"section {sec.index} {sec.name}", sec.base + pos))
                pos += 1

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    md.skipdata = True

    all_accesses: Dict[int, List[Access]] = defaultdict(list)
    all_address_sites: Dict[int, Set[Tuple[str, int, str]]] = defaultdict(set)
    for sec in sections:
        accesses, sites = analyze_section(sec, md, literal_sites)
        for target, arr in accesses.items():
            all_accesses[target].extend(arr)
        for target, arr in sites.items():
            all_address_sites[target].update(arr)

    result = {"targets": {}, "overall_verdict": None}
    target_verdicts = []

    for target in TARGETS:
        acc = all_accesses[target]
        reads = [a for a in acc if a.access_kind == "READ"]
        writes = [a for a in acc if a.access_kind == "WRITE"]
        unresolved = [a for a in acc if a.access_kind == "UNKNOWN/UNRESOLVED"]
        arithmetic_consumers = [a for a in reads if a.consumer_operations]
        address_evidence = set(all_address_sites[target])
        for sec_name, va in literal_sites[target]:
            address_evidence.add((sec_name, va, "raw-little-endian-literal"))

        verdict = target_verdict(reads, len(address_evidence), unresolved)
        target_verdicts.append(verdict)
        key = f"{target:08X}"
        result["targets"][key] = {
            "target_address": f"0x{target:08x}",
            "reads": [a.as_dict() for a in reads],
            "writes": [a.as_dict() for a in writes],
            "unresolved": [a.as_dict() for a in unresolved],
            "address_only_evidence": [
                {"section": s, "va": f"0x{va:08x}", "reason": reason}
                for s, va, reason in sorted(address_evidence)
            ],
            "target_verdict": verdict,
        }

        print(f"\n=== TARGET 0x{target:08x} ===")
        for a in acc:
            print(json.dumps(a.as_dict(), sort_keys=True))
        for s, va, reason in sorted(address_evidence):
            print(f"ADDRESS_EVIDENCE target=0x{target:08x} va=0x{va:08x} section={s!r} reason={reason}")
        print(f"TARGET_{key}_READS={len(reads)}")
        print(f"TARGET_{key}_WRITES={len(writes)}")
        print(f"TARGET_{key}_ADDRESS_ONLY={len(address_evidence)}")
        print(f"TARGET_{key}_ARITHMETIC_CONSUMERS={len(arithmetic_consumers)}")
        print(f"TARGET_{key}_UNRESOLVED={len(unresolved)}")
        print(f"TARGET_{key}_VERDICT={verdict}")

    if any(v == "PROVEN_READ_WITH_CONSUMER" for v in target_verdicts):
        overall = "GAIN_CONSUMER_FOUND"
    elif any(v == "AMBIGUOUS" for v in target_verdicts):
        overall = "UNRESOLVED"
    elif any(v == "PROVEN_READ_NO_CONSUMER" for v in target_verdicts):
        # A real read exists, but v0.55 has not established an image arithmetic consumer.
        overall = "UNRESOLVED"
    else:
        overall = "NO_GAIN_CONSUMER"
    result["overall_verdict"] = overall
    print(f"\nOVERALL_VERDICT={overall}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"V055_JSON={args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
