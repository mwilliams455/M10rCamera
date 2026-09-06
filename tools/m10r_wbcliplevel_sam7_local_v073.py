#!/usr/bin/env python3
"""M10-R v0.73: section-relative IMG-SAM7 WBCLIPLEVEL xref trace.

Avoids assuming a global SAM7 runtime base.  It first searches direct Thumb
PC-relative ADR/ADD edges, then infers any local string-address bias only from
a tight code/string neighbourhood around the verified WB clip error string.
Research-only; no renderer/application changes.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter
import csv,re,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

TARGET=b'CI:Im_B2Y_Set_WB_Clip_Level error. b2y_bay_color = NULL'

def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def find_section(root,name):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    for r in rows:
        if r['name']==name:return r,(root/r['file']).read_bytes()
    return None,None

def branch_target(ins):
    if ins.mnemonic.lower() not in ('b','beq','bne','bhi','blo','bhs','bls','bgt','blt','bge','ble','bl','blx'):return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
    except:pass
    return None

def pc_lit(ins,b):
    try:ops=list(ins.operands)
    except:return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            q=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(b,q)
            if v is not None:return q,v
    return None

def pc_relative_targets(ins):
    out=[]
    try:ops=list(ins.operands)
    except:return out
    mn=ins.mnemonic.lower()
    # Capstone versions differ on whether ADR's immediate is represented as a
    # resolved address or displacement. Keep both interpretations and require
    # an exact match downstream.
    if mn=='adr':
        for op in ops:
            if op.type==ARM_OP_IMM:
                imm=int(op.imm)&0xffffffff
                out.append(('ADR_IMM',imm))
                out.append(('ADR_PCPLUS',(((ins.address+4)&~3)+imm)&0xffffffff))
    if mn in ('add','adds') and 'pc' in ins.op_str.lower():
        imm=None
        for op in ops:
            if op.type==ARM_OP_IMM:imm=int(op.imm)
        if imm is not None:
            out.append(('ADD_PC',(((ins.address+4)&~3)+imm)&0xffffffff))
    return out

def cstrings(b,a,z):
    out=[]
    for m in re.finditer(rb'[ -~]{5,}\x00',b[a:z]):
        raw=m.group()[:-1]
        if len(raw)>220:continue
        try:s=raw.decode('ascii')
        except:continue
        out.append((a+m.start(),s))
    return out

def scan_ins(md,b,a,z):
    out=[]
    for o in range(a,z-4,2):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if ins:out.append(ins)
    return out

def infer_local_bias(lits,strings):
    vals=Counter(v for _,_,v in lits)
    scores=Counter()
    for v in vals:
        for s,_ in strings:scores[(v-s)&0xffffffff]+=1
    ranked=[];vset=set(vals)
    for k in scores:
        matched=[(s,t) for s,t in strings if ((k+s)&0xffffffff) in vset]
        if len(matched)>=3:
            ranked.append((len(matched),k,matched))
    ranked.sort(key=lambda x:(x[0],-(x[1]&0xfff)),reverse=True)
    return ranked

def find_func_start(md,b,xref,back=0x500):
    lo=max(0,xref-back);best=None
    for o in range(lo,xref+1,2):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():best=o
    return best

def decode(md,b,st,lim=0x400):
    out=[]
    for ins in md.disasm(b[st:min(len(b),st+lim)],st):
        out.append(ins)
        mn=ins.mnemonic.lower();op=ins.op_str.lower()
        if (mn=='pop' and 'pc' in op) or (mn=='bx' and op.strip()=='lr'):break
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]);_,b=find_section(root,'IMG-SAM7')
    print(f'V073_SAM7_FOUND={int(b is not None)}')
    if b is None:
        print('OVERALL_VERDICT=SAM7_NOT_FOUND');return
    target=b.find(TARGET)
    print(f'V073_TARGET_REL={"0x%x"%target if target>=0 else "-"}')
    if target<0:
        print('OVERALL_VERDICT=TARGET_NOT_FOUND');return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    a=max(0,target-0x3000);z=min(len(b),target+0x1000)
    insns=scan_ins(md,b,a,z)
    direct=[];lits=[]
    for ins in insns:
        for kind,t in pc_relative_targets(ins):
            if target<=t<target+len(TARGET)+1:
                direct.append((ins.address,kind,t,ins.mnemonic,ins.op_str))
        lv=pc_lit(ins,b)
        if lv:lits.append((ins.address,lv[0],lv[1]))
    print(f'V073_LOCAL_WINDOW=0x{a:x}-0x{z:x}|insns={len(insns)}|pc_literals={len(lits)}')
    print(f'V073_DIRECT_PC_REL_XREFS={len(direct)}')
    for x in direct:print(f'V073_DIRECT_PC_REL_XREF=insn=0x{x[0]:x}|{x[1]}->0x{x[2]:x}|{x[3]} {x[4]}')

    strs=cstrings(b,max(0,target-0x4000),min(len(b),target+0x2000))
    print(f'V073_LOCAL_STRINGS={len(strs)}')
    for o,s in strs:
        if abs(o-target)<=0x500:
            print(f'V073_STRING_NEAR=rel={o-target:+#x}|off=0x{o:x}|{s}')
    ranked=infer_local_bias(lits,strs)
    print(f'V073_LOCAL_BIAS_CANDIDATES={len(ranked)}')
    for score,k,matched in ranked[:12]:
        near=sum(1 for o,_ in matched if abs(o-target)<0x1000)
        print(f'V073_LOCAL_BIAS=0x{k:08x}|matches={score}|near_target={near}|aligned4k={int((k&0xfff)==0)}')
        for o,s in matched[:12]:print(f'V073_LOCAL_BIAS_MATCH=0x{k:08x}|str_rel=0x{o:x}|runtime=0x{(k+o)&0xffffffff:08x}|{s}')

    exact_lit=[]
    for score,k,matched in ranked[:12]:
        tva=(k+target)&0xffffffff
        refs=[x for x in lits if x[2]==tva]
        if refs:
            exact_lit.append((score,k,refs))
            print(f'V073_TARGET_LITERAL_BIAS=0x{k:08x}|score={score}|target_va=0x{tva:08x}|refs={len(refs)}')
            for x in refs:print(f'V073_TARGET_LITERAL_XREF=0x{x[0]:x}|pool=0x{x[1]:x}|value=0x{x[2]:08x}')

    xrefs=[x[0] for x in direct]
    for _,_,refs in exact_lit:xrefs.extend(x[0] for x in refs)
    xrefs=sorted(set(xrefs))
    starts=[]
    for xr in xrefs:
        st=find_func_start(md,b,xr)
        print(f'V073_XREF_FUNC=xref=0x{xr:x}|start={"0x%x"%st if st is not None else "-"}')
        if st is not None and st not in starts:starts.append(st)
    # Also report the nearest three prologue candidates before the string. This
    # is evidence-only fallback if compiler materializes the string address by
    # an encoding outside the recognized ADR/LDR forms.
    pro=[]
    for o in range(max(0,target-0x800),target,2):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():pro.append(o)
    print('V073_NEAREST_PROLOGUES='+(','.join(f'0x{x:x}' for x in pro[-6:]) or '-'))
    candidates=starts[:] if starts else pro[-3:]
    for st in candidates:
        seq=decode(md,b,st)
        print(f'V073_FUNC_BEGIN=0x{st:x}|insns={len(seq)}')
        for ins in seq:
            lv=pc_lit(ins,b);bt=branch_target(ins)
            tail=''
            if lv:tail+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
            if bt is not None:tail+=f' ; branch=0x{bt:x}'
            print(f'V073_FUNC_DISASM={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
        print(f'V073_FUNC_END=0x{st:x}')
    if xrefs:
        print('OVERALL_VERDICT=SAM7_WBCLIP_STRING_XREF_PROVEN')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_STRING_XREF_ENCODING_STILL_UNRESOLVED')
if __name__=='__main__':main()
