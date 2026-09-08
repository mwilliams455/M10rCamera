#!/usr/bin/env python3
"""v0.77: enumerate IMG-System code references to B2Y MMIO page 0x20020900.

Known owners from prior evidence:
  drv reached from record 0x0D (Y_BLEND) -> 0x420d4480
  drv reached from record 0x0C (YC_CONVERSION) -> 0x420d4570

This probe finds every literal reference to the page and dumps local code/string
context so field semantics can be recovered from independent readers/writers.
It does not infer semantics from register offsets alone.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
BASE=0x42000000
PAGE=0x20020900

def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def strings_near(data,off,r=0x500):
    lo=max(0,off-r);hi=min(len(data),off+r);out=[];i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=8:out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else:i+=1
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: m10r_b2y_20900_xrefs_v077.py <sections_dir>')
    root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    lits=[]
    for o in range(0,len(data)-3,4):
        if u32(data,o)==PAGE:lits.append(o)
    print(f'V077_PAGE=0x{PAGE:08x}|literal_occurrences={len(lits)}|offs={",".join(hex(x) for x in lits)}')
    refs=[]
    # Decode every halfword only around +-0x2000 of each literal, sufficient for Thumb PC-relative pools.
    for loff in lits:
        start=max(0,loff-0x2000);end=min(len(data)-4,loff+0x100)
        for off in range(start,end,2):
            ins=next(md.disasm(data[off:off+4],BASE+off,count=1),None)
            if ins is None:continue
            try:ops=list(ins.operands)
            except Exception:continue
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    po=(((ins.address+4)&~3)+int(op.mem.disp))-BASE
                    if po==loff:
                        refs.append((off,loff,ins.mnemonic,ins.op_str));break
    # dedupe
    refs=sorted(set(refs))
    print(f'V077_CODE_REF_COUNT={len(refs)}')
    for off,loff,m,ops in refs:
        print(f'\nV077_REF=code=0x{off:x}|va=0x{BASE+off:08x}|literal=0x{loff:x}|{m} {ops}')
        # dump compact +-0x60 code context from an aligned nearby point
        s=max(0,off-0x60);e=min(len(data),off+0xa0)
        for ins in md.disasm(data[s:e],BASE+s):
            io=ins.address-BASE
            if off-0x30<=io<=off+0x60:
                print(f'  V077_INS=0x{io:x}|{ins.mnemonic} {ins.op_str}')
        for so,text in strings_near(data,off,0x500):
            low=text.lower()
            if any(k in low for k in ('b2y','blend','conversion','clip','tone','ycc','chroma','luma','rgb')):
                print(f'  V077_ASCII=0x{so:x}|{text}')
    print('\nOVERALL_VERDICT=B2Y_20900_CODE_XREFS_ENUMERATED_WITHOUT_FIELD_NAME_GUESSES')
if __name__=='__main__':main()
