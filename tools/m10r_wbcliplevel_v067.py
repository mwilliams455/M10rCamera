#!/usr/bin/env python3
"""M10-R v0.67 trace explicit WBCLIPLEVEL selector toward hardware.

v0.66 recovered an exact semantic edge in IMG-System:
  'WBCLIPLEVEL     String:%s'
  'NO VALID STRING   img_b2y_select_wbcliplevel_paraset'
The central B2Y orchestrator 0x42154f84 calls 0x42154d58 immediately after the
proven WB gain setter 0x420d4380.

This probe decodes 0x42154d58, inventories its literals/memory accesses/callees,
then inspects one call level below it for MMIO ownership and clip-related ASCII.
It also inventories every printable 'clip' string in IMG-System and exact callers
of 0x42154d58.  The goal is to locate the actual WB clipping parameter path,
which may be distinct from the unresolved 0x20020780 three-field defaults.
"""
from __future__ import annotations
from pathlib import Path
import re, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

TARGET=0x42154d58
WB_SETTER=0x420d4380
PAGE20780=0x20020780
WB_PAGE=0x20020080
CENTRAL_A=0x42150000
CENTRAL_B=0x42156000


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


def bt(ins):
    if ins.mnemonic.lower() not in ('bl','blx'): return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def decode(md,data,bias,st,maxlen=0xb00):
    seq=[]
    for ins in md.disasm(data[st-bias:min(len(data),st-bias+maxlen)],st):
        seq.append(ins)
        m=ins.mnemonic.lower(); op=ins.op_str.lower()
        if (m=='pop' and 'pc' in op) or (m=='bx' and op.strip()=='lr'):
            return seq,ins.address+ins.size
    return seq,(seq[-1].address+seq[-1].size if seq else st)


def callers(md,data,bias,target,a=CENTRAL_A,b=CENTRAL_B):
    out=[]
    for off in range(a-bias,b-bias,2):
        ins=next(md.disasm(data[off:off+4],bias+off,count=1),None)
        if ins and bt(ins)==target: out.append(ins.address)
    return out


def ascii_all(data,bias,needle='clip'):
    out=[]; i=0
    while i<len(data):
        if 32<=data[i]<127:
            j=i
            while j<len(data) and 32<=data[j]<127: j+=1
            if j-i>=8:
                s=data[i:j].decode('ascii','replace')
                if needle.lower() in s.lower(): out.append((bias+i,s))
            i=j
        else: i+=1
    return out


def classify_literal(v):
    if v==WB_PAGE: return 'WB_PAGE'
    if v==PAGE20780: return 'PAGE20780'
    if 0x20000000<=v<0x30000000: return 'MMIO'
    if 0x40000000<=v<0x50000000: return 'RAM'
    if 0x42000000<=v<0x43000000: return 'IMG_SYSTEM_VA'
    return 'VALUE'


def reg_mem_accesses(seq):
    out=[]
    for ins in seq:
        m=ins.mnemonic.lower()
        if m.startswith(('ldr','str')) and '[' in ins.op_str:
            out.append((ins.address,m,ins.op_str))
    return out


