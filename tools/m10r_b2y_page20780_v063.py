#!/usr/bin/env python3
"""M10-R v0.63 ownership probe for B2Y MMIO page 0x20020780.

The v0.62 cluster nearest the proven WB setter writes 0x3fff into fields on
0x20020780.  This probe resolves all literal pools containing that exact MMIO
base, finds real Thumb PC-relative xrefs to those pools, groups xrefs by nearby
function prologue, and inventories function calls/strings/0x3fff usage.

A shared orchestration function is not enough to infer WB semantics; page-level
ownership must be classified independently from the proven WB page 0x20020080.
"""
from __future__ import annotations
from pathlib import Path
import struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

PAGE=0x20020780
WB_PAGE=0x20020080
WB_SETTER=0x420D4380
TARGET14=0x00003fff


def litref(ins,data,bias):
    out=[]
    try: ops=list(ins.operands)
    except Exception: return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            p=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(data,p-bias)
            if v is not None: out.append((p,v))
    return out


def branch_target(ins):
    if ins.mnemonic.lower() not in ('bl','blx'): return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def nearest_push(md,data,bias,x,back=0x700):
    found=[]
    for va in range(max(bias,x-back),x,2):
        off=va-bias
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower(): found.append(va)
    return found[-1] if found else None


def decode_function(md,data,bias,st,maxlen=0xa00):
    seq=[]; off=st-bias
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        seq.append(ins)
        m=ins.mnemonic.lower(); op=ins.op_str.lower()
        if (m=='pop' and 'pc' in op) or (m=='bx' and op.strip()=='lr'):
            return seq,ins.address+ins.size
    return seq,(seq[-1].address+seq[-1].size if seq else st)


def ascii_near(data,bias,st,r=0x700):
    lo=max(0,st-bias-r); hi=min(len(data),st-bias+r)
    b=data[lo:hi]; out=[]; i=0
    while i<len(b):
        if 32<=b[i]<127:
            j=i
            while j<len(b) and 32<=b[j]<127: j+=1
            if j-i>=10: out.append((bias+lo+i,b[i:j].decode('ascii','replace')))
            i=j
        else: i+=1
    return out


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    imgs=get_img_section(Path(sys.argv[1]))
    print(f'V063_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAP'); return
    print(f'V063_MAP_BIAS=0x{bias:08x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    # Find every exact raw pool occurrence in IMG-System.
    pat=struct.pack('<I',PAGE); pools=[]; pos=0
    while True:
        p=data.find(pat,pos)
        if p<0: break
        pools.append(bias+p); pos=p+1
    print(f'V063_RAW_PAGE_POOLS={len(pools)}|'+(','.join(f'0x{x:08x}' for x in pools) or '-'))

    # Find actual Thumb literal-load xrefs within the maximum Thumb LDR literal
    # reach around each pool. Scan a slightly wider window conservatively.
    xrefs=[]
    for pool in pools:
        lo=max(bias,pool-0x1200); hi=min(bias+len(data),pool+0x100)
        for va in range(lo,hi,2):
            off=va-bias
            ins=next(md.disasm(data[off:off+4],va,count=1),None)
            if not ins: continue
            for p,v in litref(ins,data,bias):
                if p==pool and v==PAGE:
                    xrefs.append((va,pool,ins))
    # dedupe
    tmp={x[0]:(x[1],x[2]) for x in xrefs}; xrefs=[(va,p,i) for va,(p,i) in sorted(tmp.items())]
    print(f'V063_CODE_XREFS={len(xrefs)}')
    owners={}
    for va,pool,ins in xrefs:
        st=nearest_push(md,data,bias,va)
        print(f'V063_XREF=0x{va:08x}|pool=0x{pool:08x}|{ins.mnemonic} {ins.op_str}|owner={"-" if st is None else f"0x{st:08x}"}')
        if st is not None: owners.setdefault(st,[]).append(va)

    print(f'V063_OWNER_FUNCTIONS={len(owners)}')
    named_page_context=0; wb_related=0; target14_owners=0
    for st,xs in sorted(owners.items()):
        seq,en=decode_function(md,data,bias,st)
        calls=[]; lits=[]
        print(f'\n=== OWNER 0x{st:08x}-0x{en:08x} page_xrefs={",".join(hex(x) for x in xs)} ===')
        for ins in seq:
            bt=branch_target(ins)
            if bt is not None: calls.append((ins.address,bt))
            rr=litref(ins,data,bias); tail=''
            if rr:
                ps=[]
                for p,v in rr:
                    lits.append((ins.address,p,v))
                    cls='PAGE20780' if v==PAGE else 'WB_PAGE' if v==WB_PAGE else 'MMIO' if 0x20000000<=v<0x30000000 else 'RAM' if 0x40000000<=v<0x50000000 else 'VALUE'
                    s=read_cstr_va(data,bias,v) if 0x42000000<=v<0x43000000 else None
                    ps.append(f'pool=0x{p:08x}->0x{v:08x}:{cls}:str={s!r}')
                tail=' ; '+' ; '.join(ps)
            print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
        strings=ascii_near(data,bias,st)
        for va,s in strings: print(f'V063_NEAR_ASCII=owner=0x{st:08x}|0x{va:08x}|{s}')
        has_wb_call=any(t==WB_SETTER for _,t in calls)
        has_wb_page=any(v==WB_PAGE for _,_,v in lits)
        has14=any(v in (TARGET14,0x3fff0000) for _,_,v in lits)
        names=[s for _,s in strings if 'b2y' in s.lower() or 'img' in s.lower()]
        if names: named_page_context+=1
        if has_wb_call or has_wb_page: wb_related+=1
        if has14: target14_owners+=1
        print(f'V063_OWNER_SUMMARY=start=0x{st:08x}|end=0x{en:08x}|has_wb_call={int(has_wb_call)}|has_wb_page={int(has_wb_page)}|has_3fff={int(has14)}|named_context={int(bool(names))}')
        print('V063_CALLS='+(','.join(f'0x{a:08x}->0x{t:08x}' for a,t in calls) or '-'))

    print(f'V063_OWNERS_NAMED_CONTEXT={named_page_context}')
    print(f'V063_OWNERS_WB_RELATED={wb_related}')
    print(f'V063_OWNERS_WITH_3FFF={target14_owners}')
    # Page semantics remain distinct from WB unless a page owner itself is a
    # named WB setter or references WB MMIO. A shared top-level configurator is
    # explicitly insufficient to merge the pages.
    if not xrefs:
        print('OVERALL_VERDICT=NO_CODE_OWNER_FOR_20020780')
    elif wb_related==0:
        print('OVERALL_VERDICT=PAGE_20020780_DISTINCT_FROM_PROVEN_WB_PAGE')
    else:
        print('OVERALL_VERDICT=PAGE_20020780_SHARED_ORCHESTRATOR_NEEDS_SUBBLOCK_CLASSIFICATION')

if __name__=='__main__': main()
