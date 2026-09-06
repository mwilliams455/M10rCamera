#!/usr/bin/env python3
"""M10-R v0.66 all-section ownership scan for B2Y page 0x20020780.

v0.63-v0.65 established that IMG-System touches 0x20020780 only inside the
large B2Y setup orchestrator.  This probe widens only the firmware-section
boundary: every extracted section is searched for exact literals
0x20020780/8c/90/94, and each literal is tested for local Thumb and ARM
PC-relative load xrefs.

Unknown-base sections are reported strictly as section + file offset.  A
synthetic disassembly base is used only to recover relative PC/literal geometry;
it is never presented as firmware runtime VA.
"""
from __future__ import annotations
from pathlib import Path
import csv, re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

TARGETS=(0x20020780,0x2002078c,0x20020790,0x20020794)


def u32(b,o):
    return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None


def read_rows(root):
    return list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))


def synthetic_base(idx):
    return 0x10000000 + int(idx)*0x01000000


def litrefs(ins,data,base):
    out=[]
    try: ops=list(ins.operands)
    except Exception: return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            # ARM literal uses PC+8; Thumb literal uses aligned PC+4. Capstone
            # mode is carried by caller, so test both candidate pool addresses
            # and retain the one that is in-range.
            disp=int(op.mem.disp)
            cands=[((ins.address+4)&~3)+disp,ins.address+8+disp]
            for va in cands:
                off=va-base
                if 0<=off<=len(data)-4:
                    out.append((off,u32(data,off)))
    # dedupe
    seen=set(); ans=[]
    for x in out:
        if x not in seen: seen.add(x); ans.append(x)
    return ans


def printable_near(data,off,r=0x500):
    lo=max(0,off-r); hi=min(len(data),off+r); b=data[lo:hi]
    out=[]; i=0
    while i<len(b):
        if 32<=b[i]<127:
            j=i
            while j<len(b) and 32<=b[j]<127: j+=1
            if j-i>=10:
                s=b[i:j].decode('ascii','replace')
                out.append((lo+i,s))
            i=j
        else: i+=1
    return out


def nearest_thumb_push(md,data,base,xoff,back=0x600):
    found=[]
    for off in range(max(0,xoff-back),xoff,2):
        ins=next(md.disasm(data[off:off+4],base+off,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower(): found.append(off)
    return found[-1] if found else None


def nearest_arm_push(md,data,base,xoff,back=0x800):
    # ARM compilers often use stmdb sp!, {...,lr}; Capstone alias may render push.
    found=[]
    start=max(0,xoff-back); start-=start%4
    for off in range(start,xoff,4):
        ins=next(md.disasm(data[off:off+4],base+off,count=1),None)
        if not ins: continue
        m=ins.mnemonic.lower(); op=ins.op_str.lower()
        if (m=='push' and 'lr' in op) or (m in ('stmdb','stmfd') and 'sp' in op and 'lr' in op):
            found.append(off)
    return found[-1] if found else None


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); rows=read_rows(root)
    print(f'V066_SECTIONS={len(rows)}')
    total_raw=0; total_xrefs=0; sections_with=[]
    for row in rows:
        data=(root/row['file']).read_bytes(); idx=int(row['index']); name=row['name']
        base=synthetic_base(idx)
        md_t=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md_t.detail=True
        md_a=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN); md_a.detail=True
        occurrences=[]
        for target in TARGETS:
            pat=struct.pack('<I',target); p=0
            while True:
                q=data.find(pat,p)
                if q<0: break
                occurrences.append((target,q)); p=q+1
        if not occurrences: continue
        sections_with.append((idx,name)); total_raw+=len(occurrences)
        image_base=row.get('image_base','0x00000000')
        print(f'\nV066_SECTION={idx}:{name}|size={len(data)}|image_base={image_base}|raw_literals={len(occurrences)}')
        for target,pool_off in occurrences:
            print(f'V066_RAW_LITERAL=section={idx}:{name}|target=0x{target:08x}|pool_off=0x{pool_off:x}')
            xrefs=[]
            # Literal reach for Thumb/ARM is bounded. Scan close to pool only.
            lo=max(0,pool_off-0x1400); hi=min(len(data)-2,pool_off+0x200)
            for off in range(lo,hi,2):
                ins=next(md_t.disasm(data[off:off+4],base+off,count=1),None)
                if ins and any(po==pool_off and v==target for po,v in litrefs(ins,data,base)):
                    xrefs.append(('THUMB',off,ins.mnemonic,ins.op_str))
            loa=max(0,pool_off-0x1400); loa-=loa%4; hia=min(len(data)-4,pool_off+0x200)
            for off in range(loa,hia,4):
                ins=next(md_a.disasm(data[off:off+4],base+off,count=1),None)
                if ins and any(po==pool_off and v==target for po,v in litrefs(ins,data,base)):
                    xrefs.append(('ARM',off,ins.mnemonic,ins.op_str))
            # dedupe mode/off/op
            seen=set(); ux=[]
            for x in xrefs:
                if x not in seen: seen.add(x); ux.append(x)
            print(f'V066_LITERAL_XREFS=section={idx}:{name}|target=0x{target:08x}|pool_off=0x{pool_off:x}|count={len(ux)}')
            total_xrefs+=len(ux)
            for mode,off,mn,ops in ux:
                owner=nearest_thumb_push(md_t,data,base,off) if mode=='THUMB' else nearest_arm_push(md_a,data,base,off)
                print(f'  V066_XREF=section={idx}:{name}|mode={mode}|code_off=0x{off:x}|owner_off={"-" if owner is None else f"0x{owner:x}"}|{mn} {ops}')
                for so,s in printable_near(data,owner if owner is not None else off,r=0x500):
                    low=s.lower()
                    if any(k in low for k in ('b2y','rgb','clip','clamp','range','white','black','level','limit','gain','tone','image','img_')):
                        print(f'    V066_NEAR_ASCII=off=0x{so:x}|{s}')

    print('\n=== V066 SUMMARY ===')
    print(f'V066_SECTIONS_WITH_RAW_TARGETS={len(sections_with)}|'+(','.join(f'{i}:{n}' for i,n in sections_with) or '-'))
    print(f'V066_RAW_TARGET_OCCURRENCES={total_raw}')
    print(f'V066_PROVEN_LOCAL_XREFS={total_xrefs}')
    # The question is whether another firmware component owns the sub-block.
    # Raw constants without code xrefs do not count as ownership.
    if total_xrefs==0:
        print('OVERALL_VERDICT=NO_FIRMWARE_CODE_OWNER_RECOVERED')
    elif len(sections_with)==1 and sections_with[0][1]=='IMG-System':
        print('OVERALL_VERDICT=PAGE20780_OWNERSHIP_REMAINS_IMG_SYSTEM_ONLY')
    else:
        print('OVERALL_VERDICT=PAGE20780_CROSS_SECTION_OWNERSHIP_PRESENT_NEEDS_CLASSIFICATION')

if __name__=='__main__': main()
