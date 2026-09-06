#!/usr/bin/env python3
"""M10-R v0.77: bounded IMG-SAM7 WBCLIPLEVEL control-flow census.

Does not assume the null/error block begins at 0x4FCE0. It prints the bounded
preceding function region, all prologue/return candidates, branch edges into or
across the diagnostic neighbourhood, and WB-page literal references. Research
only; no renderer/application code is touched.
"""
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

REGION_START=0x4FA80
REGION_END=0x4FCF8
NEAR_START=0x4FC40
NEAR_END=0x4FCF8
WB_PAGE=0x20020080
DIAG=b'I:Im_B2Y_Set_WB_Clip_Level error. b2y_bay_color = NULL'


def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def find_section(root,name):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    for r in rows:
        if r['name']==name:return (root/r['file']).read_bytes()
    return None

def one(md,b,o):
    if o<0 or o>=len(b)-1:return None
    return next(md.disasm(b[o:o+4],o,count=1),None)

def aligned(md,b,a,z):
    for o in range(max(0,a)&~1,min(len(b),z)&~1,2):
        ins=one(md,b,o)
        if ins:yield ins

def pc_lit(ins,b):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                q=((ins.address+4)&~3)+int(op.mem.disp)
                v=u32(b,q)
                if v is not None:return q,v
    except:pass
    return None

def branch_target(ins):
    mn=ins.mnemonic.lower()
    if not (mn.startswith('b') or mn in ('cbz','cbnz')) or mn in ('bic','bics'):return None
    try:
        vals=[int(op.imm)&0xffffffff for op in ins.operands if op.type==ARM_OP_IMM]
        return vals[-1] if vals else None
    except:return None

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    b=find_section(Path(sys.argv[1]),'IMG-SAM7')
    print(f'V077_SAM7_FOUND={int(b is not None)}')
    if b is None:return
    diag=b.find(DIAG)
    print(f'V077_DIAG_REL={"0x%x"%diag if diag>=0 else "-"}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    pushes=[];returns=[];edges=[];wb=[]
    for ins in aligned(md,b,REGION_START,REGION_END):
        mn=ins.mnemonic.lower();bt=branch_target(ins);lv=pc_lit(ins,b)
        if mn=='push' and 'lr' in ins.op_str.lower():pushes.append(ins.address)
        if (mn=='pop' and 'pc' in ins.op_str.lower()) or (mn=='bx' and ins.op_str.strip().lower()=='lr'):returns.append(ins.address)
        if bt is not None:
            if NEAR_START<=bt<NEAR_END or (ins.address<NEAR_START and bt>=NEAR_END):
                edges.append((ins.address,bt,mn,ins.op_str))
        if lv and lv[1]==WB_PAGE:wb.append((ins.address,lv[0],ins.op_str))

    print('V077_PUSHES='+(','.join(f'0x{x:x}' for x in pushes) or '-'))
    print('V077_RETURNS='+(','.join(f'0x{x:x}' for x in returns) or '-'))
    print(f'V077_NEAR_EDGE_COUNT={len(edges)}')
    for a,t,m,op in edges:print(f'V077_NEAR_EDGE=0x{a:x}->0x{t:x}|{m} {op}')
    print(f'V077_WB_PAGE_LITERAL_COUNT={len(wb)}')
    for a,p,op in wb:print(f'V077_WB_PAGE_LITERAL=0x{a:x}|pool=0x{p:x}|{op}')

    print('V077_CONTEXT_BEGIN')
    for ins in aligned(md,b,REGION_START,REGION_END):
        lv=pc_lit(ins,b);bt=branch_target(ins);extra=''
        if lv:extra+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
        if bt is not None:extra+=f' ; branch=0x{bt:x}'
        print(f'V077_CONTEXT={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{extra}'.rstrip())
    print('V077_CONTEXT_END')
    print('OVERALL_VERDICT=BOUNDED_CONTEXT_CENSUS_COMPLETE')
if __name__=='__main__':main()
