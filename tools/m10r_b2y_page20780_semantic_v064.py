#!/usr/bin/env python3
"""M10-R v0.64 semantic ownership probe for B2Y MMIO page 0x20020780.

Goal: classify the three 14-bit fields at 0x2002078c/90/94 without inferring
semantics from the value 0x3fff alone.

Evidence sources, all within hash-verified IMG-System:
  1. enumerate every ASCII drv_img_b2y_* diagnostic string;
  2. find Thumb ADR / literal-pool xrefs to those strings and associate nearby
     named functions with MMIO page literals;
  3. find exact full-address literals for 0x2002078c/90/94 and code xrefs;
  4. decode the proven central orchestrator 0x42154f84 around the direct-WB
     call 0x42154fce and the 0x20020780 writes, including adjacent callees;
  5. classify semantic keywords conservatively.

A shared orchestration function is not sufficient to merge sub-block semantics.
No renderer/application files are modified.
"""
from __future__ import annotations
from pathlib import Path
import re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

PAGE=0x20020780
FIELDS=(0x2002078c,0x20020790,0x20020794)
WB_PAGE=0x20020080
WB_SETTER=0x420d4380
ORCH=0x42154f84
ORCH_END=0x42155380
SEMANTIC_WORDS=(
    'clip','clamp','range','limit','max','min','white','black','level','offset',
    'rgb','yuv','window','crop','size','width','height','link','sdram','tone',
    'operation','mode','gain','matrix','gamma','color','colour','threshold'
)


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
    if ins.mnemonic.lower() not in ('bl','blx'): return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def adr_target(ins):
    if ins.mnemonic.lower()!='adr': return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:
                # Capstone commonly returns absolute target for Thumb ADR. If it
                # looks like a small displacement, resolve from aligned PC.
                v=int(op.imm)&0xffffffff
                return v if v>=0x100000 else (((ins.address+4)&~3)+v)&0xffffffff
    except Exception: pass
    return None


def ascii_strings(data,bias,prefix=b'drv_img_b2y_'):
    out=[]; pos=0
    while True:
        p=data.find(prefix,pos)
        if p<0: break
        lo=p
        # diagnostics sometimes include a prefix before drv_img_b2y_; retain
        # only the API-ish token itself through printable terminator.
        j=p
        while j<len(data) and 32<=data[j]<127: j+=1
        s=data[p:j].decode('ascii','replace')
        out.append((bias+p,s)); pos=p+1
    return out


def find_string_xrefs(md,data,bias,targets):
    """Candidate-seeded scan around each string/literal pool, not full linear disasm."""
    by_target={t:[] for t in targets}
    # First locate raw 32-bit pointer pools to strings.
    pools={t:[] for t in targets}
    for t in targets:
        pat=struct.pack('<I',t); p=0
        while True:
            q=data.find(pat,p)
            if q<0: break
            pools[t].append(bias+q); p=q+1
    # Thumb LDR literal reach is bounded. Search around each pool. Also search
    # ADR in a bounded +/-4KB neighborhood of each actual string.
    for t in targets:
        seen=set()
        for pool in pools[t]:
            lo=max(bias,pool-0x1200); hi=min(bias+len(data),pool+0x100)
            for va in range(lo,hi,2):
                ins=next(md.disasm(data[va-bias:va-bias+4],va,count=1),None)
                if not ins: continue
                if any(p==pool and v==t for p,v in litrefs(ins,data,bias)):
                    key=(va,'LDR',pool)
                    if key not in seen:
                        seen.add(key); by_target[t].append((va,'LDR',pool,ins.mnemonic,ins.op_str))
        lo=max(bias,t-0x1000); hi=min(bias+len(data),t+0x100)
        for va in range(lo,hi,2):
            ins=next(md.disasm(data[va-bias:va-bias+4],va,count=1),None)
            if not ins: continue
            at=adr_target(ins)
            if at==t:
                key=(va,'ADR',None)
                if key not in seen:
                    seen.add(key); by_target[t].append((va,'ADR',None,ins.mnemonic,ins.op_str))
    return by_target,pools


