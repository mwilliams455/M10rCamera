#!/usr/bin/env python3
"""M10-R v0.64: prove the dedicated WBCLIPLEVEL path and recover its data ABI.

Inputs are the decoded firmware sections.  This probe stays entirely static and
never changes renderer/application code.

Targets established by v0.63b:
  selector wrapper 0x42154d58 (ADR-backed string: WBCLIPLEVEL)
  low-level driver 0x420d42dc
  driver MMIO page 0x20020080

v0.64 inventories the exact driver packing, literal constants/default branch,
all direct callers, the selector's inline descriptor bytes, the generic paraset
lookup helper it invokes, and every decoded firmware section containing a
WBCLIPLEVEL string.  The goal is to recover active/default clip values or, if
those remain data-driven, establish the narrow boundary cleanly.
"""
from __future__ import annotations

from pathlib import Path
import csv
import struct
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

WRAP=0x42154D58
DRIVER=0x420D42DC
LOOKUP=0x421A0FC0
CENTRAL=0x42154F84
MMIO=0x20020080
REG0=MMIO+0x14
REG1=MMIO+0x18
INLINE_LO=0x42154DB0
INLINE_HI=0x42154E20
SEARCH_NEEDLES=(b'WBCLIPLEVEL', b'wbcliplevel', b'WbClipLevel', b'WBClipLevel')


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


def adr_target(ins):
    if ins.mnemonic.lower()!='adr': return None
    parts=ins.op_str.split('#')
    if len(parts)!=2: return None
    try: imm=int(parts[1],0)
    except ValueError: return None
    return ((ins.address+4)&~3)+imm


def decode(md,data,bias,st,maxlen=0x1200):
    off=st-bias; seq=[]
    if not (0<=off<len(data)): return seq,st
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        seq.append(ins)
        m=ins.mnemonic.lower(); o=ins.op_str.lower()
        if (m=='pop' and 'pc' in o) or (m=='bx' and o.strip()=='lr'):
            return seq,ins.address+ins.size
    return seq,(seq[-1].address+seq[-1].size if seq else st)


def emit_function(md,data,bias,st,label):
    seq,en=decode(md,data,bias,st)
    print(f'\n=== V064_{label} 0x{st:08x}-0x{en:08x} ===')
    lits=[]; calls=[]; adrs=[]
    for ins in seq:
        rr=litrefs(ins,data,bias)
        tail=[]
        for p,v in rr:
            lits.append((ins.address,p,v))
            cls='MMIO' if 0x20000000<=v<0x30000000 else 'CODE/DATA' if bias<=v<bias+len(data) else 'VALUE'
            s=read_cstr_va(data,bias,v) if bias<=v<bias+len(data) else None
            tail.append(f'pool=0x{p:08x}->0x{v:08x}:{cls}:str={s!r}')
        t=branch_target(ins)
        if ins.mnemonic.lower() in ('bl','blx') and t is not None: calls.append((ins.address,t))
        at=adr_target(ins)
        if at is not None:
            adrs.append((ins.address,at))
            s=read_cstr_va(data,bias,at)
            tail.append(f'adr=0x{at:08x}:str={s!r}')
        print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}' + ((' ; '+' ; '.join(tail)) if tail else ''))
    for a,t in calls: print(f'V064_CALL={label}|0x{a:08x}->0x{t:08x}')
    for a,p,v in lits: print(f'V064_LITERAL={label}|ins=0x{a:08x}|pool=0x{p:08x}|value=0x{v:08x}')
    for a,at in adrs: print(f'V064_ADR={label}|ins=0x{a:08x}|target=0x{at:08x}')
    return seq,en,lits,calls,adrs


def find_callers(md,data,bias,target):
    out=[]
    for off in range(0,len(data)-4,2):
        va=bias+off
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if not ins or ins.mnemonic.lower() not in ('bl','blx'): continue
        if branch_target(ins)==target: out.append(va)
    return out


def hex_dump_va(data,bias,lo,hi):
    a=max(0,lo-bias); b=min(len(data),hi-bias)
    for off in range(a,b,16):
        chunk=data[off:min(b,off+16)]
        hx=' '.join(f'{x:02x}' for x in chunk)
        asc=''.join(chr(x) if 32<=x<127 else '.' for x in chunk)
        print(f'V064_HEX=0x{bias+off:08x}|{hx:<47}|{asc}')


