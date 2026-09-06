#!/usr/bin/env python3
"""M10-R v0.60 B2Y WB-output clamp/ceiling ownership probe.

Question: does firmware software around the already-proven B2Y driver/programmer
explicitly own either the DNG WhiteLevel 15000 (0x3a98) or the natural 14-bit
maximum 16383 (0x3fff)?

This is intentionally bounded.  It uses the same two independent IMG-System
string anchors as v0.56 to recover the archive VA/file mapping, then examines
only the proven B2Y driver and central/programmer regions.  Hits elsewhere in
the firmware are irrelevant to this verdict.
"""
from __future__ import annotations

from pathlib import Path
import re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32

TARGETS = {
    0x00003A98: "DNG_WHITE_15000",
    0x00003FFF: "MAX14_16383",
}
# Extra masks are evidence of a 14-bit software boundary if explicitly consumed.
MASK_TARGETS = {
    0xFFFFC000: "CLEAR_LOW14",
    0x00003FFF: "LOW14_MASK",
}
REGIONS = [
    ("B2Y_DRIVER", 0x420D0000, 0x420D6000),
    ("B2Y_CENTRAL_PROGRAMMER", 0x42150000, 0x42156000),
]


def literal_ref(ins, data: bytes, bias: int):
    try:
        ops = list(ins.operands)
    except Exception:
        return []
    out=[]
    for op in ops:
        if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
            pool_va = ((ins.address + 4) & ~3) + int(op.mem.disp)
            val = u32(data, pool_va - bias)
            if val is not None:
                out.append((pool_va,val))
    return out


def immediate_values(ins):
    vals=[]
    try:
        for op in ins.operands:
            if op.type == ARM_OP_IMM:
                vals.append(int(op.imm) & 0xffffffff)
    except Exception:
        pass
    # Capstone occasionally omits detail for aliases; keep a conservative text
    # fallback only for exact hexadecimal/decimal target spellings.
    s=ins.op_str.lower()
    for tok in re.findall(r'#(?:0x[0-9a-f]+|\d+)',s):
        try: vals.append(int(tok[1:],0)&0xffffffff)
        except ValueError: pass
    return vals


def context(md, data, bias, va, before=12, after=28):
    start=max(0,va-bias-before)
    base=bias+start
    return [f"{i.address:08x}: {i.mnemonic:<8} {i.op_str}".rstrip()
            for i in md.disasm(data[start:start+before+after],base)]


def main():
    if len(sys.argv)!=2:
        raise SystemExit(f"usage: {sys.argv[0]} sections_dir")
    root=Path(sys.argv[1])
    imgs=get_img_section(root)
    print(f"V060_IMG_SECTIONS={len(imgs)}")
    if len(imgs)!=1:
        print("OVERALL_VERDICT=UNRESOLVED_IMG_SECTION"); return 0
    row,data=imgs[0]
    ev,bias=derive_mapping(data)
    for va,needle,poss in ev:
        print(f"V060_MAP_ANCHOR=0x{va:08x}|hits={len(poss)}|offsets={','.join(hex(x) for x in poss) or '-'}")
    if bias is None:
        print("OVERALL_VERDICT=UNRESOLVED_MAPPING"); return 0
    print(f"V060_MAP_BIAS=0x{bias:08x}")
    print(f"V060_SECTION={row['index']}:{row['name']}|bytes={len(data)}")

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    hits=[]
    literal_blob_hits=[]

    # Raw 32-bit literal occurrences are recorded, but only become consumer
    # evidence when a decoded PC-relative load in a bounded region references one.
    for value,label in TARGETS.items():
        pat=struct.pack('<I',value)
        start=0
        while True:
            p=data.find(pat,start)
            if p<0: break
            va=bias+p
            literal_blob_hits.append((label,va))
            start=p+1
    for label,va in literal_blob_hits:
        inreg=[name for name,a,b in REGIONS if a<=va<b]
        if inreg:
            print(f"V060_RAW_LITERAL_IN_REGION={label}|0x{va:08x}|{','.join(inreg)}")

    for rname,start_va,end_va in REGIONS:
        a=max(0,start_va-bias); b=min(len(data),end_va-bias)
        print(f"V060_REGION={rname}|0x{start_va:08x}-0x{end_va:08x}|file=0x{a:x}-0x{b:x}")
        if a>=b: continue
        # Candidate-seeded Thumb decode: one instruction from every halfword.
        # This avoids losing xrefs due to mixed literal pools while keeping the
        # verdict restricted to exact target-valued operands/references.
        for off in range(a,b-2,2):
            va=bias+off
            ins=next(md.disasm(data[off:off+4],va,count=1),None)
            if ins is None: continue
            for imm in immediate_values(ins):
                if imm in TARGETS or imm in MASK_TARGETS:
                    label=TARGETS.get(imm,MASK_TARGETS.get(imm))
                    hits.append((rname,va,"IMMEDIATE",imm,label,ins.mnemonic,ins.op_str))
            for pool,val in literal_ref(ins,data,bias):
                if val in TARGETS or val in MASK_TARGETS:
                    label=TARGETS.get(val,MASK_TARGETS.get(val))
                    hits.append((rname,va,"LITERAL_XREF",val,label,ins.mnemonic,ins.op_str,pool))

    # Deduplicate aliases/text fallback.
    uniq=[]; seen=set()
    for h in hits:
        key=(h[0],h[1],h[2],h[3],h[5],h[6],h[7] if len(h)>7 else None)
        if key not in seen:
            seen.add(key); uniq.append(h)
    hits=uniq

    print(f"V060_EXACT_BOUNDED_HITS={len(hits)}")
    for h in hits:
        rname,va,kind,val,label,mn,ops,*tail=h
        pool=f"|pool=0x{tail[0]:08x}" if tail else ""
        print(f"V060_HIT={rname}|0x{va:08x}|{kind}|{label}|0x{val:08x}|{mn} {ops}{pool}")
        for line in context(md,data,bias,va):
            print("  "+line)

    white=[h for h in hits if h[3]==0x3a98]
    max14=[h for h in hits if h[3] in (0x3fff,0xffffc000)]
    print(f"V060_15000_HITS={len(white)}")
    print(f"V060_14BIT_BOUNDARY_HITS={len(max14)}")
    print(f"V060_RAW_15000_OCCURRENCES_IMG_SYSTEM={sum(1 for l,_ in literal_blob_hits if l=='DNG_WHITE_15000')}")
    print(f"V060_RAW_3FFF_OCCURRENCES_IMG_SYSTEM={sum(1 for l,_ in literal_blob_hits if l=='MAX14_16383')}")

    # A bounded exact hit is only software ownership evidence, not proof that the
    # hardware pixel datapath clips there. Absence likewise means hardware-internal.
    if white and not max14:
        print("OVERALL_VERDICT=EXPLICIT_15000_SOFTWARE_BOUNDARY_CANDIDATE")
    elif max14 and not white:
        print("OVERALL_VERDICT=EXPLICIT_14BIT_SOFTWARE_BOUNDARY_CANDIDATE")
    elif white and max14:
        print("OVERALL_VERDICT=BOTH_BOUNDARIES_PRESENT_NEEDS_DATAFLOW_CLASSIFICATION")
    else:
        print("OVERALL_VERDICT=NO_EXPLICIT_BOUND_IN_BOUNDED_B2Y_SOFTWARE")

if __name__=='__main__':
    main()