def nearest_push(md,data,bias,x,back=0x700):
    found=[]
    for va in range(max(bias,x-back),x,2):
        ins=next(md.disasm(data[va-bias:va-bias+4],va,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower(): found.append(va)
    return found[-1] if found else None


def decode_function(md,data,bias,st,maxlen=0xc00):
    seq=[]
    for ins in md.disasm(data[st-bias:min(len(data),st-bias+maxlen)],st):
        seq.append(ins)
        m=ins.mnemonic.lower(); op=ins.op_str.lower()
        if (m=='pop' and 'pc' in op) or (m=='bx' and op.strip()=='lr'):
            return seq,ins.address+ins.size
    return seq,(seq[-1].address+seq[-1].size if seq else st)


def exact_literal_xrefs(md,data,bias,value):
    pools=[]; pat=struct.pack('<I',value); p=0
    while True:
        q=data.find(pat,p)
        if q<0: break
        pools.append(bias+q); p=q+1
    x=[]
    for pool in pools:
        lo=max(bias,pool-0x1200); hi=min(bias+len(data),pool+0x100)
        for va in range(lo,hi,2):
            ins=next(md.disasm(data[va-bias:va-bias+4],va,count=1),None)
            if ins and any(pp==pool and vv==value for pp,vv in litrefs(ins,data,bias)):
                x.append((va,pool,ins.mnemonic,ins.op_str))
    return pools,sorted(set(x))


def classify_name(s):
    low=s.lower()
    return [w for w in SEMANTIC_WORDS if w in low]


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    imgs=get_img_section(Path(sys.argv[1]))
    print(f'V064_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAP'); return
    print(f'V064_MAP_BIAS=0x{bias:08x}')
    print(f"V064_SECTION={row['index']}:{row['name']}")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    names=ascii_strings(data,bias)
    print(f'V064_B2Y_NAME_STRINGS={len(names)}')
    sx,pools=find_string_xrefs(md,data,bias,[va for va,_ in names])
    named_owners={}
    for sva,s in names:
        kws=classify_name(s)
        refs=sx.get(sva,[])
        print(f'V064_NAME=0x{sva:08x}|{s}|keywords={",".join(kws) or "-"}|xrefs={len(refs)}')
        for ref in refs:
            va,kind,pool,mn,ops=ref
            st=nearest_push(md,data,bias,va)
            print(f'  V064_NAME_XREF=0x{va:08x}|{kind}|pool={"-" if pool is None else f"0x{pool:08x}"}|owner={"-" if st is None else f"0x{st:08x}"}|{mn} {ops}')
            if st is not None:
                named_owners.setdefault(st,set()).add(s)

    # Inventory named owner functions and MMIO literals. This is the core page
    # ownership correlation.
    owners_with_page=[]; owners_with_wb=[]
    for st,ss in sorted(named_owners.items()):
        seq,en=decode_function(md,data,bias,st)
        mmio=[]; calls=[]; vals=[]
        for ins in seq:
            bt=branch_target(ins)
            if bt is not None: calls.append((ins.address,bt))
            for p,v in litrefs(ins,data,bias):
                vals.append((ins.address,p,v))
                if 0x20000000<=v<0x30000000: mmio.append(v)
        has_page=PAGE in mmio or any(v in FIELDS for _,_,v in vals)
        has_wb=WB_PAGE in mmio or WB_SETTER in [t for _,t in calls]
        if has_page: owners_with_page.append((st,en,sorted(ss),sorted(set(mmio))))
        if has_wb: owners_with_wb.append((st,en,sorted(ss),sorted(set(mmio))))
        print(f'V064_NAMED_OWNER=start=0x{st:08x}|end=0x{en:08x}|names={";".join(sorted(ss))}|mmio={",".join(f"0x{x:08x}" for x in sorted(set(mmio))) or "-"}|has_page20780={int(has_page)}|has_wb_relation={int(has_wb)}')

    # Exact address ownership: a dedicated setter could use 0x2002078c/90/94
    # directly without ever loading the base page.
    field_code_xrefs=[]
    for value in (PAGE,)+FIELDS:
        pp,xx=exact_literal_xrefs(md,data,bias,value)
        print(f'V064_ADDR_LITERAL=value=0x{value:08x}|raw_pools={len(pp)}|code_xrefs={len(xx)}')
        for va,pool,mn,ops in xx:
            st=nearest_push(md,data,bias,va)
            print(f'  V064_ADDR_XREF=0x{va:08x}|value=0x{value:08x}|pool=0x{pool:08x}|owner={"-" if st is None else f"0x{st:08x}"}|{mn} {ops}')
            if value in FIELDS: field_code_xrefs.append((value,va,st))

    # Decode the exact orchestrator window and label calls around WB + page writes.
    print('\n=== V064 ORCHESTRATOR 0x42154f84 ===')
    orch_calls=[]; page_first=None; page_last=None; wb_call=None
    for ins in md.disasm(data[ORCH-bias:ORCH_END-bias],ORCH):
        rr=litrefs(ins,data,bias); bt=branch_target(ins)
        if bt is not None:
            orch_calls.append((ins.address,bt))
            if bt==WB_SETTER: wb_call=ins.address
        if any(v==PAGE for _,v in rr):
            page_first=ins.address if page_first is None else min(page_first,ins.address)
            page_last=ins.address if page_last is None else max(page_last,ins.address)
        tail=''
        if rr: tail=' ; '+';'.join(f'pool=0x{p:08x}->0x{v:08x}' for p,v in rr)
        print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
        if ins.mnemonic.lower()=='pop' and 'pc' in ins.op_str.lower(): break
    print(f'V064_ORCH_WB_CALL={"-" if wb_call is None else f"0x{wb_call:08x}"}')
    print(f'V064_ORCH_PAGE_REF_SPAN={"-" if page_first is None else f"0x{page_first:08x}-0x{page_last:08x}"}')
    for a,t in orch_calls:
        relation='BEFORE_WB' if wb_call is not None and a<wb_call else 'AFTER_WB_BEFORE_PAGE' if wb_call is not None and page_first is not None and wb_call<a<page_first else 'PAGE_NEIGHBOR' if page_first is not None and page_first-0x20<=a<=page_last+0x20 else 'AFTER_PAGE'
        print(f'V064_ORCH_CALL=0x{a:08x}->0x{t:08x}|{relation}')

    # Map adjacent callees to any named owner we recovered.
    for a,t in orch_calls:
        labels=sorted(named_owners.get(t,set()))
        if labels:
            print(f'V064_ORCH_CALLEE_NAME=0x{a:08x}->0x{t:08x}|{";".join(labels)}')

    page_name_hits=[]
    for st,en,ss,mm in owners_with_page:
        for s in ss:
            kws=classify_name(s)
            if kws: page_name_hits.append((st,s,kws))

    print(f'V064_NAMED_OWNERS_WITH_PAGE20780={len(owners_with_page)}')
    print(f'V064_NAMED_OWNERS_WITH_WB_RELATION={len(owners_with_wb)}')
    print(f'V064_DIRECT_FIELD_ADDRESS_XREFS={len(field_code_xrefs)}')
    for st,s,kws in page_name_hits:
        print(f'V064_PAGE_SEMANTIC_NAME=0x{st:08x}|{s}|keywords={",".join(kws)}')

    # Verdict intentionally conservative. Positive semantic evidence requires a
    # named page owner containing range/clip/level/RGB/white/black concepts. A
    # shared top-level orchestrator does not count.
    strong={'clip','clamp','range','limit','white','black','level','rgb','threshold'}
    strong_hits=[(st,s,kws) for st,s,kws in page_name_hits if strong.intersection(kws)]
    if strong_hits:
        print('OVERALL_VERDICT=PAGE_20020780_RANGE_OR_PIXEL_SEMANTICS_PRESENT_NEEDS_DATAFLOW')
    elif owners_with_page:
        print('OVERALL_VERDICT=PAGE_20020780_NAMED_NONRANGE_CONTROL_SUBBLOCK')
    elif field_code_xrefs:
        print('OVERALL_VERDICT=PAGE_20020780_FIELD_SETTER_EXISTS_BUT_SEMANTICS_UNNAMED')
    else:
        print('OVERALL_VERDICT=PAGE_20020780_ONLY_SHARED_ORCHESTRATOR_NO_NAMED_OWNER')

if __name__=='__main__': main()
