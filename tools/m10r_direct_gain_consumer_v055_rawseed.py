#!/usr/bin/env python3
"""Fast v0.55 seed front-end.

Replaces full-image Capstone-lite discovery with C-speed byte-pattern searches for
the Thumb constructors that can directly build 0x2002008c / 0x20020090.  The
seeded driver still performs full-detail conservative proof only inside bounded
windows, and raw/page literal discovery still scans every extracted section.
"""
from __future__ import annotations

import re
import struct
from typing import List, Set, Tuple

import m10r_direct_gain_consumer_v055_seeded as seeded
from m10r_direct_gain_consumer_v055_seeded import Seed
from m10r_direct_gain_consumer_v055 import Section, TARGETS

# Thumb-2 MOVW/MOVT immediates use imm16 = imm4:i:imm3:imm8.  These patterns
# deliberately seed exact relevant constructors; Capstone in the bounded proof
# window remains authoritative for instruction decoding and dereferences.
MOVW_LOW_8C = re.compile(rb"\x40\xf2\x8c[\x00-\x0f]")
MOVW_LOW_90 = re.compile(rb"\x40\xf2\x90[\x00-\x0f]")
MOVT_HIGH_2002 = re.compile(rb"\xc2\xf2\x02[\x00-\x0f]")


def _add_matches(out: List[Seed], seen: Set[Tuple[str, int]], sec: Section,
                 pattern: re.Pattern[bytes], reason: str, target=None) -> None:
    for match in pattern.finditer(sec.data):
        off = match.start()
        if off & 1:
            continue
        key = (sec.index, off)
        if key in seen:
            continue
        seen.add(key)
        out.append(Seed(sec.index, off, reason, target))


def thumb_constructor_seed_scan(sections: List[Section]) -> List[Seed]:
    out: List[Seed] = []
    seen: Set[Tuple[str, int]] = set()
    for sec in sections:
        _add_matches(out, seen, sec, MOVW_LOW_8C, "thumb2-movw-low:0x008c", TARGETS[0])
        _add_matches(out, seen, sec, MOVW_LOW_90, "thumb2-movw-low:0x0090", TARGETS[1])
        _add_matches(out, seen, sec, MOVT_HIGH_2002, "thumb2-movt-high:0x2002")

        # 16-bit MOVS Rd,#imm8 is 00100:Rd:imm8.  It can supply a low immediate
        # before a later MOVT/shift/add sequence, so retain it as a conservative
        # seed without classifying it as address evidence.
        for imm, target in ((0x8C, TARGETS[0]), (0x90, TARGETS[1])):
            pos = 0
            needle = bytes((imm,))
            while True:
                pos = sec.data.find(needle, pos)
                if pos < 0:
                    break
                if not (pos & 1) and pos + 1 < len(sec.data) and 0x20 <= sec.data[pos + 1] <= 0x27:
                    key = (sec.index, pos)
                    if key not in seen:
                        seen.add(key)
                        out.append(Seed(sec.index, pos, f"thumb-movs-low:0x{imm:02x}", target))
                pos += 1
    return out


if __name__ == "__main__":
    seeded.lite_immediate_seed_scan = thumb_constructor_seed_scan
    print("V055_DISCOVERY=RAW_LITERAL_PLUS_THUMB_CONSTRUCTOR_PREFILTER")
    raise SystemExit(seeded.main())
