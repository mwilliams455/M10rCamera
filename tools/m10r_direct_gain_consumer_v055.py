#!/usr/bin/env python3
"""M10-R v0.55 conservative direct-gain consumer trace.

The gate is deliberately strict:
  address occurrence != memory dereference != downstream consumer != image gain.

For 0x2002008c and 0x20020090 this pass proves only what can be recovered from
bounded, straight-line Thumb dataflow.  Unknown runtime bases are included with
synthetic *analysis* addresses; reports retain section offsets and never present
those synthetic values as firmware runtime VAs.
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
THUMB_PHASES = (0, 2)
SYNTHETIC_START = 0x60000000
SYNTHETIC_LIMIT = 0xE0000000

LOAD_PREFIXES = ("ldr", "ldrb", "ldrh", "ldrsb", "ldrsh", "ldrd", "vldr")
STORE_PREFIXES = ("str", "strb", "strh", "strd", "vstr")
COMPARE_PREFIXES = ("cmp", "cmn", "tst", "teq", "vcmp")
ARITH_PREFIXES = (
    "add", "sub", "rsb", "adc", "sbc", "mul", "mla", "mls", "sdiv", "udiv",
    "lsl", "lsr", "asr", "ror", "and", "orr", "eor", "bic", "mvn",
    "vadd", "vsub", "vmul", "vdiv", "vmla", "vmls", "vneg", "vabs",
)
CALL_PREFIXES = ("bl", "blx")


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


@dataclass
class Section:
    index: str
    name: str
    runtime_base: Optional[int]
    analysis_base: int
    path: Path
    data: bytes

    @property
    def label(self) -> str:
        return f"section {self.index} {self.name}"

    def offset_of(self, analysis_va: int) -> int:
        return analysis_va - self.analysis_base

    def runtime_va(self, analysis_va: int) -> Optional[int]:
        if self.runtime_base is None:
            return None
        return self.runtime_base + self.offset_of(analysis_va)

    def read_u32_analysis(self, analysis_va: int) -> Optional[int]:
        off = self.offset_of(analysis_va)
        if off < 0 or off + 4 > len(self.data):
            return None
        return struct.unpack_from("<I", self.data, off)[0]


@dataclass
class Access:
    target: int
    section: Section
    phase: int
    instruction_analysis_va: int
    instruction: str
    access_kind: str
    loaded_or_destination_register: Optional[str] = None
    forward_slice: List[str] = field(default_factory=list)
    consumer_operations: List[str] = field(default_factory=list)
    terminal_sink: Optional[str] = None
    confidence: str = "HIGH"

    @property
    def instruction_offset(self) -> int:
        return self.section.offset_of(self.instruction_analysis_va)

    @property
    def instruction_runtime_va(self) -> Optional[int]:
        return self.section.runtime_va(self.instruction_analysis_va)

    def key(self) -> Tuple[int, str, int, str, Optional[str]]:
        return (
            self.target,
            self.section.index,
            self.instruction_offset,
            self.access_kind,
            self.loaded_or_destination_register,
        )

    def loc(self, analysis_va: Optional[int] = None) -> str:
        if analysis_va is None:
            analysis_va = self.instruction_analysis_va
        off = self.section.offset_of(analysis_va)
        runtime = self.section.runtime_va(analysis_va)
        if runtime is not None:
            return f"0x{runtime:08x}"
        return f"{self.section.label}+0x{off:x}"

    def as_dict(self) -> dict:
        runtime = self.instruction_runtime_va
        return {
            "target_address": f"0x{self.target:08x}",
            "instruction_va": f"0x{runtime:08x}" if runtime is not None else None,
            "instruction_offset": f"0x{self.instruction_offset:x}",
            "analysis_va": f"0x{self.instruction_analysis_va:08x}",
            "runtime_base_known": self.section.runtime_base is not None,
            "function_or_routine": self.section.label,
            "thumb_phase": self.phase,
            "access_kind": self.access_kind,
            "instruction": self.instruction,
            "loaded_or_destination_register": self.loaded_or_destination_register,
            "forward_slice": self.forward_slice,
            "consumer_operations": self.consumer_operations,
            "terminal_sink": self.terminal_sink,
            "nearby_constants": [],
            "confidence": self.confidence,
        }


@dataclass
class Provenance:
    target: int
    origin_key: Tuple[int, str, int, str, Optional[str]]
    age: int = 0


def load_sections(root: Path) -> List[Section]:
    rows = list(csv.DictReader((root / "sections.csv").open(encoding="utf-8")))
    out: List[Section] = []
    synthetic_cursor = SYNTHETIC_START
    for row in rows:
        raw_base = int(row["image_base"], 16)
        path = root / row["file"]
        data = path.read_bytes()
        if not data or len(data) > MAX_SECTION_BYTES:
            continue
        if raw_base:
            runtime_base: Optional[int] = raw_base
            analysis_base = raw_base
        else:
            runtime_base = None
            synthetic_cursor = align_up(synthetic_cursor, 0x10000)
            analysis_base = synthetic_cursor
            synthetic_cursor = align_up(synthetic_cursor + len(data) + 0x10000, 0x10000)
            if synthetic_cursor >= SYNTHETIC_LIMIT:
                raise RuntimeError("synthetic analysis address space exhausted")
        out.append(Section(row["index"], row["name"], runtime_base, analysis_base, path, data))
    return out


def reg_name(md: Cs, reg_id: int) -> Optional[str]:
    if not reg_id:
        return None
    try:
        return md.reg_name(reg_id)
    except Exception:
        return None


def safe_operands(ins) -> Optional[list]:
    # Capstone skip-data pseudo-instructions have id==0 and reject detail queries.
    if getattr(ins, "id", 0) == 0:
        return None
    try:
        return list(ins.operands)
    except Exception:
        return None


def mnemonic_starts(mn: str, prefixes: Iterable[str]) -> bool:
    return any(mn == p or mn.startswith(p + ".") or mn.startswith(p) for p in prefixes)


def is_call(mn: str) -> bool:
    return mn in CALL_PREFIXES


def is_control_break(mn: str) -> bool:
    if is_call(mn):
        return False
    if mn in ("bx", "cbz", "cbnz", "tbb", "tbh"):
        return True
    return mn == "b" or mn.startswith("b.") or (
        mn.startswith("b") and len(mn) <= 4 and mn not in ("bic", "bfi", "bfc")
    )


def instruction_text(section: Section, ins) -> str:
    off = section.offset_of(ins.address)
    runtime = section.runtime_va(ins.address)
    loc = f"{runtime:08x}" if runtime is not None else f"+{off:08x}"
    return f"{loc}: {ins.mnemonic} {ins.op_str}".rstrip()


def resolve_mem_address(ins, op, consts: Dict[str, int], section: Section, md: Cs) -> Optional[int]:
    mem = op.mem
    base_name = reg_name(md, mem.base)
    index_name = reg_name(md, mem.index)
    disp = int(mem.disp)

    if mem.base == ARM_REG_PC or base_name == "pc":
        # Thumb literal PC is Align(current instruction + 4, 4) in the same image.
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
        try:
            if op.shift.type or op.shift.value:
                return None
        except Exception:
            pass
        base += consts[index_name]

    return (base + disp) & 0xFFFFFFFF


def destination_reg(ops: list, md: Cs) -> Optional[str]:
    if not ops or ops[0].type != ARM_OP_REG:
        return None
    return reg_name(md, ops[0].reg)


def read_registers(ins, ops: list, md: Cs) -> Set[str]:
    try:
        read, _write = ins.regs_access()
        return {md.reg_name(r) for r in read if md.reg_name(r)}
    except Exception:
        regs: Set[str] = set()
        for i, op in enumerate(ops):
            if op.type == ARM_OP_REG:
                name = reg_name(md, op.reg)
                # Most data-processing operand 0 is destination; stores/compares are
                # handled explicitly below, so avoid treating it as a generic source.
                if name and i != 0:
                    regs.add(name)
            elif op.type == ARM_OP_MEM:
                for rid in (op.mem.base, op.mem.index):
                    name = reg_name(md, rid)
                    if name:
                        regs.add(name)
        return regs


def written_registers(ins, ops: list, md: Cs) -> Set[str]:
    try:
        _read, write = ins.regs_access()
        return {md.reg_name(r) for r in write if md.reg_name(r)}
    except Exception:
        dst = destination_reg(ops, md)
        return {dst} if dst else set()


def apply_constant_transfer(
    ins, ops: list, md: Cs, section: Section, consts: Dict[str, int]
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Return an exact simple register constant transfer when statically provable."""
    mn = ins.mnemonic.lower()
    dst = destination_reg(ops, md)
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
            return dst, None, "movt-low-unknown"
        return dst, (consts[dst] & 0xFFFF) | ((int(ops[1].imm) & 0xFFFF) << 16), "movt"

    if mn.startswith("adr") and len(ops) >= 2 and ops[1].type == ARM_OP_IMM:
        # Capstone normally exposes ADR's resolved target as the immediate.
        return dst, int(ops[1].imm) & 0xFFFFFFFF, "adr"

    if (mn.startswith("add") or mn.startswith("sub")) and len(ops) >= 3:
        if ops[1].type == ARM_OP_REG and ops[2].type == ARM_OP_IMM:
            src = reg_name(md, ops[1].reg)
            if src in consts:
                imm = int(ops[2].imm)
                value = consts[src] + imm if mn.startswith("add") else consts[src] - imm
                return dst, value & 0xFFFFFFFF, mn

    # An LDR literal may load the *address value* from an in-image literal pool.
    # That is address construction only.  A later LDR/STR through that register is
    # required before classifying a target RAM access.
    if mn.startswith("ldr") and len(ops) >= 2 and ops[1].type == ARM_OP_MEM:
        addr = resolve_mem_address(ins, ops[1], consts, section, md)
        base_name = reg_name(md, ops[1].mem.base)
        if addr is not None and (ops[1].mem.base == ARM_REG_PC or base_name == "pc"):
            value = section.read_u32_analysis(addr)
            if value is not None:
                return dst, value, "ldr-literal"

    return dst, None, None