def section_scan(root:Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    hits=[]
    for r in rows:
        b=(root/r['file']).read_bytes()
        seen=set()
        for needle in SEARCH_NEEDLES:
            start=0
            while True:
                p=b.find(needle,start)
                if p<0: break
                if p not in seen:
                    seen.add(p); lo=max(0,p-64); hi=min(len(b),p+160)
                    ctx=b[lo:hi]
                    hits.append((r,p,ctx,lo))
                start=p+1
    return hits


def classify_driver(seq,lits):
    by={i.address:(i.mnemonic.lower(),i.op_str.lower().replace(' ','')) for i in seq}
    lv={a:v for a,_,v in lits}
    checks=[]
    def ck(name,cond,detail):
        checks.append(bool(cond)); print(f'V064_CHECK={name}|{"PASS" if cond else "FAIL"}|{detail}')
    # Normal r1==0 branch: four uint16 inputs are packed as upper/lower pairs.
    ck('normal_branch_mode_zero', by.get(0x420d42dc)==('cmp','r1,#0') and by.get(0x420d42de)==('bne','#0x420d4336'), str(by.get(0x420d42dc)))
    ck('mmio_base', lv.get(0x420d42e0)==MMIO, f'0x{lv.get(0x420d42e0,0):08x}')
    ck('reg0_low_from_input_plus4', by.get(0x420d42e8)==('ldrh','r3,[r0,#4]') and by.get(0x420d42f2)==('str','r2,[r3,#0x14]'), 'input+4 -> reg+14 low16')
    ck('reg0_high_from_input_plus0', by.get(0x420d42fc)==('ldrh','r3,[r0]') and by.get(0x420d4308)==('str','r2,[r3,#0x14]'), 'input+0 -> reg+14 high16')
    ck('reg1_low_from_input_plus12', by.get(0x420d4312)==('ldrh','r3,[r0,#0xc]') and by.get(0x420d431c)==('str','r2,[r3,#0x18]'), 'input+12 -> reg+18 low16')
    # Exact high-half source instruction is immediately before 0x4330 in this function.
    ck('normal_branch_writes_reg1', any(a in lv and lv[a]==MMIO for a in lv) and by.get(0x420d4332)==('str','r2,[r3,#0x18]'), 'fourth halfword -> reg+18 high16')
    print(f'V064_DRIVER_ABI=0x{REG0:08x}:upper=input[0],lower=input[1]|0x{REG1:08x}:upper=input[2],lower=input[3]')
    print(f'V064_DRIVER_CHECKS={sum(checks)}/{len(checks)}')
    return all(checks)


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); imgs=get_img_section(root)
    print(f'V064_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=WBCLIPLEVEL_SEMANTICS_UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=WBCLIPLEVEL_SEMANTICS_UNRESOLVED_MAP'); return
    print(f'V064_MAP_BIAS=0x{bias:08x}'); print(f"V064_SECTION={row['index']}:{row['name']}")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    wseq,wen,wlits,wcalls,wadrs=emit_function(md,data,bias,WRAP,'WBCLIP_WRAPPER')
    dseq,den,dlits,dcalls,dadrs=emit_function(md,data,bias,DRIVER,'WBCLIP_DRIVER')
    lseq,len_,llits,lcalls,ladrs=emit_function(md,data,bias,LOOKUP,'PARASET_LOOKUP')

    print('\n=== V064_INLINE_DESCRIPTOR_HEXDUMP ===')
    hex_dump_va(data,bias,INLINE_LO,INLINE_HI)

    for target,label in ((WRAP,'WBCLIP_WRAPPER'),(DRIVER,'WBCLIP_DRIVER'),(LOOKUP,'PARASET_LOOKUP')):
        callers=find_callers(md,data,bias,target)
        print(f'V064_CALLERS={label}|count={len(callers)}|'+(','.join(f'0x{x:08x}' for x in callers) or '-'))

    hits=section_scan(root)
    print(f'V064_WBCLIP_STRING_SECTION_HITS={len(hits)}')
    for r,p,ctx,lo in hits:
        asc=''.join(chr(x) if 32<=x<127 else '.' for x in ctx)
        hx=' '.join(f'{x:02x}' for x in ctx[:96])
        print(f"V064_SECTION_HIT=section={r['index']}:{r['name']}|offset=0x{p:x}|context_start=0x{lo:x}|ascii={asc}")
        print(f"V064_SECTION_HIT_HEX=section={r['index']}|offset=0x{p:x}|{hx}")

    named=any(at in range(0x42154db0,0x42154e10) for _,at in wadrs) and any(b'WBCLIPLEVEL' in data[max(0,at-bias):min(len(data),at-bias+96)] for _,at in wadrs)
    calls_driver=any(t==DRIVER for _,t in wcalls)
    calls_lookup=any(t==LOOKUP for _,t in wcalls)
    abi_ok=classify_driver(dseq,dlits)
    mmio_values={v for _,_,v in dlits if 0x20000000<=v<0x30000000}
    print(f'V064_WBCLIP_NAMED_SELECTOR={int(named)}')
    print(f'V064_WBCLIP_SELECTOR_CALLS_LOOKUP={int(calls_lookup)}')
    print(f'V064_WBCLIP_SELECTOR_CALLS_DRIVER={int(calls_driver)}')
    print(f'V064_WBCLIP_DRIVER_MMIO_PAGE_OK={int(MMIO in mmio_values)}')

    # Literal constants in the alternate/default branch are important evidence.
    vals=sorted({v for _,_,v in dlits if v!=MMIO and not (bias<=v<bias+len(data))})
    print('V064_DRIVER_NONADDRESS_LITERALS='+(','.join(f'0x{x:08x}' for x in vals) or '-'))

    if named and calls_driver and calls_lookup and abi_ok and MMIO in mmio_values:
        if hits:
            print('OVERALL_VERDICT=WBCLIPLEVEL_DRIVER_AND_DATA_ABI_PROVEN_NEEDS_ACTIVE_PARASET_VALUES')
        else:
            print('OVERALL_VERDICT=WBCLIPLEVEL_DRIVER_PROVEN_PARASET_VALUES_NOT_STATICALLY_FOUND')
    else:
        print('OVERALL_VERDICT=WBCLIPLEVEL_SEMANTICS_UNRESOLVED')

if __name__=='__main__': main()
