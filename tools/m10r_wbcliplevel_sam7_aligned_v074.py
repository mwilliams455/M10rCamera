#!/usr/bin/env python3
"""M10-R v0.74: corrected aligned IMG-SAM7 WBCLIPLEVEL local trace.

Supersedes the v073 odd-aligned scan. Research-only.
"""
from pathlib import Path
import sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from m10r_wbcliplevel_sam7_local_v073 import (
    TARGET,find_section,scan_ins,pc_relative_targets,pc_lit,
    cstrings,infer_local_bias,branch_target
)

def prev_boundary(md,b,xref,back=0x300):
    lo=max(0,(xref-back)&~1);last_ret=None;last_push=None
    for o in range(lo,xref+1,2):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if not ins:continue
        mn=ins.mnemonic.lower();op=ins.op_str.lower()
        if mn=='push' and 'lr' in op:last_push=o
        if (mn=='bx' and op.strip()=='lr') or (mn=='pop' and 'pc' in op):last_ret=o+ins.size
    c=[x for x in (last_ret,last_push) if x is not None and x<=xref]
    return max(c) if c else max(0,(xref-0x80)&~1)

def decode_window(md,b,st,end):
    out=[];o=st
    while o<end:
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if not ins:
            o+=2;continue
        out.append(ins);o+=ins.size
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]);_,b=find_section(root,'IMG-SAM7')
    print(f'V074_SAM7_FOUND={int(b is not None)}')
    if b is None:
        print('OVERALL_VERDICT=SAM7_NOT_FOUND');return
    target=b.find(TARGET)
    print(f'V074_TARGET_REL=0x{target:x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    a=max(0,target-0x3000)&~1;z=min(len(b),target+0x1000)&~1
    insns=scan_ins(md,b,a,z)
    print(f'V074_SCAN_START=0x{a:x}|aligned={int((a&1)==0)}|insns={len(insns)}')
    exact=[];near=[];lits=[]
    for ins in insns:
        for kind,t in pc_relative_targets(ins):
            d=t-target
            if d==0:exact.append((ins.address,kind,t,ins.mnemonic,ins.op_str))
            if abs(d)<=0x10:near.append((ins.address,kind,t,d,ins.mnemonic,ins.op_str))
        lv=pc_lit(ins,b)
        if lv:lits.append((ins.address,lv[0],lv[1]))
    print(f'V074_DIRECT_EXACT_XREFS={len(exact)}')
    for x in exact:print(f'V074_DIRECT_EXACT=0x{x[0]:x}|{x[1]}->0x{x[2]:x}|{x[3]} {x[4]}')
    print(f'V074_DIRECT_NEAR_XREFS={len(near)}')
    for x in near:print(f'V074_DIRECT_NEAR=0x{x[0]:x}|{x[1]}->0x{x[2]:x}|delta={x[3]:+#x}|{x[4]} {x[5]}')

    strs=cstrings(b,max(0,target-0x4000),min(len(b),target+0x2000))
    ranked=infer_local_bias(lits,strs)
    print(f'V074_LOCAL_BIAS_CANDIDATES={len(ranked)}')
    for score,k,matched in ranked[:10]:
        aligned=(k&0xfff)==0
        target_refs=[x for x in lits if x[2]==((k+target)&0xffffffff)]
        print(f'V074_LOCAL_BIAS=0x{k:08x}|matches={score}|aligned4k={int(aligned)}|target_refs={len(target_refs)}')
        for x in target_refs:print(f'V074_LITERAL_TARGET_XREF=0x{x[0]:x}|pool=0x{x[1]:x}|value=0x{x[2]:08x}|bias=0x{k:08x}')

    # Any valid near PC-relative edge deserves a tight sequential decode. ADR
    # may address a word-aligned anchor then adjust by 1-3 bytes to an odd
    # string, so we inspect the surrounding function before declaring a hit.
    refs=sorted(set(x[0] for x in near))
    print(f'V074_NEAR_REF_INSNS={len(refs)}')
    for xr in refs:
        st=prev_boundary(md,b,xr);end=min(len(b),xr+0x100)
        print(f'V074_CONTEXT_BEGIN=xref=0x{xr:x}|start=0x{st:x}|end=0x{end:x}')
        seq=decode_window(md,b,st,end)
        for ins in seq:
            lv=pc_lit(ins,b);bt=branch_target(ins);tail=''
            if lv:tail+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
            if bt is not None:tail+=f' ; branch=0x{bt:x}'
            print(f'V074_CONTEXT={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
        print(f'V074_CONTEXT_END=xref=0x{xr:x}')
    if exact:
        print('OVERALL_VERDICT=SAM7_WBCLIP_EXACT_PC_REL_EDGE_PROVEN')
    elif near:
        print('OVERALL_VERDICT=SAM7_WBCLIP_NEAR_PC_REL_EDGE_REQUIRES_CONTEXT')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_NO_DIRECT_PC_REL_EDGE_FOUND')
if __name__=='__main__':main()
