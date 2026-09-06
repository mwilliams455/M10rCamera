#!/usr/bin/env python3
"""M10-R v0.56 surgical canonical-WB consumer probe.

Proven archived anchor: central selector 0x42154F84 loads the B2Y runtime
halfwords local +0x04/+0x06/+0x08 into r0/r1/r2 and calls 0x420D4380.

The IMG-System section table has image_base=0, so archived 0x420... labels are
mapped back to raw section offsets only after TWO independent exact string
anchors from the preserved research agree on the same address-minus-offset
bias.  No guessed 0x42000000 raw base is accepted.

No renderer/application files are touched.
"""
from __future__ import annotations

from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC

TARGET = 0x420D4380
WINDOW = 0x280
STRING_ANCHORS = [
    (0x420A40AF, b'Gain R: %4.f | G: %4.f | B: %4.f'),
    (0x421E9CCD, b'ca9_cm_ColorManagementFinished'),
]


def get_img_section(root: Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    hits=[]
    for row in rows:
        if row['name']=='IMG-System':
            hits.append((row,(root/row['file']).read_bytes()))
    return hits


def derive_mapping(data: bytes):
    evidence=[]
    for va,needle in STRING_ANCHORS:
        poss=[]; start=0
        while True:
            p=data.find(needle,start)
            if p<0: break
            poss.append(p); start=p+1
        evidence.append((va,needle,poss))
    if any(len(x[2])!=1 for x in evidence):
        return evidence,None
    biases=[va-poss[0] for va,_,poss in evidence]
    return evidence,(biases[0] if len(set(biases))==1 else None)


def rn(md,rid): return md.reg_name(rid) if rid else None

def op_regs(ins,md):
    try:
        rd,wr=ins.regs_access()
        return ({rn(md,x) for x in rd if rn(md,x)}, {rn(md,x) for x in wr if rn(md,x)})
    except Exception:
        return set(),set()


def literal_value(ins,op,data,bias):
    if op.type!=ARM_OP_MEM or op.mem.base!=ARM_REG_PC: return None
    va=((ins.address+4)&~3)+int(op.mem.disp)
    off=va-bias
    if 0<=off<=len(data)-4:
        return va,struct.unpack_from('<I',data,off)[0]
    return None


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); imgs=get_img_section(root)
    print('V056_ANCHOR=0x42154f84:local+04/+06/+08->r0/r1/r2->0x420d4380')
    print('V056_CALLEE=0x420d4380')
    print(f'V056_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG_SECTION'); return 0
    row,data=imgs[0]
    print(f"V056_SECTION={row['index']}:{row['name']}")
    print(f"V056_SECTION_TABLE_BASE={row['image_base']}")
    evidence,bias=derive_mapping(data)
    for va,needle,poss in evidence:
        print(f"V056_MAP_ANCHOR=0x{va:08x}|{needle.decode('ascii')}|hits={len(poss)}|offsets={','.join(hex(x) for x in poss) or '-'}")
        for p in poss:
            print(f'V056_MAP_BIAS_CANDIDATE=0x{va-p:08x}')
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_ARCHIVE_TO_FILE_MAPPING'); return 0
    off=TARGET-bias
    print(f'V056_MAP_BIAS=0x{bias:08x}')
    print(f'V056_CALLEE_FILE_OFFSET=0x{off:x}')
    if not (0<=off<len(data)):
        print('OVERALL_VERDICT=UNRESOLVED_CALLEE_OFFSET'); return 0
    print(f'V056_CALLEE_BYTES={data[off:off+32].hex()}')

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    code=data[off:off+WINDOW]
    taint={'r0':{'R'},'r1':{'G'},'r2':{'B'}}
    stores=[]; calls=[]; literals=[]; taint_ops=[]; insn_count=0; return_seen=False
    print('=== V056_CALLEE_BODY ===')
    for ins in md.disasm(code,TARGET):
        insn_count+=1
        print(f'{ins.address:08x}: {ins.mnemonic:<10} {ins.op_str}'.rstrip())
        try: ops=list(ins.operands)
        except Exception: ops=[]
        reads,writes=op_regs(ins,md)
        used=set()
        for r in reads: used|=taint.get(r,set())
        for op in ops:
            lv=literal_value(ins,op,data,bias)
            if lv:
                va,val=lv; literals.append((ins.address,va,val))
                print(f'  V056_LITERAL@0x{ins.address:08x}=0x{val:08x} pool=0x{va:08x}')
        mn=ins.mnemonic.lower()
        if used:
            taint_ops.append((ins.address,mn,ins.op_str,sorted(used)))
            print(f"  V056_TAINT_USE labels={','.join(sorted(used))}")
        if mn.startswith('str') and ops:
            labs=set()
            if ops[0].type==ARM_OP_REG: labs|=taint.get(rn(md,ops[0].reg),set())
            stores.append((ins.address,ins.op_str,sorted(labs)))
            print(f"  V056_STORE labels={','.join(sorted(labs)) or '-'} op='{ins.op_str}'")
        if mn in ('bl','blx'):
            argmap={r:sorted(taint.get(r,set())) for r in ('r0','r1','r2','r3') if taint.get(r)}
            calls.append((ins.address,ins.op_str,argmap)); print(f'  V056_CALL_TAINT={argmap}')
            for r in ('r0','r1','r2','r3','r12','lr'): taint.pop(r,None)
        else:
            labs=set()
            for r in reads: labs|=taint.get(r,set())
            for w in writes: taint.pop(w,None)
            if labs and len(writes)==1 and not mn.startswith(('cmp','tst','str','push')):
                taint[next(iter(writes))]=set(labs)
        if mn=='bx' and 'lr' in ins.op_str: return_seen=True; break
        if mn=='pop' and 'pc' in ins.op_str: return_seen=True; break
        if insn_count>=220: break

    print('=== V056_SUMMARY ===')
    print(f'V056_INSNS={insn_count}'); print(f'V056_RETURN_SEEN={int(return_seen)}')
    print(f'V056_TAINT_OPS={len(taint_ops)}'); print(f'V056_STORES={len(stores)}')
    print(f'V056_CALLS={len(calls)}'); print(f'V056_LITERALS={len(literals)}')
    ls=[x for x in stores if x[2]]; lc=[x for x in calls if x[2]]
    print(f'V056_TAINTED_STORES={len(ls)}'); print(f'V056_TAINTED_CALLS={len(lc)}')
    for a,op,labs in ls: print(f"V056_TAINTED_STORE=0x{a:08x}|{','.join(labs)}|{op}")
    for a,op,args in lc: print(f'V056_TAINTED_CALL=0x{a:08x}|{op}|{args}')
    if insn_count==0: print('OVERALL_VERDICT=UNRESOLVED_NO_DECODE')
    elif ls: print('OVERALL_VERDICT=CANONICAL_WB_REACHES_STORE_NEEDS_TARGET_CLASSIFICATION')
    elif lc: print('OVERALL_VERDICT=CANONICAL_WB_ESCAPES_TO_CALLEE_UNRESOLVED')
    elif return_seen: print('OVERALL_VERDICT=NO_OUTWARD_CANONICAL_WB_CONSUMER_IN_HELPER')
    else: print('OVERALL_VERDICT=UNRESOLVED')

if __name__=='__main__': main()
