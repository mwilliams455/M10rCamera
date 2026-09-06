#!/usr/bin/env python3
"""Strict v0.55 direct-gain verdict driver.

Keeps the candidate-seeded coverage from rawseed/seeded but refuses to call
bitfield read-modify-write traffic a gain consumer.  A target-derived value
that is only shifted/masked/ORed and written back to the same target is
classified as SELF_RMW.  A target-derived value reaching a BL/BLX argument is
reported as CALL_ARG_UNRESOLVED until the callee is explicitly modeled.

This script does not modify renderer/color/tone behavior; it is analysis only.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import argparse
import json
import re
from typing import Dict, List, Set, Tuple

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB

import m10r_direct_gain_consumer_v055_seeded as seeded
import m10r_direct_gain_consumer_v055_rawseed as rawseed
from m10r_direct_gain_consumer_v055 import Access, TARGETS, THUMB_PHASES, analyze_phase, load_sections, merge_accesses

# Reuse the tightened discovery policy already validated by v0.55 CI.
seeded.raw_seed_scan = rawseed.tight_raw_seed_scan
seeded.lite_immediate_seed_scan = rawseed.thumb_constructor_seed_scan
seeded.RAW_WINDOW_BEFORE = 0x1200
seeded.RAW_WINDOW_AFTER = 0x400

FIELD_OPS = {
    "lsl", "lsls", "lsr", "lsrs", "asr", "asrs", "ror", "rors",
    "and", "ands", "orr", "orrs", "eor", "eors", "bic", "bics",
    "bfi", "bfc", "ubfx", "sbfx", "mvn", "mvns",
}
CALL_RE = re.compile(r":\s+blx?\s", re.I)
STORE_RE = re.compile(r":\s+(?:str|strb|strh|strd|vstr)\b", re.I)
MN_RE = re.compile(r":\s+([a-z0-9.]+)\b", re.I)


def mnemonic(text: str) -> str:
    match = MN_RE.search(text)
    if not match:
        return ""
    return match.group(1).lower().split(".", 1)[0]


def classify_read(read: Access, writes: List[Access]) -> dict:
    """Classify the proven forward slice without inventing image semantics."""
    forward = list(read.forward_slice)
    op_mnemonics = [mnemonic(x) for x in read.consumer_operations]
    tainted_store_lines = [x for x in forward if STORE_RE.search(x)]
    call_lines = [x for x in forward if CALL_RE.search(x)]

    # validate_read_forward only adds a store when the stored source is tainted.
    # Match those store instructions to independently proven exact-target WRITEs.
    same_target_write_lines = {
        w.instruction for w in writes
        if w.target == read.target and w.section.index == read.section.index
    }
    self_store_lines = [x for x in tainted_store_lines if x in same_target_write_lines]
    other_store_lines = [x for x in tainted_store_lines if x not in same_target_write_lines]

    field_only = bool(op_mnemonics) and all(mn in FIELD_OPS for mn in op_mnemonics)
    self_rmw = bool(self_store_lines) and not other_store_lines and field_only

    if call_lines:
        consumer_class = "CALL_ARG_UNRESOLVED"
    elif other_store_lines:
        consumer_class = "STORE_OTHER_UNRESOLVED"
    elif self_rmw:
        consumer_class = "BITFIELD_SELF_RMW"
    elif read.consumer_operations:
        consumer_class = "ARITHMETIC_UNRESOLVED"
    elif tainted_store_lines:
        consumer_class = "STORE_UNRESOLVED"
    elif read.terminal_sink and read.terminal_sink.startswith("COMPARE"):
        consumer_class = "COMPARE_ONLY"
    else:
        consumer_class = "NO_MEANINGFUL_CONSUMER"

    # Strict direct-gain gate.  None of the generic unresolved classes proves
    # image arithmetic.  A future stage may promote a path only after identifying
    # a pixel/image sink or explicitly modeled callee behavior.
    direct_gain_consumer = False

    return {
        "consumer_class": consumer_class,
        "direct_gain_consumer": direct_gain_consumer,
        "self_rmw": self_rmw,
        "self_target_stores": self_store_lines,
        "other_tainted_stores": other_store_lines,
        "tainted_call_arguments": call_lines,
        "raw_arithmetic_operations": list(read.consumer_operations),
    }


def access_dict(access: Access, cls: dict | None = None) -> dict:
    out = access.as_dict()
    if cls is not None:
        out.update(cls)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    sections = load_sections(args.sections)
    by_index = {s.index: s for s in sections}
    known = sum(s.runtime_base is not None for s in sections)
    unknown = len(sections) - known

    raw_seeds, raw_literal_sites = seeded.raw_seed_scan(sections)
    lite_seeds = seeded.lite_immediate_seed_scan(sections)
    seeds = raw_seeds + lite_seeds
    windows = seeded.build_windows(sections, seeds)
    window_count = sum(len(v) for v in windows.values())
    window_bytes = sum(end - start for values in windows.values() for start, end in values)

    print("V055_DISCOVERY=TIGHT_RAW_TARGET_BASE_PLUS_PAIRED_THUMB_CONSTRUCTORS")
    print("V055_MODE=CANDIDATE_SEEDED_STRICT_CONSUMER_GATE")
    print(f"V055_SECTIONS_SCANNED={len(sections)}")
    print(f"V055_KNOWN_BASE_SECTIONS={known}")
    print(f"V055_UNKNOWN_BASE_SECTIONS={unknown}")
    print(f"V055_RAW_SEEDS={len(raw_seeds)}")
    print(f"V055_LITE_IMMEDIATE_SEEDS={len(lite_seeds)}")
    print(f"V055_SEED_WINDOWS={window_count}")
    print(f"V055_WINDOW_BYTES={window_bytes}")
    print("V055_THUMB_PHASES=" + ",".join(map(str, THUMB_PHASES)))
    print("V055_TARGETS=" + ",".join(f"0x{x:08x}" for x in TARGETS))

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    md.skipdata = True

    all_accesses: List[Access] = []
    constructed_sites: Dict[int, Set[Tuple[str, int, str]]] = defaultdict(set)
    for sec_index, ranges in windows.items():
        parent = by_index[sec_index]
        for start, end in ranges:
            win = seeded.WindowSection(parent, start, end)
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
            seeded.validate_read_forward(by_index[access.section.index], access, md)

    by_target: Dict[int, List[Access]] = defaultdict(list)
    all_writes = [a for a in all_accesses if a.access_kind == "WRITE"]
    for access in all_accesses:
        by_target[access.target].append(access)

    result = {
        "coverage": {
            "mode": "candidate-seeded-strict-consumer-gate",
            "sections_scanned": len(sections),
            "known_runtime_base_sections": known,
            "unknown_runtime_base_sections": unknown,
            "raw_seeds": len(raw_seeds),
            "lite_immediate_seeds": len(lite_seeds),
            "seed_windows": window_count,
            "window_bytes": window_bytes,
            "thumb_phases": list(THUMB_PHASES),
        },
        "targets": {},
        "overall_verdict": None,
    }

    any_direct_gain = False
    any_unresolved_escape = False
    any_proven_read = False

    for target in TARGETS:
        accesses = by_target[target]
        reads = [a for a in accesses if a.access_kind == "READ"]
        writes = [a for a in accesses if a.access_kind == "WRITE"]
        unresolved = [a for a in accesses if a.access_kind == "UNKNOWN/UNRESOLVED"]
        any_proven_read |= bool(reads)

        classes = {a.key(): classify_read(a, all_writes) for a in reads}
        direct = [a for a in reads if classes[a.key()]["direct_gain_consumer"]]
        self_rmw = [a for a in reads if classes[a.key()]["consumer_class"] == "BITFIELD_SELF_RMW"]
        call_arg = [a for a in reads if classes[a.key()]["consumer_class"] == "CALL_ARG_UNRESOLVED"]
        other_unresolved = [
            a for a in reads
            if classes[a.key()]["consumer_class"] in {
                "STORE_OTHER_UNRESOLVED", "ARITHMETIC_UNRESOLVED", "STORE_UNRESOLVED"
            }
        ]
        any_direct_gain |= bool(direct)
        any_unresolved_escape |= bool(call_arg or other_unresolved or unresolved)

        address_evidence: Set[Tuple[str, int, str]] = set(constructed_sites[target])
        for sec_index, off in raw_literal_sites[target]:
            address_evidence.add((sec_index, off, "raw-little-endian-literal"))

        if direct:
            verdict = "PROVEN_READ_WITH_CONSUMER"
        elif call_arg or other_unresolved or unresolved:
            verdict = "AMBIGUOUS"
        elif reads:
            verdict = "PROVEN_READ_NO_CONSUMER"
        elif address_evidence:
            verdict = "ADDRESS_ONLY"
        else:
            verdict = "NO_REFERENCE"

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
            "reads": [access_dict(a, classes[a.key()]) for a in reads],
            "writes": [access_dict(a) for a in writes],
            "unresolved": [access_dict(a) for a in unresolved],
            "address_only_evidence": evidence_json,
            "target_verdict": verdict,
        }

        print(f"\n=== TARGET 0x{target:08x} ===")
        for access in reads:
            print("READ_EVIDENCE " + json.dumps(access_dict(access, classes[access.key()]), sort_keys=True))
        for access in writes:
            print("WRITE_EVIDENCE " + json.dumps(access_dict(access), sort_keys=True))
        for ev in evidence_json:
            print("ADDRESS_EVIDENCE " + json.dumps(ev, sort_keys=True))

        # The legacy hard counter name is retained, but now means strict direct
        # gain/image arithmetic consumers rather than any bitwise arithmetic.
        print(f"TARGET_{key}_READS={len(reads)}")
        print(f"TARGET_{key}_WRITES={len(writes)}")
        print(f"TARGET_{key}_ADDRESS_ONLY={len(address_evidence)}")
        print(f"TARGET_{key}_ARITHMETIC_CONSUMERS={len(direct)}")
        print(f"TARGET_{key}_SELF_RMW_READS={len(self_rmw)}")
        print(f"TARGET_{key}_CALL_ARG_SINKS={len(call_arg)}")
        print(f"TARGET_{key}_OTHER_UNRESOLVED_CONSUMERS={len(other_unresolved)}")
        print(f"TARGET_{key}_UNRESOLVED={len(unresolved)}")
        print(f"TARGET_{key}_VERDICT={verdict}")

    if any_direct_gain:
        overall = "GAIN_CONSUMER_FOUND"
    elif any_unresolved_escape:
        overall = "UNRESOLVED"
    elif any_proven_read:
        overall = "NO_GAIN_CONSUMER"
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
