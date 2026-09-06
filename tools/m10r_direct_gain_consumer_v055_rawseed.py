#!/usr/bin/env python3
"""Fast v0.55 seed front-end with bounded, evidence-driven discovery.

Every extracted section is still searched for exact target/base literals.  Full
Capstone detail/dataflow is restricted to windows around those literals and
plausible Thumb-2 constructors.  Standalone low-byte MOVS and standalone MOVT
hits are deliberately not global seeds because they explode candidate volume;
a MOVT #0x2002 is retained when paired locally with a relevant low-half
constructor.  Capstone in the bounded proof window remains authoritative for
instruction decoding and actual target dereferences.
"""
from __future__ import annotations

from collections import defaultdict
import re
import struct
from typing import Dict, List, Set, Tuple

import m10r_direct_gain_consumer_v055_seeded as seeded
from m10r_direct_gain_consumer_v055_seeded import Seed
from m10r_direct_gain_consumer_v055 import Section, TARGETS

TARGET_BASES = (0x20020000, 0x20020080)
PAIR_LOOKBACK = 16

# Thumb-2 MOVW/MOVT immediate encoding: imm16 = imm4:i:imm3:imm8.
# These byte patterns are only prefilters; bounded Capstone decoding decides
# whether an instruction is real and whether the final address is dereferenced.
MOVW_LOW_00 = re.compile(rb"\x40\xf2\x00[\x00-\x0f]")
MOVW_LOW_80 = re.compile(rb"\x40\xf2\x80[\x00-\x0f]")
MOVW_LOW_8C = re.compile(rb"\x40\xf2\x8c[\x00-\x0f]")
MOVW_LOW_90 = re.compile(rb"\x40\xf2\x90[\x00-\x0f]")
MOVT_HIGH_2002 = re.compile(rb"\xc2\xf2\x02[\x00-\x0f]")
LOW_PATTERNS = (
    (MOVW_LOW_00, "0x0000", None),
    (MOVW_LOW_80, "0x0080", None),
    (MOVW_LOW_8C, "0x008c", TARGETS[0]),
    (MOVW_LOW_90, "0x0090", TARGETS[1]),
)


def _find_all(data: bytes, needle: bytes):
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0:
            return
        yield pos
        pos += 1


def tight_raw_seed_scan(
    sections: List[Section],
) -> Tuple[List[Seed], Dict[int, Set[Tuple[str, int]]]]:
    """All-section literal scan limited to targets and useful target bases."""
    seeds: List[Seed] = []
    exact: Dict[int, Set[Tuple[str, int]]] = defaultdict(set)
    seen: Set[Tuple[str, int, str]] = set()

    for sec in sections:
        for target in TARGETS:
            for pos in _find_all(sec.data, struct.pack("<I", target)):
                exact[target].add((sec.index, pos))
                reason = f"raw-target-{target:08x}"
                key = (sec.index, pos, reason)
                if key not in seen:
                    seen.add(key)
                    seeds.append(Seed(sec.index, pos, reason, target))

        for base in TARGET_BASES:
            for pos in _find_all(sec.data, struct.pack("<I", base)):
                reason = f"ram-target-base-{base:08x}"
                key = (sec.index, pos, reason)
                if key not in seen:
                    seen.add(key)
                    seeds.append(Seed(sec.index, pos, reason, None))

    return seeds, exact


def _aligned_movs_low(window: bytes, window_base: int) -> bool:
    """True for an aligned MOVS Rd,#0x8c/0x90 in a short pairing window."""
    for imm in (0x8C, 0x90):
        pos = 0
        while True:
            pos = window.find(bytes((imm,)), pos)
            if pos < 0:
                break
            absolute = window_base + pos
            if not (absolute & 1) and pos + 1 < len(window) and 0x20 <= window[pos + 1] <= 0x27:
                return True
            pos += 1
    return False


def thumb_constructor_seed_scan(sections: List[Section]) -> List[Seed]:
    """Seed exact target MOVW plus locally paired 0x2002 high-half builds."""
    out: List[Seed] = []
    seen: Set[Tuple[str, int]] = set()

    for sec in sections:
        # Exact target-low MOVW is useful by itself: a later high-half build may
        # be farther away than the pairing lookback but remains inside the proof
        # window.  Base-low MOVWs are not seeded globally; they are kept only
        # when paired with the relevant MOVT below.
        for pattern, low_text, target in LOW_PATTERNS[2:]:
            for match in pattern.finditer(sec.data):
                off = match.start()
                if off & 1:
                    continue
                key = (sec.index, off)
                if key not in seen:
                    seen.add(key)
                    out.append(Seed(sec.index, off, f"thumb2-movw-low:{low_text}", target))

        for movt in MOVT_HIGH_2002.finditer(sec.data):
            off = movt.start()
            if off & 1:
                continue
            lo = max(0, off - PAIR_LOOKBACK)
            preceding = sec.data[lo:off]

            paired_reason = None
            paired_target = None
            for pattern, low_text, target in LOW_PATTERNS:
                matches = [m for m in pattern.finditer(preceding) if not ((lo + m.start()) & 1)]
                if matches:
                    paired_reason = f"thumb2-movw-{low_text}+movt-0x2002"
                    paired_target = target
                    break
            if paired_reason is None and _aligned_movs_low(preceding, lo):
                paired_reason = "thumb-movs-target-low+movt-0x2002"

            if paired_reason is None:
                continue
            key = (sec.index, off)
            if key in seen:
                continue
            seen.add(key)
            out.append(Seed(sec.index, off, paired_reason, paired_target))

    return out


if __name__ == "__main__":
    seeded.raw_seed_scan = tight_raw_seed_scan
    seeded.lite_immediate_seed_scan = thumb_constructor_seed_scan
    seeded.RAW_WINDOW_BEFORE = 0x1200
    seeded.RAW_WINDOW_AFTER = 0x400
    print("V055_DISCOVERY=TIGHT_RAW_TARGET_BASE_PLUS_PAIRED_THUMB_CONSTRUCTORS")
    raise SystemExit(seeded.main())
