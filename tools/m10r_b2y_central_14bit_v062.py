#!/usr/bin/env python3
"""M10-R v0.62 classify central/programmer 0x3fff consumers.

v0.60 found nine exact 0x3fff literal consumers in the bounded central B2Y
programmer region.  This probe groups those xrefs by enclosing Thumb function,
then inventories each owner's literal/MMIO references, calls, nearby strings,
and relationship to the proven WB setter 0x420d4380.

The goal is semantic exclusion: distinguish WB/pixel-headroom fields from
operation-mode, lookup/configuration, geometry, or unrelated control state.
"""
from __future__ import annotations
from pathlib import Path
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

WB_SETTER=0x420D4380
WB_MMIO=0x20020080
OPMODE_MMIO=0x20021080
XREFS=[0x421509c0,0x421509e4,0x42150c40,0x42150cce,0x42150d90,
       0x42150ee2,0x421510a2,0x42155004,0x42155020,0x4215503c]
REGION_START=0x42150800
REGION_END=0x42155380


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


def branch_target(ins):
    if ins.mnemonic.lower() not in ('bl','blx','b','b.w'): return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def nearest_push(md,data,bias,x,back=0x500):
    found=[]
    for va in range(max(REGION_START,x-back),x,2):
        off=va-bias
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():
            found.append(va)
    return found[-1] if found else None


def decode_function(md,data,bias,st,maxlen=0x900):
    seq=[]; off=st-bias
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        seq.append(ins)
        m=ins.mnemonic.lower(); op=ins.op_str.lower()
        if (m=='pop' and 'pc' in op) or (m=='bx' and op.strip()=='lr'):
            return seq,ins.address+ins.size
    return seq,(seq[-1].address+seq[-1].size if seq else st)


def ascii_near(data,bias,st,r=0x500):
    lo=max(0,st-bias-r); hi=min(len(data),st-bias+r)
    b=data[lo:hi]; out=[]; i=0
    while i<len(b):
        if 32<=b[i]<127:
            j=i
            while j<len(b) and 32<=b[j]<127: j+=1
            if j-i>=9: out.append((bias+lo+i,b[i:j].decode('ascii','replace')))
            i=j
        else: i+=1
    return out


def central_callers(md,data,bias,target):
    out=[]
    a=REGION_START-bias; b=REGION_END-bias
    for off in range(a,b-4,2):
        va=bias+off
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if not ins or ins.mnemonic.lower() not in ('bl','blx'): continue
        if branch_target(ins)==target: out.append(va)
    return out


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    imgs=get_img_section(Path(sys.argv[1]))
    print(f'V062_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAP'); return
    print(f'V062_MAP_BIAS=0x{bias:08x}')
    print(f"V062_SECTION={row['index']}:{row['name']}")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    owners={}
    for x in XREFS:
        st=nearest_push(md,data,bias,x)
        print(f'V062_XREF=0x{x:08x}|owner_start={"-" if st is None else f"0x{st:08x}"}')
        if st is not None: owners.setdefault(st,[]).append(x)

    print(f'V062_OWNER_FUNCTIONS={len(owners)}')
    wb_owner_hits=0; wb_mmio_hits=0; opmode_hits=0; unknown14=[]
    for st,xs in sorted(owners.items()):
        seq,en=decode_function(md,data,bias,st)
        calls=[]; lits=[]
        print(f'\n=== OWNER 0x{st:08x}-0x{en:08x} xrefs={",".join(hex(x) for x in xs)} ===')
        for ins in seq:
            bt=branch_target(ins)
            if ins.mnemonic.lower() in ('bl','blx') and bt is not None: calls.append((ins.address,bt))
            rr=litrefs(ins,data,bias); tail=''
            if rr:
                ps=[]
                for p,v in rr:
                    lits.append((ins.address,p,v))
                    cls='WB_MMIO' if v==WB_MMIO else 'OPMODE_MMIO' if v==OPMODE_MMIO else 'MMIO' if 0x20000000<=v<0x30000000 else 'RAM' if 0x40000000<=v<0x50000000 else 'VALUE'
                    s=read_cstr_va(data,bias,v) if 0x42000000<=v<0x43000000 else None
                    ps.append(f'pool=0x{p:08x}->0x{v:08x}:{cls}:str={s!r}')
                tail=' ; '+' ; '.join(ps)
            print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
        ctargets=[t for _,t in calls]
        has_wb=WB_SETTER in ctargets
        has_wb_mmio=any(v==WB_MMIO for _,_,v in lits)
        has_opmode=any(v==OPMODE_MMIO for _,_,v in lits)
        if has_wb: wb_owner_hits+=1
        if has_wb_mmio: wb_mmio_hits+=1
        if has_opmode: opmode_hits+=1
        callers=central_callers(md,data,bias,st)
        print(f'V062_OWNER_SUMMARY=start=0x{st:08x}|end=0x{en:08x}|xrefs={len(xs)}|calls_wb_setter={int(has_wb)}|wb_mmio_literal={int(has_wb_mmio)}|opmode_mmio_literal={int(has_opmode)}|central_callers={len(callers)}')
        print('V062_CALLS='+(','.join(f'0x{a:08x}->0x{t:08x}' for a,t in calls) or '-'))
        print('V062_CALLERS='+(','.join(f'0x{x:08x}' for x in callers) or '-'))
        seen=set()
        for _,p,v in lits:
            if (p,v) in seen: continue
            seen.add((p,v))
            print(f'V062_LITERAL=owner=0x{st:08x}|pool=0x{p:08x}|value=0x{v:08x}')
        for va,s in ascii_near(data,bias,st):
            print(f'V062_NEAR_ASCII=owner=0x{st:08x}|0x{va:08x}|{s}')
        if not has_wb and not has_wb_mmio:
            unknown14.extend(xs)

    print(f'V062_OWNERS_CALLING_WB_SETTER={wb_owner_hits}')
    print(f'V062_OWNERS_WITH_WB_MMIO_LITERAL={wb_mmio_hits}')
    print(f'V062_OWNERS_WITH_OPMODE_MMIO_LITERAL={opmode_hits}')
    print('V062_14BIT_XREFS_WITHOUT_WB_RELATION='+(','.join(f'0x{x:08x}' for x in unknown14) or '-'))

    # Conservative verdict: only direct owner relationship to proven WB setter or
    # its MMIO page keeps a 14-bit WB-ceiling hypothesis alive.
    if wb_owner_hits or wb_mmio_hits:
        print('OVERALL_VERDICT=CENTRAL_14BIT_HAS_WB_RELATION_NEEDS_FIELD_DATAFLOW')
    else:
        print('OVERALL_VERDICT=CENTRAL_14BIT_NOT_TIED_TO_PROVEN_WB_PATH')

if __name__=='__main__': main()
