#!/usr/bin/env python3
"""v0.70: trace the common B2Y parameter lookup and enumerate calibration records.

This probe intentionally keeps two evidence streams separate:
  A) IMG-System code evidence for the common lookup at 0x421a0fc4 and its callers.
  B) data_calib_B2Y record-table evidence using the already-frozen parser layout.

It does not equate selector immediates with calibration record IDs unless the
code trace actually establishes that mapping.
"""
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import importlib.util
import struct
import sys
from collections import Counter, defaultdict

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

IMG_BASE = 0x42000000
LOOKUP_OFF = 0x1A0FC4
LOOKUP_VA = IMG_BASE + LOOKUP_OFF


def load_assets_module(repo_root: Path):
    p = repo_root / "tools" / "m10r_b2y_assets.py"
    spec = importlib.util.spec_from_file_location("m10r_b2y_assets_v070", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load m10r_b2y_assets.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def u32(data: bytes, off: int):
    return struct.unpack_from("<I", data, off)[0] if 0 <= off <= len(data) - 4 else None


def md_thumb():
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    return md


def litrefs(ins, data: bytes):
    out = []
    try:
        ops = list(ins.operands)
    except Exception:
        return out
    for op in ops:
        if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
            po = (((ins.address + 4) & ~3) + int(op.mem.disp)) - IMG_BASE
            if 0 <= po <= len(data) - 4:
                out.append((po, u32(data, po)))
    return out


def ascii_near(data: bytes, off: int, radius: int = 0x400):
    lo = max(0, off - radius)
    hi = min(len(data), off + radius)
    out = []
    i = lo
    while i < hi:
        if 32 <= data[i] < 127:
            j = i
            while j < hi and 32 <= data[j] < 127:
                j += 1
            if j - i >= 8:
                out.append((i, data[i:j].decode("ascii", "replace")))
            i = j
        else:
            i += 1
    return out


def function_ins(md, data: bytes, start: int, maxspan: int = 0x500):
    out = []
    for ins in md.disasm(data[start:min(len(data), start + maxspan)], IMG_BASE + start):
        out.append(ins)
        off = ins.address - IMG_BASE
        m = ins.mnemonic.lower()
        if off > start + 2 and ((m == "pop" and "pc" in ins.op_str.lower()) or (m == "bx" and "lr" in ins.op_str.lower())):
            break
    return out


def decode_mov_r1_imm(ins):
    m = ins.mnemonic.lower()
    if m not in ("mov", "movs", "mov.w", "movs.w"):
        return None
    try:
        ops = list(ins.operands)
    except Exception:
        return None
    if len(ops) != 2 or ops[1].type != ARM_OP_IMM:
        return None
    # Capstone op_str is the most robust register-name check here.
    if not ins.op_str.lower().replace(" ", "").startswith("r1,"):
        return None
    return int(ops[1].imm)


def trace_lookup(img: bytes):
    md = md_thumb()
    print("=== V070 A: COMMON LOOKUP BODY ===")
    print(f"V070_LOOKUP=off=0x{LOOKUP_OFF:x}|va=0x{LOOKUP_VA:08x}")
    for so, s in ascii_near(img, LOOKUP_OFF, 0x600):
        low = s.lower()
        if any(k in low for k in ("para", "calib", "table", "b2y", "tone", "blend", "clip", "select", "record")):
            print(f"V070_LOOKUP_NEAR_ASCII=0x{so:x}|{s}")
    body = function_ins(md, img, LOOKUP_OFF, 0x700)
    for ins in body:
        off = ins.address - IMG_BASE
        extra = []
        for po, v in litrefs(ins, img):
            extra.append(f"LIT=0x{po:x}->0x{v:08x}")
        if ins.mnemonic.lower().startswith("bl"):
            try:
                op = ins.operands[0]
                if op.type == ARM_OP_IMM:
                    extra.append(f"CALL=0x{op.imm:08x}|target_off=0x{op.imm-IMG_BASE:x}")
            except Exception:
                pass
        print(f"V070_LOOKUP_INS=0x{off:x}|{ins.mnemonic} {ins.op_str}" + (("|" + "|".join(extra)) if extra else ""))

    print("\n=== V070 A2: DIRECT CALLERS OF COMMON LOOKUP ===")
    callers = []
    # Decode whole image once. Thumb decoding from 0 can lose sync in data islands,
    # so scan every halfword and accept only direct BL targets equal to LOOKUP_VA.
    for off in range(0, len(img) - 4, 2):
        ins = next(md.disasm(img[off:off+4], IMG_BASE + off, count=1), None)
        if ins is None or not ins.mnemonic.lower().startswith("bl"):
            continue
        try:
            op = ins.operands[0]
        except Exception:
            continue
        if op.type != ARM_OP_IMM or int(op.imm) != LOOKUP_VA:
            continue
        context = []
        # Walk a fixed 32-byte window before the call and record explicit r1 immediates.
        for p in range(max(0, off - 32), off, 2):
            q = next(md.disasm(img[p:p+4], IMG_BASE+p, count=1), None)
            if q is None:
                continue
            imm = decode_mov_r1_imm(q)
            if imm is not None:
                context.append((p, imm, q.mnemonic, q.op_str))
        nearby = ascii_near(img, off, 0x160)
        names = [(so, s) for so, s in nearby if any(k in s.lower() for k in ("b2y", "tone", "blend", "clip", "conversion", "select"))]
        callers.append((off, context, names))
    print(f"V070_LOOKUP_CALLER_COUNT={len(callers)}")
    for off, context, names in callers:
        print(f"V070_LOOKUP_CALLER=off=0x{off:x}|va=0x{IMG_BASE+off:08x}")
        for p, imm, m, op in context[-4:]:
            print(f"  V070_R1_IMM=code=0x{p:x}|value={imm}|0x{imm:x}|{m} {op}")
        for so, s in names[:8]:
            print(f"  V070_CALLER_ASCII=0x{so:x}|{s}")


def record_manifest(repo_root: Path, b2y_path: Path):
    mod = load_assets_module(repo_root)
    data = b2y_path.read_bytes()
    records = mod.parse_records(data)
    print("\n=== V070 B: B2Y CALIBRATION RECORD MANIFEST ===")
    print(f"V070_B2Y_PATH={b2y_path}")
    print(f"V070_B2Y_SHA256={hashlib.sha256(data).hexdigest()}")
    print(f"V070_RECORD_COUNT={len(records)}")
    by_id = defaultdict(list)
    size_counts = Counter()
    for rec in records:
        blob = data[rec.payload_offset:rec.payload_offset+rec.size]
        by_id[rec.record_id].append(rec)
        size_counts[rec.size] += 1
        head = blob[:48].hex()
        nonzero = sum(b != 0 for b in blob[:min(len(blob), 256)])
        print(
            f"V070_RECORD=index={rec.index}|id=0x{rec.record_id:x}|id_dec={rec.record_id}|"
            f"rel=0x{rec.rel_offset:x}|size=0x{rec.size:x}|size_dec={rec.size}|"
            f"payload=0x{rec.payload_offset:x}|sha256={hashlib.sha256(blob).hexdigest()}|"
            f"head48={head}|nonzero_first256={nonzero}"
        )
    print("\nV070_ID_SUMMARY")
    for rid in sorted(by_id):
        rs = by_id[rid]
        print(f"V070_ID=id=0x{rid:x}|count={len(rs)}|indices={','.join(str(r.index) for r in rs)}|sizes={','.join(hex(r.size) for r in rs)}")
    print("V070_SIZE_SUMMARY=" + ",".join(f"0x{k:x}:{v}" for k, v in sorted(size_counts.items())))

    print("\n=== V070 B2: KNOWN-ASSET ANCHORS ===")
    for label, rid in (("TONE_TBL0", mod.ID_TONE_TBL0), ("DG_MAIN", mod.ID_DG_MAIN), ("DG_FL", mod.ID_DG_FL)):
        rs = by_id.get(rid, [])
        print(f"V070_KNOWN={label}|id=0x{rid:x}|count={len(rs)}|indices={','.join(str(r.index) for r in rs) or '-'}")

    # Candidate inventory only: records that are neither known nonlinear assets nor empty,
    # and that have enough bytes for the multi-field Y_BLEND driver structure.
    print("\n=== V070 B3: MULTI-FIELD CANDIDATE INVENTORY (NO ID ASSIGNMENT) ===")
    known = {mod.ID_TONE_TBL0, mod.ID_DG_MAIN, mod.ID_DG_FL}
    for rec in records:
        if rec.record_id in known or rec.size < 0x20:
            continue
        blob = data[rec.payload_offset:rec.payload_offset+rec.size]
        if not any(blob[:min(0x80, len(blob))]):
            continue
        vals16 = [struct.unpack_from("<H", blob, o)[0] for o in range(0, min(len(blob)-1, 0x20), 2)]
        vals8 = list(blob[:min(len(blob), 0x20)])
        print(
            f"V070_MULTIFIELD_CAND=index={rec.index}|id=0x{rec.record_id:x}|size=0x{rec.size:x}|"
            f"u8_0_31={','.join(str(x) for x in vals8)}|u16_0_30={','.join(str(x) for x in vals16)}"
        )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: m10r_b2y_lookup_manifest_v070.py <sections_dir> <repo_root>")
    sections = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])
    rows = list(csv.DictReader((sections / "sections.csv").open()))
    img_row = next((r for r in rows if r["name"] == "IMG-System"), None)
    if img_row is None:
        raise SystemExit("IMG-System section missing")
    b2y_row = next((r for r in rows if "data_calib_B2Y" in r["name"]), None)
    if b2y_row is None:
        raise SystemExit("data_calib_B2Y section missing")
    img = (sections / img_row["file"]).read_bytes()
    trace_lookup(img)
    record_manifest(repo_root, sections / b2y_row["file"])
    print("\nOVERALL_VERDICT=LOOKUP_CODE_AND_RECORD_MANIFEST_RECORDED_WITHOUT_FORCED_MAPPING")


if __name__ == "__main__":
    main()
