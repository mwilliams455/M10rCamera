#!/usr/bin/env python3
"""M10-R B2Y tone descriptor -> MMIO bitfield audit 1B.

Research-only. This extends Audit1A by perturbing every u32 field of the
canonical record-8 tone descriptor one bit at a time and observing the bounded
CPU-side register programmer. It does not emulate B2Y pixels and it does not
assign photographic semantics to synthetic values.

Primary questions:
  * which descriptor fields feed 0x20020800 / 0x20020804;
  * which output bits each input bit can influence;
  * exact ARM instructions responsible for 0x20020804 writes;
  * whether real record-8 occurrences differ in those controls.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN

from m10r_b2y_assets import parse_records, occurrences
from m10r_b2y_register_audit1a import (
    IMG_SHA, B2Y_SHA, CODE, TONE, Programmer, checked,
)

FOCUS = {0x20020800, 0x20020804, 0x20020808, 0x2002080C}
TONE_END = 0x420D4298
WRITE_WINDOW_RADIUS = 0x30


def hx(v: int) -> str:
    return f"0x{v:08x}"


def u32s(data: bytes) -> list[int]:
    if len(data) % 4:
        raise ValueError("descriptor length is not u32-aligned")
    return list(struct.unpack(f"<{len(data)//4}I", data))


def reg_ints(run: dict[str, Any]) -> dict[int, int]:
    return {int(k, 16): int(v, 16) for k, v in run["registers"].items()}


def diff_regs(base: dict[int, int], test: dict[int, int]) -> dict[str, dict[str, str]]:
    out = {}
    for addr in sorted(set(base) | set(test)):
        a = base.get(addr, 0)
        b = test.get(addr, 0)
        if a != b:
            out[hex(addr)] = {"baseline": hx(a), "test": hx(b), "xor": hx(a ^ b)}
    return out


def disasm_window(img: bytes, pc: int, radius: int = WRITE_WINDOW_RADIUS) -> list[dict[str, Any]]:
    start = max(CODE, (pc - radius) & ~3)
    end = (pc + radius + 4) & ~3
    # Programmer maps img[4:] at CODE.
    a = 4 + (start - CODE)
    b = 4 + (end - CODE)
    if a < 4 or b > len(img):
        return []
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    return [
        {
            "address": hex(ins.address),
            "bytes": ins.bytes.hex(),
            "mnemonic": ins.mnemonic,
            "op_str": ins.op_str,
            "is_write_pc": ins.address == pc,
        }
        for ins in md.disasm(img[a:b], start)
    ]


def summarize_field(field: dict[str, Any]) -> str:
    masks = field["influence_masks"]
    interesting = []
    for addr in ("0x20020800", "0x20020804", "0x20020808", "0x2002080c"):
        if addr in masks and int(masks[addr], 16):
            interesting.append(f"{addr}:{masks[addr]}")
    return ", ".join(interesting) if interesting else "none"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sections", type=Path)
    ap.add_argument("json_out", type=Path)
    ap.add_argument("md_out", type=Path)
    args = ap.parse_args()

    img = checked(args.sections / "092_IMG-System.bin", IMG_SHA)
    b2y = checked(args.sections / "074_IMG_Calibration_Data_data_calib_B2Y.bin.bin", B2Y_SHA)
    records = parse_records(b2y)
    tone_recs = occurrences(records, 8)
    if not tone_recs:
        raise SystemExit("B2Y record 8 not found")

    def payload(rec) -> bytes:
        return b2y[rec.payload_offset:rec.payload_offset + rec.size]

    default = payload(tone_recs[0])
    if len(default) != 44 * 4:
        raise SystemExit(f"unexpected record-8 size: {len(default)}")

    table0_rec = occurrences(records, 0x19)[1]
    table1_rec = occurrences(records, 0x1A)[1]
    table0 = payload(table0_rec)[:0xA000]
    table1 = payload(table1_rec)[:0xA000]
    p = Programmer(img, table0, table1)

    baseline_run = p.run(default, TONE, TONE_END, tone=True)
    baseline_regs = reg_ints(baseline_run)
    base_words = u32s(default)

    fields = []
    successful = 0
    failed = 0
    for index, base_value in enumerate(base_words):
        off = index * 4
        probes = []
        influence: dict[int, int] = {}
        for bit in range(32):
            test_value = base_value ^ (1 << bit)
            d = bytearray(default)
            struct.pack_into("<I", d, off, test_value)
            try:
                run = p.run(bytes(d), TONE, TONE_END, tone=True)
                test_regs = reg_ints(run)
                delta = diff_regs(baseline_regs, test_regs)
                for addr_s, item in delta.items():
                    addr = int(addr_s, 16)
                    influence[addr] = influence.get(addr, 0) | int(item["xor"], 16)
                focus_delta = {k: v for k, v in delta.items() if int(k, 16) in FOCUS}
                probes.append({
                    "input_bit": bit,
                    "input_mask": hx(1 << bit),
                    "test_value": hx(test_value),
                    "focus_delta": focus_delta,
                    "all_changed_registers": sorted(delta),
                })
                successful += 1
            except Exception as exc:  # synthetic illegal modes are evidence too
                probes.append({
                    "input_bit": bit,
                    "input_mask": hx(1 << bit),
                    "test_value": hx(test_value),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                failed += 1

        fields.append({
            "index": index,
            "descriptor_offset": hex(off),
            "baseline_value": hx(base_value),
            "influence_masks": {hex(a): hx(m) for a, m in sorted(influence.items())},
            "focus_input_bits": [
                {
                    "input_bit": q["input_bit"],
                    "input_mask": q["input_mask"],
                    "focus_delta": q.get("focus_delta", {}),
                }
                for q in probes if q.get("focus_delta")
            ],
            "failed_bits": [q for q in probes if "error" in q],
        })

    # Record every real record-8 occurrence without assuming all are legal in the
    # same runtime state. The bounded programmer either returns or records error.
    real_occurrences = []
    for n, rec in enumerate(tone_recs):
        data = payload(rec)
        entry = {
            "occurrence": n,
            "record_size": rec.size,
            "payload_offset": hex(rec.payload_offset),
            "u32": [hex(x) for x in u32s(data)] if len(data) % 4 == 0 else None,
        }
        if len(data) == len(default):
            try:
                run = p.run(data, TONE, TONE_END, tone=True)
                regs = reg_ints(run)
                entry["focus_registers"] = {
                    hex(a): hx(regs[a]) for a in sorted(FOCUS) if a in regs
                }
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
        real_occurrences.append(entry)

    # The dynamic baseline gives exact PCs that wrote 0x20020804. Disassemble
    # around each so later analysis can tie the RMW masks to descriptor loads.
    pcs_0804 = []
    for w in baseline_run["writes"]:
        if int(w["address"], 16) == 0x20020804:
            pc = int(w["pc"], 16)
            if pc not in pcs_0804:
                pcs_0804.append(pc)
    write_pc_windows = {hex(pc): disasm_window(img, pc) for pc in pcs_0804}

    report = {
        "schema": "m10r.b2y.datapath_audit1b.v1",
        "scope": "synthetic descriptor-bit -> CPU MMIO mapping; B2Y pixels are NOT emulated",
        "caution": "synthetic bit toggles establish packing/control dependencies, not legal photographic modes or semantic names",
        "img_section_sha256": IMG_SHA,
        "b2y_section_sha256": B2Y_SHA,
        "tone_programmer": {"start": hex(TONE), "end": hex(TONE_END)},
        "baseline_descriptor_u32": [hex(x) for x in base_words],
        "baseline_focus_registers": {
            hex(a): hx(baseline_regs[a]) for a in sorted(FOCUS) if a in baseline_regs
        },
        "baseline_0804_write_pcs": [hex(x) for x in pcs_0804],
        "probe_counts": {"successful": successful, "failed": failed},
        "fields": fields,
        "real_record8_occurrences": real_occurrences,
        "write_pc_disassembly": write_pc_windows,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# M10-R B2Y DATAPATH AUDIT1B — TONE CONTROL ROUTING",
        "",
        "Research-only. Renderer unchanged.",
        "",
        "## Baseline",
        "",
        f"- Tone programmer: `{hex(TONE)} .. {hex(TONE_END)}`",
        f"- Record-8 u32 fields: `{len(base_words)}`",
        f"- Bit probes successful / failed: `{successful} / {failed}`",
        "- Focus registers: " + ", ".join(
            f"`{hex(a)}={hx(baseline_regs[a])}`" for a in sorted(FOCUS) if a in baseline_regs
        ),
        "- `0x20020804` write PCs: " + ", ".join(f"`{hex(x)}`" for x in pcs_0804),
        "",
        "## Descriptor fields affecting focus registers",
        "",
        "| Descriptor offset | Baseline | Observed output-bit influence |",
        "|---:|---:|---|",
    ]
    for f in fields:
        s = summarize_field(f)
        if s != "none":
            lines.append(f"| `{f['descriptor_offset']}` | `{f['baseline_value']}` | `{s}` |")

    lines += [
        "",
        "## Fields affecting `0x20020804`",
        "",
    ]
    any_0804 = False
    for f in fields:
        if int(f["influence_masks"].get("0x20020804", "0"), 16):
            any_0804 = True
            lines.append(
                f"- descriptor `{f['descriptor_offset']}` baseline `{f['baseline_value']}` -> "
                f"output mask `{f['influence_masks']['0x20020804']}`"
            )
            for q in f["focus_input_bits"]:
                if "0x20020804" in q["focus_delta"]:
                    d = q["focus_delta"]["0x20020804"]
                    lines.append(
                        f"  - input bit {q['input_bit']} (`{q['input_mask']}`) -> "
                        f"`{d['baseline']} -> {d['test']}`, xor `{d['xor']}`"
                    )
    if not any_0804:
        lines.append("- No descriptor bit toggle changed `0x20020804`; control may be fixed or sourced outside record 8.")

    lines += [
        "",
        "## Real record-8 occurrences",
        "",
    ]
    for e in real_occurrences:
        if "focus_registers" in e:
            regs = ", ".join(f"`{k}={v}`" for k, v in e["focus_registers"].items())
            lines.append(f"- occurrence {e['occurrence']}: {regs}")
        else:
            lines.append(f"- occurrence {e['occurrence']}: `{e.get('error', 'size mismatch')}`")

    lines += [
        "",
        "## Interpretation boundary",
        "",
        "This audit can prove descriptor-to-register packing and control dependencies. It cannot by itself prove luma-vs-RGB signal routing, MEDIUM/DG pixel order, LUT coordinate scaling, clamp placement, Q15 rounding, or post-DG transfer semantics.",
        "",
    ]
    args.md_out.write_text("\n".join(lines))

    print(f"AUDIT1B_JSON={args.json_out}")
    print(f"AUDIT1B_MD={args.md_out}")
    print(f"AUDIT1B_PROBES_SUCCESSFUL={successful}")
    print(f"AUDIT1B_PROBES_FAILED={failed}")
    print("AUDIT1B_0804_WRITE_PCS=" + ",".join(hex(x) for x in pcs_0804))
    for f in fields:
        if int(f["influence_masks"].get("0x20020804", "0"), 16):
            print(
                f"AUDIT1B_0804_FIELD={f['descriptor_offset']};base={f['baseline_value']};"
                f"mask={f['influence_masks']['0x20020804']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
