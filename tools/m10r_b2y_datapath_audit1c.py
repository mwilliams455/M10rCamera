#!/usr/bin/env python3
"""Audit1C: resolve record-8 +0x08 table-copy control and tone write sequence.

Research-only. Relaxes Audit1A's expected-copy assertion solely to log the
arguments produced by synthetic +0x08 values. No B2Y pixels are emulated.
"""
from __future__ import annotations
import argparse, json, struct
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR, UC_ARM_REG_PC

from m10r_b2y_assets import parse_records, occurrences
from m10r_b2y_register_audit1a import (
    IMG_SHA, B2Y_SHA, CODE, TONE, COPY, RETURN, Programmer, checked,
)

TONE_END = 0x420D4298
CONTROL_START = 0x420D3C50
CONTROL_END = 0x420D3D70


def hx(v: int) -> str: return f"0x{v:08x}"


class RelaxedProgrammer(Programmer):
    def code(self, uc, address, size, unused):
        self.instructions += 1
        if address == COPY:
            dst, src, count = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            self.copies.append({
                "helper": hex(address), "caller_lr": hex(uc.reg_read(UC_ARM_REG_LR)),
                "destination": hex(dst), "source": hex(src), "bytes": count,
            })
            # Only reproduce the two already-proven legal table copies. For
            # synthetic illegal requests, log and return without touching RAM.
            if dst in (0x20A00000, 0x20A0A000) and count == 0xA000:
                data = bytes(uc.mem_read(src, count))
                uc.mem_write(dst, data)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not self.allowed[0] <= address < self.allowed[1]:
            raise RuntimeError(f"execution escaped bounded programmer at {address:#x}")


def disasm(img: bytes, start: int, end: int) -> list[dict[str, Any]]:
    a = 4 + start - CODE
    b = 4 + end - CODE
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    return [{"address": hex(i.address), "mnemonic": i.mnemonic, "op_str": i.op_str, "bytes": i.bytes.hex()}
            for i in md.disasm(img[a:b], start)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sections", type=Path)
    ap.add_argument("json_out", type=Path)
    ap.add_argument("md_out", type=Path)
    args = ap.parse_args()

    img = checked(args.sections / "092_IMG-System.bin", IMG_SHA)
    b2y = checked(args.sections / "074_IMG_Calibration_Data_data_calib_B2Y.bin.bin", B2Y_SHA)
    records = parse_records(b2y)
    def payload(rec): return b2y[rec.payload_offset:rec.payload_offset + rec.size]
    tone = payload(occurrences(records, 8)[0])
    t0 = payload(occurrences(records, 0x19)[1])[:0xA000]
    t1 = payload(occurrences(records, 0x1A)[1])[:0xA000]
    base08 = struct.unpack_from("<I", tone, 8)[0]

    p = RelaxedProgrammer(img, t0, t1)
    probes = []
    for value in (0, 1, 2, 3, 4, 0x10, 0x100, 0xFFFFFFFF):
        d = bytearray(tone)
        struct.pack_into("<I", d, 8, value)
        try:
            run = p.run(bytes(d), TONE, TONE_END, tone=True)
            probes.append({
                "descriptor_0x08": hx(value),
                "returned": True,
                "instructions": run["instructions"],
                "copies": run["byte_copy_calls"],
                "focus": {k: v for k, v in run["registers"].items() if k in ("0x20020800","0x20020804")},
            })
        except Exception as exc:
            probes.append({"descriptor_0x08": hx(value), "returned": False,
                           "error": f"{type(exc).__name__}: {exc}", "copies": list(getattr(p, "copies", []))})

    control = disasm(img, CONTROL_START, CONTROL_END)
    whole = disasm(img, TONE, TONE_END)
    copy_callsites = [i for i in whole if i["mnemonic"].startswith("bl") and "4204f2ec" in i["op_str"].lower()]

    report = {
        "schema": "m10r.b2y.datapath_audit1c.v1",
        "scope": "record-8 +0x08 copy-argument logging and static ARM disassembly; no pixel emulation",
        "baseline_descriptor_0x08": hx(base08),
        "probes": probes,
        "copy_helper": hex(COPY),
        "copy_callsites": copy_callsites,
        "control_disassembly": control,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# M10-R B2Y DATAPATH AUDIT1C — RECORD-8 +0x08 TABLE CONTROL",
        "", "Research-only. Renderer unchanged.", "",
        f"Baseline record-8 `+0x08` = `{hx(base08)}`.", "",
        "## Synthetic +0x08 copy requests", "",
        "| +0x08 | Returned | Copy requests |", "|---:|:---:|---|",
    ]
    for q in probes:
        cs = "; ".join(f"dst={c['destination']} src={c['source']} bytes={c['bytes']} LR={c['caller_lr']}" for c in q.get("copies", [])) or "none"
        lines.append(f"| `{q['descriptor_0x08']}` | `{q['returned']}` | `{cs}` |")
    lines += ["", "## Static copy callsites", ""]
    if copy_callsites:
        lines.extend(f"- `{i['address']}` `{i['mnemonic']} {i['op_str']}`" for i in copy_callsites)
    else:
        lines.append("- No direct BL to the helper decoded in the bounded function; inspect indirect/veneer path.")
    lines += ["", "## Control disassembly 0x420D3C50..0x420D3D70", "", "```text"]
    lines.extend(f"{i['address']:>12}  {i['mnemonic']:<8} {i['op_str']}" for i in control)
    lines += ["```", "", "## Boundary", "",
              "Copy-request dependence can identify the +0x08 programming role, but does not prove MEDIUM/DG pixel order, signal source, coordinate scaling, clamp placement, rounding, or post-DG transfer.", ""]
    args.md_out.write_text("\n".join(lines))

    print(f"AUDIT1C_BASE_08={hx(base08)}")
    for q in probes:
        print("AUDIT1C_COPY_PROBE=" + q["descriptor_0x08"] + ";" + ";".join(
            f"dst={c['destination']},src={c['source']},bytes={c['bytes']},lr={c['caller_lr']}" for c in q.get("copies", [])))
    print("AUDIT1C_COPY_CALLSITES=" + ",".join(i["address"] for i in copy_callsites))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
