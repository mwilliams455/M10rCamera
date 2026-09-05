#!/usr/bin/env python3
"""Switchable first-parity oracle for the recovered M10-R nonlinear B2Y core.

This tool intentionally preserves unresolved hardware questions instead of
silently choosing answers for them.

Firmware-proven inputs (from tools/m10r_b2y_assets.py):
  * dg_expanded_u16le.bin : exact 32,768-entry differential-gamma transfer
  * tone_*_q15.u32le      : exact 10,240-entry Q15 gain tables

Frozen functional pieces:
  DG:   y = expanded_dg[x] in table-coordinate space
  tone: idx = x >> 1; unity = 0x8000

Still unresolved at hardware-cycle precision:
  * relative DG/tone pixel-stage order
  * Q15 multiply rounding mode
  * exact clamp/limit sequencing
  * mapping from a real image signal into this scalar table-coordinate domain

Accordingly, every unresolved choice is an explicit CLI/API parameter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DG_ENTRIES = 32768
DG_COORD_MAX = DG_ENTRIES - 1
TONE_ENTRIES = 10240
TONE_COORD_MAX = TONE_ENTRIES * 2 - 1  # 0x4fff for resolutionCode=1
Q15_SHIFT = 15
Q15_UNITY = 0x8000
LIMIT_14BIT = 0x3FFF

VALID_ORDERS = ("dg-tone", "tone-dg", "dg-only", "tone-only")
VALID_ROUNDING = ("trunc", "nearest")
VALID_CLAMP = ("none", "14bit-each", "14bit-final")
VALID_TONE = ("low", "medium", "high")


@dataclass(frozen=True)
class Assets:
    dg: tuple[int, ...]
    tone: tuple[int, ...]
    tone_name: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unpack_u16(path: Path) -> tuple[int, ...]:
    data = path.read_bytes()
    if len(data) % 2:
        raise ValueError(f"{path}: odd byte length")
    return tuple(struct.unpack(f"<{len(data)//2}H", data))


def _unpack_u32(path: Path) -> tuple[int, ...]:
    data = path.read_bytes()
    if len(data) % 4:
        raise ValueError(f"{path}: non-u32 byte length")
    return tuple(struct.unpack(f"<{len(data)//4}I", data))


def load_assets(asset_dir: Path, tone_name: str = "medium") -> Assets:
    if tone_name not in VALID_TONE:
        raise ValueError(f"tone_name must be one of {VALID_TONE}")
    dg = _unpack_u16(asset_dir / "dg_expanded_u16le.bin")
    tone = _unpack_u32(asset_dir / f"tone_{tone_name}_q15.u32le")
    if len(dg) != DG_ENTRIES:
        raise ValueError(f"expected {DG_ENTRIES} DG entries, got {len(dg)}")
    if len(tone) != TONE_ENTRIES:
        raise ValueError(f"expected {TONE_ENTRIES} tone entries, got {len(tone)}")
    if any(a > b for a, b in zip(dg, dg[1:])):
        raise ValueError("DG curve is not monotonic")
    return Assets(dg=dg, tone=tone, tone_name=tone_name)


def clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def apply_dg(x: int, dg: Sequence[int]) -> int:
    """Apply the exact expanded DG curve in recovered table-coordinate space.

    Index clipping is a software safety boundary, not a claim that hardware
    clips at this point.
    """
    return int(dg[clamp(int(x), 0, DG_COORD_MAX)])


def apply_tone(x: int, tone: Sequence[int], rounding: str = "trunc") -> int:
    """Apply the frozen Q15 gain interpretation with selectable rounding.

    The supported first-parity tone coordinate is 0..0x4fff. Input clipping is
    only to prevent indexing outside the recovered active table.
    """
    if rounding not in VALID_ROUNDING:
        raise ValueError(f"rounding must be one of {VALID_ROUNDING}")
    xx = clamp(int(x), 0, TONE_COORD_MAX)
    gain = int(tone[xx >> 1])
    bias = 0 if rounding == "trunc" else (1 << (Q15_SHIFT - 1))
    return (xx * gain + bias) >> Q15_SHIFT


def _stage_limit(v: int, clamp_policy: str, *, final: bool) -> int:
    if clamp_policy not in VALID_CLAMP:
        raise ValueError(f"clamp_policy must be one of {VALID_CLAMP}")
    if clamp_policy == "14bit-each":
        return clamp(v, 0, LIMIT_14BIT)
    if clamp_policy == "14bit-final" and final:
        return clamp(v, 0, LIMIT_14BIT)
    return v


def apply_pipeline(
    x: int,
    assets: Assets,
    *,
    order: str = "dg-tone",
    rounding: str = "trunc",
    clamp_policy: str = "none",
) -> int:
    """Evaluate one scalar candidate pipeline.

    No default here should be read as a hardware claim. The defaults are merely
    deterministic starting candidates for parity experiments.
    """
    if order not in VALID_ORDERS:
        raise ValueError(f"order must be one of {VALID_ORDERS}")
    if rounding not in VALID_ROUNDING:
        raise ValueError(f"rounding must be one of {VALID_ROUNDING}")
    if clamp_policy not in VALID_CLAMP:
        raise ValueError(f"clamp_policy must be one of {VALID_CLAMP}")

    v = int(x)
    if order == "dg-tone":
        v = apply_dg(v, assets.dg)
        v = _stage_limit(v, clamp_policy, final=False)
        v = apply_tone(v, assets.tone, rounding)
        v = _stage_limit(v, clamp_policy, final=True)
    elif order == "tone-dg":
        v = apply_tone(v, assets.tone, rounding)
        v = _stage_limit(v, clamp_policy, final=False)
        v = apply_dg(v, assets.dg)
        v = _stage_limit(v, clamp_policy, final=True)
    elif order == "dg-only":
        v = apply_dg(v, assets.dg)
        v = _stage_limit(v, clamp_policy, final=True)
    elif order == "tone-only":
        v = apply_tone(v, assets.tone, rounding)
        v = _stage_limit(v, clamp_policy, final=True)
    return int(v)


def evaluate_curve(
    assets: Assets,
    *,
    order: str,
    rounding: str,
    clamp_policy: str,
    domain_max: int = TONE_COORD_MAX,
) -> list[int]:
    return [
        apply_pipeline(
            x,
            assets,
            order=order,
            rounding=rounding,
            clamp_policy=clamp_policy,
        )
        for x in range(domain_max + 1)
    ]


def pack_u16(values: Iterable[int]) -> bytes:
    vals = list(values)
    if any(v < 0 or v > 0xFFFF for v in vals):
        raise ValueError("cannot pack curve as u16: value outside 0..65535")
    return struct.pack(f"<{len(vals)}H", *vals)


def curve_summary(values: Sequence[int]) -> dict[str, object]:
    raw = pack_u16(values)
    return {
        "entries": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "monotonic": all(a <= b for a, b in zip(values, values[1:])),
        "sha256_u16le": _sha256(raw),
        "first32": list(values[:32]),
        "last32": list(values[-32:]),
    }


def compare_curves(a: Sequence[int], b: Sequence[int]) -> dict[str, object]:
    if len(a) != len(b):
        raise ValueError("curve lengths differ")
    diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    deltas = [abs(int(x) - int(y)) for x, y in zip(a, b)]
    return {
        "entries": len(a),
        "different_entries": len(diffs),
        "max_abs_delta": max(deltas) if deltas else 0,
        "first_difference_indices": diffs[:64],
        "first_difference_samples": [
            {"x": i, "a": int(a[i]), "b": int(b[i])} for i in diffs[:32]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asset_dir", type=Path)
    ap.add_argument("--tone", choices=VALID_TONE, default="medium")
    ap.add_argument("--order", choices=VALID_ORDERS, default="dg-tone")
    ap.add_argument("--rounding", choices=VALID_ROUNDING, default="trunc")
    ap.add_argument("--clamp", dest="clamp_policy", choices=VALID_CLAMP, default="none")
    ap.add_argument("--domain-max", type=lambda s: int(s, 0), default=TONE_COORD_MAX)
    ap.add_argument("--out-u16le", type=Path)
    ap.add_argument("--summary-json", type=Path)
    args = ap.parse_args()

    if args.domain_max < 0 or args.domain_max > TONE_COORD_MAX:
        raise SystemExit(f"--domain-max must be 0..{TONE_COORD_MAX:#x}")

    assets = load_assets(args.asset_dir, args.tone)
    values = evaluate_curve(
        assets,
        order=args.order,
        rounding=args.rounding,
        clamp_policy=args.clamp_policy,
        domain_max=args.domain_max,
    )
    summary = {
        "format": "m10r-b2y-nonlinear-oracle-v1",
        "tone": args.tone,
        "order": args.order,
        "rounding": args.rounding,
        "clamp_policy": args.clamp_policy,
        "domain": [0, args.domain_max],
        "curve": curve_summary(values),
        "uncertainty": {
            "stage_order": "open",
            "tone_rounding": "open",
            "clamp_sequence": "open",
            "live_signal_normalization": "open",
        },
    }

    if args.out_u16le:
        args.out_u16le.parent.mkdir(parents=True, exist_ok=True)
        args.out_u16le.write_bytes(pack_u16(values))
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
