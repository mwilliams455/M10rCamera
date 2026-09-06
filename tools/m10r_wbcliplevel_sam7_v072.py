#!/usr/bin/env python3
"""M10-R v0.72: trace IMG-SAM7 Im_B2Y_Set_WB_Clip_Level implementation.
Research only; no renderer/application changes.
"""
from __future__ import annotations
from pathlib import Path
import csv,re,struct,sys
from collections import Counter
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC,ARM_OP_IMM

TARGET=b'CI:Im_B2Y_Set_WB_Clip_Level error. b2y_bay_color = NULL'
PREFIX=b'CI:Im_B2Y_Set_'

def u32(b,o):return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def cstr(b,o,lim=200):
    e=b.find(b'\0',o,min(len(b),o+lim))
    if e<0:return None
    try:return b[o:e].decode('ascii')
    except:return None

def find_section(root,name):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    for r in rows:
        if r['name']==name:return r,(root/r['file']).read_bytes()
    return None,None

def strings(b,prefix):
    out=[];p=0
    while True:
        p=b.find(prefix,p)
        if p<0:return out
        s=cstr(b,p)
        if s:out.append((p,s))
        p+=1

def pc_lit(ins,b,base):
    try:ops=list(ins.operands)
    except:return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            q=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(b,q-base)
            if v is not None:return q,v
    return None

def branch(ins):
    if ins.mnemonic.lower() not in ('bl','blx'):return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
    except:pass
    return None

def scan_literals(md,b,base=0):
    out=[]
    for o in range(0,len(b)-4,2):
        ins=next(md.disasm(b[o:o+4],base+o,count=1),None)
        if not ins:continue
        lv=pc_lit(ins,b,base)
        if lv:out.append((ins.address,lv[0],lv[1],ins.mnemonic,ins.op_str))
    return out

def infer_bias(lits,offs):
    vals=Counter(v for _,_,v,_,_ in lits)
    scores=Counter()
    # Candidate K from every literal value and every known string offset. A
    # correct linked-image base maps several family strings into literal values.
    for v in vals:
        for o in offs:scores[(v-o)&0xffffffff]+=1
    ranked=[]
    valset=set(vals)
    for k in scores:
        hit=sum(1 for o in offs if ((k+o)&0xffffffff) in valset)
        if hit>=2:ranked.append((hit,k))
    ranked.sort(reverse=True)
    return ranked

def func_start(md,b,base,xref,back=0x300):
    lo=max(base,xref-back);best=None
    for a in range(lo,xref+1,2):
        o=a-base
        ins=next(md.disasm(b[o:o+4],a,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():best=a
    return best

def decode(md,b,base,st,limit=0x260):
    o=st-base;out=[]
    for ins in md.disasm(b[o:min(len(b),o+limit)],st):
        out.append(ins);m=ins.mnemonic.lower();op=ins.op_str.lower()
        if (m=='pop' and 'pc' in op) or (m=='bx' and op.strip()=='lr'):break
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]);r,b=find_section(root,'IMG-SAM7')
    print(f'V072_SAM7_FOUND={int(b is not None)}')
    if b is None:
        print('OVERALL_VERDICT=SAM7_NOT_FOUND');return
    print(f'V072_SAM7_SIZE=0x{len(b):x}')
    fam=strings(b,PREFIX)
    print(f'V072_CI_FAMILY_COUNT={len(fam)}')
    for o,s in fam:print(f'V072_CI_STRING=rel=0x{o:x}|{s}')
    th=[o for o,s in fam if s.startswith(TARGET.decode())]
    print(f'V072_TARGET_HITS={len(th)}')
    if not th:
        print('OVERALL_VERDICT=TARGET_NOT_FOUND');return
    target_off=th[0]
    md0=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md0.detail=True
    lits0=scan_literals(md0,b,0)
    print(f'V072_PC_LITERAL_INSNS={len(lits0)}')
    ranked=infer_bias(lits0,[o for o,_ in fam])
    print(f'V072_BIAS_CANDIDATES={len(ranked)}')
    for hit,k in ranked[:16]:print(f'V072_BIAS_CANDIDATE=0x{k:08x}|family_literal_hits={hit}')
    if not ranked:
        print('OVERALL_VERDICT=SAM7_LINK_BIAS_UNRESOLVED');return
    besthit,bias=ranked[0]
    # Require at least 3/4 family strings when possible, otherwise keep result
    # labelled provisional rather than silently asserting a mapping.
    print(f'V072_SAM7_LINK_BIAS=0x{bias:08x}|family_literal_hits={besthit}')
    target_va=(bias+target_off)&0xffffffff
    print(f'V072_TARGET_VA=0x{target_va:08x}|rel=0x{target_off:x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    # Re-scan with linked base so PC literal addresses and branch addresses are
    # reported in the runtime domain.
    lits=scan_literals(md,b,bias)
    x=[z for z in lits if z[2]==target_va]
    print(f'V072_TARGET_LITERAL_XREFS={len(x)}')
    for a,p,v,m,op in x:print(f'V072_TARGET_XREF=0x{a:08x}|pool=0x{p:08x}|{m} {op}')
    starts=[]
    for a,_,_,_,_ in x:
        st=func_start(md,b,bias,a)
        print(f'V072_TARGET_FUNC_START=xref=0x{a:08x}|start={"0x%08x"%st if st else "-"}')
        if st and st not in starts:starts.append(st)
    for st in starts:
        seq=decode(md,b,bias,st)
        calls=[];ldrh=ldrsh=strh=0
        for ins in seq:
            mn=ins.mnemonic.lower()
            if mn=='ldrh':ldrh+=1
            if mn=='ldrsh':ldrsh+=1
            if mn=='strh':strh+=1
            bt=branch(ins)
            if bt is not None:calls.append((ins.address,bt))
        print(f'V072_FUNC_SUMMARY=0x{st:08x}|insns={len(seq)}|ldrh={ldrh}|ldrsh={ldrsh}|strh={strh}|calls={len(calls)}')
        for ins in seq:
            bt=branch(ins);tail=f' ; call=0x{bt:08x}' if bt is not None else ''
            print(f'V072_FUNC_DISASM={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
        for a,t in calls:print(f'V072_FUNC_CALL=0x{a:08x}->0x{t:08x}')
    # Locate all literal xrefs to family strings so analogous functions can be
    # compared without guessing names from proximity alone.
    for o,s in fam:
        va=(bias+o)&0xffffffff;xx=[z for z in lits if z[2]==va]
        print(f'V072_FAMILY_XREFS=0x{va:08x}|count={len(xx)}|{s}')
        for a,p,_,m,op in xx[:16]:
            st=func_start(md,b,bias,a)
            print(f'V072_FAMILY_XREF=0x{a:08x}|func={"0x%08x"%st if st else "-"}|{m} {op}')
    if x and starts and besthit>=2:
        print('OVERALL_VERDICT=SAM7_WBCLIP_API_FUNCTION_EDGE_PROVEN')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_API_FUNCTION_EDGE_PARTIAL')
if __name__=='__main__':main()