def print_func(tag,md,data,bias,st,maxlen=0x900):
    seq,en=decode(md,data,bias,st,maxlen=maxlen)
    calls=[]; mm=[]; strings=[]
    print(f'\n=== {tag} 0x{st:08x}-0x{en:08x} ===')
    for ins in seq:
        t=bt(ins)
        if t is not None: calls.append((ins.address,t))
        rr=litrefs(ins,data,bias); tail=''
        if rr:
            ps=[]
            for p,v in rr:
                cls=classify_literal(v)
                s=read_cstr_va(data,bias,v) if 0x42000000<=v<0x43000000 else None
                if s: strings.append((v,s))
                if cls in ('WB_PAGE','PAGE20780','MMIO'): mm.append((ins.address,p,v))
                ps.append(f'pool=0x{p:08x}->0x{v:08x}:{cls}:str={s!r}')
            tail=' ; '+' ; '.join(ps)
        print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
    print(f'V067_FUNC_SUMMARY={tag}|start=0x{st:08x}|end=0x{en:08x}|calls={len(calls)}|mmio_refs={len(mm)}|memops={len(reg_mem_accesses(seq))}')
    print('V067_FUNC_CALLS='+(','.join(f'0x{a:08x}->0x{t:08x}' for a,t in calls) or '-'))
    for a,m,o in reg_mem_accesses(seq): print(f'V067_MEMOP={tag}|0x{a:08x}|{m} {o}')
    for a,p,v in mm: print(f'V067_MMIO={tag}|0x{a:08x}|pool=0x{p:08x}|value=0x{v:08x}|{classify_literal(v)}')
    for v,s in sorted(set(strings)): print(f'V067_STRINGREF={tag}|0x{v:08x}|{s}')
    return seq,en,calls,mm,strings


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    imgs=get_img_section(Path(sys.argv[1]))
    print(f'V067_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAP'); return
    print(f'V067_MAP_BIAS=0x{bias:08x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    clips=ascii_all(data,bias,'clip')
    print(f'V067_CLIP_STRINGS={len(clips)}')
    for va,s in clips:
        if 'b2y' in s.lower() or 'wb' in s.lower() or 0x42154000<=va<0x42156000 or 0x420c0000<=va<0x420e0000:
            print(f'V067_CLIP_ASCII=0x{va:08x}|{s}')

    cs=callers(md,data,bias,TARGET)
    print(f'V067_TARGET_CALLERS={len(cs)}|'+(','.join(f'0x{x:08x}' for x in cs) or '-'))

    seq,en,calls0,mm0,strings0=print_func('WBCLIP_SELECTOR',md,data,bias,TARGET,maxlen=0x500)

    # Inspect every direct callee that lives in IMG-System. This is deliberately
    # one level only; deeper expansion must be evidence-driven.
    children=[]
    seen=set()
    for site,t in calls0:
        if 0x42000000<=t<0x43000000 and t not in seen:
            seen.add(t)
            cseq,cen,ccalls,cmm,cstr=print_func(f'CHILD_FROM_0x{site:08x}',md,data,bias,t,maxlen=0x500)
            children.append((site,t,cseq,cen,ccalls,cmm,cstr))

    # Find which child/direct stage has clip strings or B2Y MMIO.
    hardware=[]; semantic=[]
    for site,t,cseq,cen,ccalls,cmm,cstr in children:
        if cmm: hardware.append((site,t,cmm))
        texts=[s for _,s in cstr]
        if any('clip' in s.lower() or 'wb' in s.lower() for s in texts): semantic.append((site,t,texts))
    print(f'V067_CHILDREN_WITH_MMIO={len(hardware)}')
    for site,t,cmm in hardware:
        print(f'V067_HW_CHILD=callsite=0x{site:08x}|callee=0x{t:08x}|mmio='+','.join(f'0x{v:08x}' for _,_,v in cmm))
    print(f'V067_CHILDREN_WITH_CLIP_WB_STRING={len(semantic)}')
    for site,t,texts in semantic:
        print(f'V067_SEM_CHILD=callsite=0x{site:08x}|callee=0x{t:08x}|strings={";".join(texts)}')

    # Relationship to unresolved page: direct/child MMIO ownership is required.
    page_related = any(v==PAGE20780 for _,_,v in mm0) or any(any(v==PAGE20780 for _,_,v in cmm) for _,_,cmm in hardware)
    wbpage_related = any(v==WB_PAGE for _,_,v in mm0) or any(any(v==WB_PAGE for _,_,v in cmm) for _,_,cmm in hardware)
    print(f'V067_WBCLIP_PATH_HAS_PAGE20780={int(page_related)}')
    print(f'V067_WBCLIP_PATH_HAS_WB_PAGE={int(wbpage_related)}')

    if hardware:
        print('OVERALL_VERDICT=WBCLIP_SELECTOR_TO_MMIO_CHILD_FOUND_NEEDS_FIELD_CLASSIFICATION')
    elif page_related:
        print('OVERALL_VERDICT=WBCLIP_SELECTOR_DIRECTLY_OWNS_PAGE20780')
    else:
        print('OVERALL_VERDICT=WBCLIP_SELECTOR_PROVEN_BUT_HARDWARE_EDGE_NOT_IN_ONE_CALL_LEVEL')

if __name__=='__main__': main()