def add_unique(values: List[str], value: str) -> None:
    if value not in values:
        values.append(value)


def analyze_phase(section: Section, md: Cs, phase: int) -> Tuple[List[Access], Set[Tuple[int, int, str]]]:
    accesses: List[Access] = []
    access_by_key: Dict[Tuple[int, str, int, str, Optional[str]], Access] = {}
    address_sites: Set[Tuple[int, int, str]] = set()
    consts: Dict[str, int] = {}
    prov: Dict[str, Provenance] = {}

    start = phase
    if start >= len(section.data):
        return accesses, address_sites

    def origin_for(p: Provenance) -> Optional[Access]:
        return access_by_key.get(p.origin_key)

    for ins in md.disasm(section.data[start:], section.analysis_base + start):
        mn = ins.mnemonic.lower()
        ops = safe_operands(ins)
        if ops is None:
            # Data/padding breaks straight-line proof.  Crucially, do not ask
            # Capstone for operands/regs on skip-data pseudo-instructions.
            consts.clear()
            prov.clear()
            continue
        text = instruction_text(section, ins)

        # Bounded lifetime for loaded-value provenance.
        for reg, p in list(prov.items()):
            p.age += 1
            if p.age > MAX_FORWARD_INSNS:
                prov.pop(reg, None)

        pre_prov = dict(prov)
        read_regs = read_registers(ins, ops, md)
        used = [(r, pre_prov[r]) for r in read_regs if r in pre_prov]

        # Classify downstream consumers before mutating register state.
        if used and mnemonic_starts(mn, ARITH_PREFIXES):
            for _reg, p in used:
                acc = origin_for(p)
                if acc:
                    add_unique(acc.consumer_operations, text)
                    add_unique(acc.forward_slice, text)
                    if acc.terminal_sink is None:
                        acc.terminal_sink = f"ARITHMETIC@{acc.loc(ins.address)}"

        if used and mnemonic_starts(mn, COMPARE_PREFIXES):
            for _reg, p in used:
                acc = origin_for(p)
                if acc:
                    add_unique(acc.forward_slice, text)
                    if acc.terminal_sink is None:
                        acc.terminal_sink = f"COMPARE@{acc.loc(ins.address)}"

        # Store operand 0 is the value written, so record it explicitly even if
        # Capstone's generic read-register metadata is sparse for this alias.
        if mnemonic_starts(mn, STORE_PREFIXES) and ops and ops[0].type == ARM_OP_REG:
            src = reg_name(md, ops[0].reg)
            if src in pre_prov:
                acc = origin_for(pre_prov[src])
                if acc:
                    add_unique(acc.forward_slice, text)
                    if acc.terminal_sink is None:
                        acc.terminal_sink = f"STORE@{acc.loc(ins.address)}"

        if is_call(mn):
            for reg in ("r0", "r1", "r2", "r3"):
                if reg in pre_prov:
                    acc = origin_for(pre_prov[reg])
                    if acc:
                        add_unique(acc.forward_slice, text)
                        if acc.terminal_sink is None:
                            acc.terminal_sink = f"CALL_ARG_{reg.upper()}@{acc.loc(ins.address)}"

        # Resolve target memory accesses using constants valid on entry to this instruction.
        memory_targets: List[int] = []
        for op in ops:
            if op.type != ARM_OP_MEM:
                continue
            addr = resolve_mem_address(ins, op, consts, section, md)
            if addr in TARGETS:
                memory_targets.append(addr)

        loaded_dsts: Set[str] = set()
        for target in sorted(set(memory_targets)):
            if mnemonic_starts(mn, LOAD_PREFIXES):
                dst = destination_reg(ops, md)
                acc = Access(
                    target=target,
                    section=section,
                    phase=phase,
                    instruction_analysis_va=ins.address,
                    instruction=text,
                    access_kind="READ",
                    loaded_or_destination_register=dst,
                    forward_slice=[text],
                    confidence="HIGH" if section.runtime_base is not None else "MEDIUM",
                )
                accesses.append(acc)
                access_by_key[acc.key()] = acc
                if dst:
                    loaded_dsts.add(dst)
                    prov[dst] = Provenance(target, acc.key(), 0)
            elif mnemonic_starts(mn, STORE_PREFIXES):
                acc = Access(
                    target=target,
                    section=section,
                    phase=phase,
                    instruction_analysis_va=ins.address,
                    instruction=text,
                    access_kind="WRITE",
                    forward_slice=[text],
                    confidence="HIGH" if section.runtime_base is not None else "MEDIUM",
                )
                accesses.append(acc)
                access_by_key[acc.key()] = acc
            else:
                acc = Access(
                    target=target,
                    section=section,
                    phase=phase,
                    instruction_analysis_va=ins.address,
                    instruction=text,
                    access_kind="UNKNOWN/UNRESOLVED",
                    forward_slice=[text],
                    confidence="MEDIUM" if section.runtime_base is not None else "LOW",
                )
                accesses.append(acc)
                access_by_key[acc.key()] = acc

        # Propagate loaded provenance into straightforward data-processing results.
        dst = destination_reg(ops, md)
        if dst and mn in ("mov", "movs") and len(ops) >= 2 and ops[1].type == ARM_OP_REG:
            src = reg_name(md, ops[1].reg)
            if src in pre_prov:
                p = pre_prov[src]
                prov[dst] = Provenance(p.target, p.origin_key, 0)
                acc = origin_for(p)
                if acc:
                    add_unique(acc.forward_slice, f"{dst}={src} :: {text}")
        elif dst and used and mnemonic_starts(mn, ARITH_PREFIXES):
            origins = {p.origin_key for _reg, p in used}
            targets = {p.target for _reg, p in used}
            if len(origins) == 1 and len(targets) == 1:
                p = used[0][1]
                prov[dst] = Provenance(p.target, p.origin_key, 0)
                acc = origin_for(p)
                if acc:
                    add_unique(acc.forward_slice, f"{dst}=derived :: {text}")
            else:
                prov.pop(dst, None)

        # Exact constant/address transfer.  This runs after access resolution so
        # a PC-relative literal that *contains* 0x2002008c/90 is not confused with
        # a dereference of that RAM address.
        c_dst, c_value, c_reason = apply_constant_transfer(ins, ops, md, section, consts)

        # Kill stale register state written by the current instruction, preserving
        # only values just established by proven load/provenance/constant transfer.
        written = written_registers(ins, ops, md)
        for wr in written:
            if wr not in loaded_dsts and wr != dst:
                prov.pop(wr, None)
            if wr != c_dst:
                consts.pop(wr, None)

        if c_dst:
            if c_value is None:
                consts.pop(c_dst, None)
            else:
                consts[c_dst] = c_value
                if c_value in TARGETS:
                    address_sites.add((c_value, section.offset_of(ins.address), c_reason or "constant"))

        # Calls terminate volatile-register proof.  We record call arguments above,
        # but do not infer callee behavior.
        if is_call(mn):
            for reg in ("r0", "r1", "r2", "r3", "r12", "lr"):
                consts.pop(reg, None)
                prov.pop(reg, None)

        if is_control_break(mn):
            consts.clear()
            prov.clear()

    return accesses, address_sites


