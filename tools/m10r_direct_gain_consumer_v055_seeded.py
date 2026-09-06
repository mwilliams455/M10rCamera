#!/usr/bin/env python3
"""M10-R v0.55 candidate-seeded direct-gain consumer trace.

This is the scalable driver for m10r_direct_gain_consumer_v055.  It keeps the
strict evidence gate but separates cheap all-section discovery from expensive
Capstone detail/dataflow:

  every section -> raw/page + lite-immediate seeds -> bounded Thumb windows
  -> exact target dereference -> independently validated forward provenance.

A literal containing a target remains ADDRESS_ONLY.  A target is READ/WRITE
only when an actual memory operand resolves exactly to 0x2002008c/90.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import re
import struct
from typing import Dict, List, Optional, Set, Tuple

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB
from capstone.arm import ARM_OP_REG

from m10r_direct_gain_consumer_v055 import (
    Access,
    ARITH_PREFIXES,
    CALL_PREFIXES,
    COMPARE_PREFIXES,
    MAX_FORWARD_INSNS,
    Section,
    STORE_PREFIXES,
    TARGETS,
    THUMB_PHASES,
    add_unique,
    analyze_phase,
    destination_reg,
    instruction_text,
    is_call,
    is_control_break,
    load_sections,
    merge_accesses,
    mnemonic_starts,
    read_registers,
    reg_name,
    safe_operands,
    target_verdict,
    written_registers,
)

RAW_WINDOW_BEFORE = 0x1800
RAW_WINDOW_AFTER = 0x800
IMM_WINDOW_BEFORE = 0x300
IMM_WINDOW_AFTER = 0x500
MERGE_GAP = 0x40
MAX_SEED_WINDOWS = 20000
LOW_IMM_RE = re.compile(r"(?<![0-9a-f])0x(?:8c|90)(?![0-9a-f])", re.I)
SEED_MNEMONICS = ("mov", "movw", "movt", "add", "sub", "adr", "ldr")


@dataclass(frozen=True)
class Seed:
    section_index: str
    offset: int
    reason: str
    target: Optional[int] = None


class WindowSection(Section):
    """A byte slice that reports offsets/VAs in its parent section coordinates."""

    def __init__(self, parent: Section, start: int, end: int):
        runtime = parent.runtime_base + start if parent.runtime_base is not None else None
        super().__init__(
            parent.index,
            parent.name,
            runtime,
            parent.analysis_base + start,
            parent.path,
            parent.data[start:end],
        )
        self.parent = parent
        self.parent_start = start

    @property
    def label(self) -> str:
        return self.parent.label

    def offset_of(self, analysis_va: int) -> int:
        return self.parent_start + (analysis_va - self.analysis_base)

    def runtime_va(self, analysis_va: int) -> Optional[int]:
        if self.parent.runtime_base is None:
            return None
        return self.parent.runtime_base + self.offset_of(analysis_va)

    def read_u32_analysis(self, analysis_va: int) -> Optional[int]:
        local = analysis_va - self.analysis_base
        if local < 0 or local + 4 > len(self.data):
            return None
        return struct.unpack_from("<I", self.data, local)[0]


def raw_seed_scan(sections: List[Section]) -> Tuple[List[Seed], Dict[int, Set[Tuple[str, int]]]]:
    seeds: List[Seed] = []
    exact: Dict[int, Set[Tuple[str, int]]] = defaultdict(set)
    page_re = re.compile(rb"[\x00-\xff]\x00\x02\x20", re.DOTALL)

    for sec in sections:
        seen: Set[Tuple[int, str]] = set()
        for target in TARGETS:
            needle = struct.pack("<I", target)
            pos = 0
            while True:
                pos = sec.data.find(needle, pos)
                if pos < 0:
                    break
                exact[target].add((sec.index, pos))
                key = (pos, f"raw-target-{target:08x}")
                if key not in seen:
                    seeds.append(Seed(sec.index, pos, key[1], target))
                    seen.add(key)
                pos += 1

        # Any 0x200200xx literal can be a nearby base/alias constructor.  Regex
        # runs in C and is much cheaper than unpacking every halfword in Python.
        for match in page_re.finditer(sec.data):
            pos = match.start()
            value = struct.unpack_from("<I", sec.data, pos)[0]
            if 0x20020000 <= value < 0x20020100:
                key = (pos, f"ram-page-literal-{value:08x}")
                if key not in seen:
                    seeds.append(Seed(sec.index, pos, key[1], value if value in TARGETS else None))
                    seen.add(key)
    return seeds, exact


def lite_immediate_seed_scan(sections: List[Section]) -> List[Seed]:
    """Fast no-detail disassembly used only to locate bounded proof windows."""
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    md.skipdata = True
    seeds: List[Seed] = []
    seen: Set[Tuple[str, int]] = set()

    for sec in sections:
        for phase in THUMB_PHASES:
            if phase >= len(sec.data):
                continue
            for address, _size, mnemonic, op_str in md.disasm_lite(
                sec.data[phase:], sec.analysis_base + phase
            ):
                mn = mnemonic.lower()
                if mn == ".byte" or not mn.startswith(SEED_MNEMONICS):
                    continue
                text = op_str.lower()
                target: Optional[int] = None
                if "0x2002008c" in text:
                    target = TARGETS[0]
                elif "0x20020090" in text:
                    target = TARGETS[1]
                interesting = target is not None or "0x2002" in text or bool(LOW_IMM_RE.search(text))
                if not interesting:
                    continue
                off = address - sec.analysis_base
                key = (sec.index, off)
                if key in seen:
                    continue
                seen.add(key)
                seeds.append(Seed(sec.index, off, f"lite-immediate:{mn} {op_str}", target))
    return seeds


def build_windows(sections: List[Section], seeds: List[Seed]) -> Dict[str, List[Tuple[int, int]]]:
    by_index = {s.index: s for s in sections}
    intervals: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for seed in seeds:
        sec = by_index[seed.section_index]
        rawish = seed.reason.startswith("raw-target") or seed.reason.startswith("ram-page")
        before = RAW_WINDOW_BEFORE if rawish else IMM_WINDOW_BEFORE
        after = RAW_WINDOW_AFTER if rawish else IMM_WINDOW_AFTER
        start = max(0, seed.offset - before) & ~1
        end = min(len(sec.data), seed.offset + after)
        if end > start:
            intervals[sec.index].append((start, end))

    merged: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    total = 0
    for sec_index, values in intervals.items():
        values.sort()
        for start, end in values:
            if merged[sec_index] and start <= merged[sec_index][-1][1] + MERGE_GAP:
                old_start, old_end = merged[sec_index][-1]
                merged[sec_index][-1] = (old_start, max(old_end, end))
            else:
                merged[sec_index].append((start, end))
                total += 1
    if total > MAX_SEED_WINDOWS:
        raise RuntimeError(f"candidate window explosion: {total} > {MAX_SEED_WINDOWS}")
    return merged


def validate_read_forward(parent: Section, acc: Access, md: Cs) -> None:
    """Recompute every READ consumer with kill-correct straight-line provenance."""
    acc.consumer_operations = []
    acc.terminal_sink = None
    acc.forward_slice = [acc.instruction]
    dst0 = acc.loaded_or_destination_register
    if not dst0:
        return

    off = acc.instruction_offset
    if off < 0 or off >= len(parent.data):
        return
    scan_end = min(len(parent.data), off + 0x200)
    insns = list(md.disasm(parent.data[off:scan_end], parent.analysis_base + off))
    if not insns:
        return

    provenance: Set[str] = {dst0}
    steps = 0
    first = True
    for ins in insns:
        if first:
            first = False
            continue
        if steps >= MAX_FORWARD_INSNS or not provenance:
            break
        steps += 1
        ops = safe_operands(ins)
        if ops is None:
            break
        mn = ins.mnemonic.lower()
        text = instruction_text(parent, ins)
        pre = set(provenance)
        reads = read_registers(ins, ops, md)
        used = pre.intersection(reads)
        established: Set[str] = set()
        dst = destination_reg(ops, md)

        if used and mnemonic_starts(mn, ARITH_PREFIXES):
            add_unique(acc.consumer_operations, text)
            add_unique(acc.forward_slice, text)
            if acc.terminal_sink is None:
                acc.terminal_sink = f"ARITHMETIC@{acc.loc(ins.address)}"
            if dst:
                established.add(dst)

        if used and mnemonic_starts(mn, COMPARE_PREFIXES):
            add_unique(acc.forward_slice, text)
            if acc.terminal_sink is None:
                acc.terminal_sink = f"COMPARE@{acc.loc(ins.address)}"

        if mnemonic_starts(mn, STORE_PREFIXES) and ops and ops[0].type == ARM_OP_REG:
            src = reg_name(md, ops[0].reg)
            if src in pre:
                add_unique(acc.forward_slice, text)
                if acc.terminal_sink is None:
                    acc.terminal_sink = f"STORE@{acc.loc(ins.address)}"

        if is_call(mn):
            for reg in ("r0", "r1", "r2", "r3"):
                if reg in pre:
                    add_unique(acc.forward_slice, text)
                    if acc.terminal_sink is None:
                        acc.terminal_sink = f"CALL_ARG_{reg.upper()}@{acc.loc(ins.address)}"
                    break

        if dst and mn in ("mov", "movs") and len(ops) >= 2 and ops[1].type == ARM_OP_REG:
            src = reg_name(md, ops[1].reg)
            if src in pre:
                established.add(dst)
                add_unique(acc.forward_slice, f"{dst}={src} :: {text}")

        written = written_registers(ins, ops, md)
        provenance.difference_update(written)
        provenance.update(established)

        if is_call(mn):
            provenance.difference_update(("r0", "r1", "r2", "r3", "r12", "lr"))
        if is_control_break(mn):
            break


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    sections = load_sections(args.sections)
    by_index = {s.index: s for s in sections}
    known = sum(s.runtime_base is not None for s in sections)
    unknown = len(sections) - known

    raw_seeds, raw_literal_sites = raw_seed_scan(sections)
    lite_seeds = lite_immediate_seed_scan(sections)
    seeds = raw_seeds + lite_seeds
    windows = build_windows(sections, seeds)
    window_count = sum(len(v) for v in windows.values())
    window_bytes = sum(end - start for values in windows.values() for start, end in values)

    print(f"V055_MODE=CANDIDATE_SEEDED")
    print(f"V055_SECTIONS_SCANNED={len(sections)}")
    print(f"V055_KNOWN_BASE_SECTIONS={known}")
    print(f"V055_UNKNOWN_BASE_SECTIONS={unknown}")
    print(f"V055_RAW_SEEDS={len(raw_seeds)}")
    print(f"V055_LITE_IMMEDIATE_SEEDS={len(lite_seeds)}")
    print(f"V055_SEED_WINDOWS={window_count}")
    print(f"V055_WINDOW_BYTES={window_bytes}")
    print("V055_THUMB_PHASES=" + ",".join(map(str, THUMB_PHASES)))
    print("V055_TARGETS=" + ",".join(f"0x{x:08x}" for x in TARGETS))
    print(f"V055_MAX_FORWARD_INSNS={MAX_FORWARD_INSNS}")

    # Emit seeds so the bounded coverage can be audited independently of verdicts.
    for seed in seeds:
        sec = by_index[seed.section_index]
        runtime = sec.runtime_base + seed.offset if sec.runtime_base is not None else None
        print("SEED " + json.dumps({
            "section": sec.label,
            "offset": f"0x{seed.offset:x}",
            "va": f"0x{runtime:08x}" if runtime is not None else None,
            "runtime_base_known": sec.runtime_base is not None,
            "reason": seed.reason,
            "target": f"0x{seed.target:08x}" if seed.target is not None else None,
        }, sort_keys=True))

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    md.skipdata = True

    all_accesses: List[Access] = []
    constructed_sites: Dict[int, Set[Tuple[str, int, str]]] = defaultdict(set)
    for sec_index, ranges in windows.items():
        parent = by_index[sec_index]
        for start, end in ranges:
            win = WindowSection(parent, start, end)
            for phase in THUMB_PHASES:
                accesses, sites = analyze_phase(win, md, phase)
                for access in accesses:
                    access.section = parent
                    all_accesses.append(access)
                for target, off, reason in sites:
                    constructed_sites[target].add((sec_index, off, reason))

    all_accesses = merge_accesses(all_accesses)
    for access in all_accesses:
        if access.access_kind == "READ":
            validate_read_forward(by_index[access.section.index], access, md)

    by_target: Dict[int, List[Access]] = defaultdict(list)
    for access in all_accesses:
        by_target[access.target].append(access)

    result = {
        "coverage": {
            "mode": "candidate-seeded",
            "sections_scanned": len(sections),
            "known_runtime_base_sections": known,
            "unknown_runtime_base_sections": unknown,
            "raw_seeds": len(raw_seeds),
            "lite_immediate_seeds": len(lite_seeds),
            "seed_windows": window_count,
            "window_bytes": window_bytes,
            "thumb_phases": list(THUMB_PHASES),
            "max_forward_instructions": MAX_FORWARD_INSNS,
        },
        "targets": {},
        "overall_verdict": None,
    }
    target_verdicts: List[str] = []

    for target in TARGETS:
        accesses = by_target[target]
        reads = [a for a in accesses if a.access_kind == "READ"]
        writes = [a for a in accesses if a.access_kind == "WRITE"]
        unresolved = [a for a in accesses if a.access_kind == "UNKNOWN/UNRESOLVED"]
        arithmetic = [a for a in reads if a.consumer_operations]

        address_evidence: Set[Tuple[str, int, str]] = set(constructed_sites[target])
        for sec_index, off in raw_literal_sites[target]:
            address_evidence.add((sec_index, off, "raw-little-endian-literal"))

        verdict = target_verdict(reads, len(address_evidence), unresolved)
        target_verdicts.append(verdict)
        key = f"{target:08X}"
        evidence_json = []
        for sec_index, off, reason in sorted(address_evidence):
            sec = by_index[sec_index]
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
        for access in accesses:
            print(json.dumps(access.as_dict(), sort_keys=True))
        for ev in evidence_json:
            print("ADDRESS_EVIDENCE " + json.dumps(ev, sort_keys=True))
        print(f"TARGET_{key}_READS={len(reads)}")
        print(f"TARGET_{key}_WRITES={len(writes)}")
        print(f"TARGET_{key}_ADDRESS_ONLY={len(address_evidence)}")
        print(f"TARGET_{key}_ARITHMETIC_CONSUMERS={len(arithmetic)}")
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
