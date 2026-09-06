#!/usr/bin/env python3
"""M10-R v0.61 classify explicit 0x3fff use in proven B2Y software.

v0.60 proved explicit 14-bit-valued consumers in bounded B2Y code but did not
establish their semantics.  This probe focuses on the two driver literal pools
at 0x420d3428 and 0x420d35d8.  It recovers enclosing Thumb functions, all
PC-relative literal values, MMIO ownership, nearby strings, and direct BL
callers.  It does not infer a pixel clamp from the numeric value alone.
"""
from __future__ import annotations
from pathlib import Path
import struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

POOLS=[0x420D3428,0x420D35D8]
SEARCH_START=0x420D3200
SEARCH_END=0x420D3620
MMIO_MIN=0x20000000
MMIO_MAX=0x30000000


def litrefs(ins,data,bias):
    out=[]
    try: ops=list(ins.operands)
    except Exception: return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            p=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(data,p-bias)
            if v is not None: out.append((p,v))
    return out


def branch_imm(ins):
    if not ins.mnemonic.lower().startswith('b'): return None
    try:
        ops=list(ins.operands)
        for op in ops:
            if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def plausible_functions(md,data,bias):
    a=SEARCH_START-bias; b=SEARCH_END-bias
    starts=[]
    for off in range(a,b,2):
        va=bias+off
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():
            starts.append(va)
    funcs=[]
    for st in starts:
        off=st-bias; seq=[]; end=None
        for ins in md.disasm(data[off: min(len(data),off+0x500)],st):
            seq.append(ins)
            m=ins.mnemonic.lower(); op=ins.op_str.lower()
            if (m=='pop' and 'pc' in op) or m=='bx' and op.strip()=='lr':
                end=ins.address+ins.size; break
            # avoid swallowing obvious next function after a return-less branch
            if len(seq)>300: break
        if end: funcs.append((st,end,seq))
    return funcs


def direct_callers(md,data,bias,target):
    # Candidate-seeded halfword scan of IMG-System; report only exact BL/BLX
    # immediate targets. This is slow but bounded to one 9.9MB image and exact.
    out=[]
    for off in range(0,len(data)-4,2):
        va=bias+off
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if not ins or ins.mnemonic.lower() not in ('bl','blx'): continue
        t=branch_imm(ins)
        if t==target: out.append(va)
    return out


def ascii_around(data,bias,va,radius=0x300):
    lo=max(0,va-bias-radius); hi=min(len(data),va-bias+radius)
    blob=data[lo:hi]
    hits=[]
    i=0
    while i<len(blob):
        if 32<=blob[i]<127:
            j=i
            while j<len(blob) and 32<=blob[j]<127: j+=1
            if j-i>=8:
                s=blob[i:j].decode('ascii','replace')
                hits.append((bias+lo+i,s))
            i=j
        else: i+=1
    return hits


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    imgs=get_img_section(Path(sys.argv[1]))
    print(f'V061_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG_SECTION'); return
    row,data=imgs[0]
    ev,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAPPING'); return
    print(f'V061_MAP_BIAS=0x{bias:08x}')
    print(f"V061_SECTION={row['index']}:{row['name']}")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    funcs=plausible_functions(md,data,bias)
    print(f'V061_PLAUSIBLE_FUNCTIONS={len(funcs)}')

    selected=[]
    for pool in POOLS:
        # Find every xref to this literal pool in the search region.
        xrefs=[]
        for off in range(SEARCH_START-bias,SEARCH_END-bias,2):
            va=bias+off
            ins=next(md.disasm(data[off:off+4],va,count=1),None)
            if not ins: continue
            for p,v in litrefs(ins,data,bias):
                if p==pool: xrefs.append((va,v,ins))
        print(f'V061_POOL=0x{pool:08x}|value=0x{u32(data,pool-bias) or 0:08x}|xrefs={len(xrefs)}')
        for va,v,ins in xrefs:
            print(f'V061_POOL_XREF=0x{va:08x}|0x{v:08x}|{ins.mnemonic} {ins.op_str}')
            owners=[f for f in funcs if f[0]<=va<f[1]]
            for f in owners:
                if f not in selected: selected.append(f)
                print(f'V061_XREF_OWNER=0x{va:08x}|function=0x{f[0]:08x}-0x{f[1]:08x}')

    # Prefer shortest enclosing function if candidate starts overlap.
    uniq={f[0]:f for f in selected}
    selected=sorted(uniq.values(),key=lambda x:x[0])
    print(f'V061_SELECTED_FUNCTIONS={len(selected)}')
    any_mmio=False
    for st,en,seq in selected:
        print(f'\n=== FUNCTION 0x{st:08x}-0x{en:08x} ===')
        callers=direct_callers(md,data,bias,st)
        print(f'V061_FUNCTION=0x{st:08x}|end=0x{en:08x}|size={en-st}|callers={len(callers)}')
        print('V061_CALLERS='+(','.join(f'0x{x:08x}' for x in callers) or '-'))
        literals=[]
        for ins in seq:
            refs=litrefs(ins,data,bias)
            extra=''
            if refs:
                parts=[]
                for p,v in refs:
                    parts.append(f'pool=0x{p:08x}->0x{v:08x}')
                    literals.append((ins.address,p,v))
                extra=' ; '+';'.join(parts)
            print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{extra}'.rstrip())
        # Unique literal inventory with classifications.
        seen=set()
        for iva,p,v in literals:
            key=(p,v)
            if key in seen: continue
            seen.add(key)
            cls='MMIO' if MMIO_MIN<=v<MMIO_MAX else 'RAM' if 0x40000000<=v<0x50000000 else 'VALUE'
            if cls=='MMIO': any_mmio=True
            s=read_cstr_va(data,bias,v) if 0x42000000<=v<0x43000000 else None
            print(f'V061_LITERAL=function=0x{st:08x}|pool=0x{p:08x}|value=0x{v:08x}|class={cls}|string={s!r}')
        for sva,s in ascii_around(data,bias,st):
            print(f'V061_NEAR_ASCII=function=0x{st:08x}|0x{sva:08x}|{s}')

    # Also report direct callers of the known WB setter for relational context.
    wbcall=direct_callers(md,data,bias,0x420D4380)
    print(f'V061_WB_SETTER_CALLERS={len(wbcall)}|'+(','.join(f'0x{x:08x}' for x in wbcall) or '-'))

    if not selected:
        print('OVERALL_VERDICT=UNRESOLVED_NO_FUNCTION_OWNER')
    elif any_mmio:
        print('OVERALL_VERDICT=14BIT_FIELDS_HAVE_EXPLICIT_B2Y_MMIO_OWNERSHIP_NEEDS_FIELD_SEMANTICS')
    else:
        print('OVERALL_VERDICT=14BIT_FIELDS_NOT_PROVEN_PIXEL_MMIO')

if __name__=='__main__': main()