def merge_accesses(items: List[Access]) -> List[Access]:
    """Deduplicate the same decoded instruction seen from both Thumb phases."""
    merged: Dict[Tuple[int, str, int, str, Optional[str]], Access] = {}
    for acc in items:
        key = acc.key()
        if key not in merged:
            merged[key] = acc
            continue
        dst = merged[key]
        for v in acc.forward_slice:
            add_unique(dst.forward_slice, v)
        for v in acc.consumer_operations:
            add_unique(dst.consumer_operations, v)
        if dst.terminal_sink is None and acc.terminal_sink is not None:
            dst.terminal_sink = acc.terminal_sink
        if dst.confidence == "LOW" and acc.confidence != "LOW":
            dst.confidence = acc.confidence
    return sorted(merged.values(), key=lambda a: (a.target, a.section.index, a.instruction_offset, a.access_kind))


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
    known = sum(s.runtime_base is not None for s in sections)
    unknown = len(sections) - known
    print(f"V055_SECTIONS_SCANNED={len(sections)}")
    print(f"V055_KNOWN_BASE_SECTIONS={known}")
    print(f"V055_UNKNOWN_BASE_SECTIONS={unknown}")
    print("V055_THUMB_PHASES=" + ",".join(map(str, THUMB_PHASES)))
    print("V055_TARGETS=" + ",".join(f"0x{x:08x}" for x in TARGETS))
    print(f"V055_MAX_FORWARD_INSNS={MAX_FORWARD_INSNS}")

    # Raw target words remain address evidence only.  Search every extracted
    # section, including sections whose runtime load address is unknown.
    raw_literal_sites: Dict[int, Set[Tuple[str, int]]] = defaultdict(set)
    for sec in sections:
        for target in TARGETS:
            needle = struct.pack("<I", target)
            pos = 0
            while True:
                pos = sec.data.find(needle, pos)
                if pos < 0:
                    break
                raw_literal_sites[target].add((sec.index, pos))
                pos += 1

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    md.skipdata = True

    all_accesses: List[Access] = []
    constructed_sites: Dict[int, Set[Tuple[str, int, str]]] = defaultdict(set)
    for sec in sections:
        for phase in THUMB_PHASES:
            accesses, sites = analyze_phase(sec, md, phase)
            all_accesses.extend(accesses)
            for target, off, reason in sites:
                constructed_sites[target].add((sec.index, off, reason))

    all_accesses = merge_accesses(all_accesses)
    by_target: Dict[int, List[Access]] = defaultdict(list)
    for acc in all_accesses:
        by_target[acc.target].append(acc)

    result = {
        "coverage": {
            "sections_scanned": len(sections),
            "known_runtime_base_sections": known,
            "unknown_runtime_base_sections": unknown,
            "thumb_phases": list(THUMB_PHASES),
            "max_forward_instructions": MAX_FORWARD_INSNS,
        },
        "targets": {},
        "overall_verdict": None,
    }
    target_verdicts: List[str] = []

    section_by_index = {s.index: s for s in sections}

    for target in TARGETS:
        acc = by_target[target]
        reads = [a for a in acc if a.access_kind == "READ"]
        writes = [a for a in acc if a.access_kind == "WRITE"]
        unresolved = [a for a in acc if a.access_kind == "UNKNOWN/UNRESOLVED"]
        arithmetic_consumers = [a for a in reads if a.consumer_operations]

        address_evidence: Set[Tuple[str, int, str]] = set(constructed_sites[target])
        for sec_index, off in raw_literal_sites[target]:
            address_evidence.add((sec_index, off, "raw-little-endian-literal"))

        verdict = target_verdict(reads, len(address_evidence), unresolved)
        target_verdicts.append(verdict)
        key = f"{target:08X}"
        evidence_json = []
        for sec_index, off, reason in sorted(address_evidence):
            sec = section_by_index[sec_index]
            runtime = sec.runtime_base + off if sec.runtime_base is not None else None
            evidence_json.append({
                "section": sec.label,
                "offset": f"0x{off:x}",
                "va": f"0x{runtime:08x}" if runtime is not None else None,
                "runtime_base_known": sec.runtime_base is not None,
                "reason": reason,
            })

        result["targets"][key] = {
            "target_address": f"0x{target:08x}",
            "reads": [a.as_dict() for a in reads],
            "writes": [a.as_dict() for a in writes],
            "unresolved": [a.as_dict() for a in unresolved],
            "address_only_evidence": evidence_json,
            "target_verdict": verdict,
        }

        print(f"\n=== TARGET 0x{target:08x} ===")
        for a in acc:
            print(json.dumps(a.as_dict(), sort_keys=True))
        for ev in evidence_json:
            print("ADDRESS_EVIDENCE " + json.dumps(ev, sort_keys=True))
        print(f"TARGET_{key}_READS={len(reads)}")
        print(f"TARGET_{key}_WRITES={len(writes)}")
        print(f"TARGET_{key}_ADDRESS_ONLY={len(address_evidence)}")
        print(f"TARGET_{key}_ARITHMETIC_CONSUMERS={len(arithmetic_consumers)}")
        print(f"TARGET_{key}_UNRESOLVED={len(unresolved)}")
        print(f"TARGET_{key}_VERDICT={verdict}")

    if any(v == "PROVEN_READ_WITH_CONSUMER" for v in target_verdicts):
        overall = "GAIN_CONSUMER_FOUND"
    elif any(v in ("AMBIGUOUS", "PROVEN_READ_NO_CONSUMER") for v in target_verdicts):
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
