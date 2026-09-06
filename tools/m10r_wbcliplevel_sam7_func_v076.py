#!/usr/bin/env python3
"""M10-R v0.76: recover IMG-SAM7 WBCLIPLEVEL control flow robustly.

Extends v075 only where the evidence failed: Thumb CBZ/CBNZ are treated as
conditional branches, and entry into any instruction of the compact null/error
block is accepted. All addresses remain IMG-SAM7 section-relative. Research
only; no renderer/application code is touched.
"""
from __future__ import annotations
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC,ARM_REG_R0

DIAG=b'I:Im_B2Y_Set_WB_Clip_Level error. b2y_bay_color = NULL'
WB_PAGE=0x20020080
EXPECTED_DIAG=0x500B8
EXPECTED_XREF=0x4FCEA
ERROR_START=0x4FCE0
ERROR_END=0x4FCF8


def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def find_section(root:Path,name:str):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    for r in rows:
        if r['name']==name:return (root/r['file']).read_bytes()
    return None

def one(md,b,o):
    if o<0 or o>=len(b)-1:return None
    return next(md.disasm(b[o:o+4],o,count=1),None)

def aligned_scan(md,b,a,z):
    a=max(0,a)&~1; z=min(len(b),z)&~1
    for o in range(a,z,2):
        ins=one(md,b,o)
        if ins: yield ins

def pc_lit(ins,b):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                q=((ins.address+4)&~3)+int(op.mem.disp)
                v=u32(b,q)
                if v is not None:return q,v
    except: pass
    return None

def adr_targets(ins):
    if ins.mnemonic.lower()!='adr':return []
    out=[]
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:
                imm=int(op.imm)&0xffffffff
                out += [imm,((((ins.address+4)&~3)+imm)&0xffffffff)]
    except: pass
    return out

def branch_target(ins):
    mn=ins.mnemonic.lower()
    if not (mn.startswith('b') or mn in ('cbz','cbnz')):return None
    if mn in ('bic','bics'):return None
    try:
        imms=[int(op.imm)&0xffffffff for op in ins.operands if op.type==ARM_OP_IMM]
        return imms[-1] if imms else None
    except:return None

def is_conditional_branch(ins):
    mn=ins.mnemonic.lower()
    if mn in ('cbz','cbnz'):return True
    return mn.startswith('b') and mn not in ('b','bl','blx','bic','bics')

def find_diag_xrefs(md,b,diag):
    out=[]
    for ins in aligned_scan(md,b,diag-0x3000,diag+0x800):
        if diag in adr_targets(ins):out.append((ins.address,'ADR'))
        lv=pc_lit(ins,b)
        if lv and lv[1]==diag:out.append((ins.address,'LDR_LITERAL_OFFSET'))
    return out

def find_error_entries(md,b,a,z,back=0x1000):
    out=[]
    for ins in aligned_scan(md,b,a-back,a):
        bt=branch_target(ins)
        if bt is not None and a<=bt<z and is_conditional_branch(ins):
            out.append((ins.address,bt,ins.mnemonic,ins.op_str))
    return out

def find_func_start(md,b,site,back=0x400):
    pushes=[]
    for ins in aligned_scan(md,b,site-back,site+1):
        if ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():pushes.append(ins.address)
    return pushes[-1] if pushes else None

def linear_decode(md,b,a,z):
    out=[];o=a
    while o<z:
        ins=one(md,b,o)
        if not ins:o+=2;continue
        out.append(ins);o+=ins.size
    return out

def mem_base_offset(ins):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM:return ins.reg_name(op.mem.base),int(op.mem.disp)
    except:pass
    return None

def detect_input_reg(seq):
    for ins in seq[:16]:
        if ins.mnemonic.lower() in ('mov','movs'):
            try:
                ops=list(ins.operands)
                if len(ops)>=2 and ops[1].reg==ARM_REG_R0:
                    return ins.reg_name(ops[0].reg)
            except:pass
    return 'r0'

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    b=find_section(Path(sys.argv[1]),'IMG-SAM7')
    print(f'V076_SAM7_FOUND={int(b is not None)}')
    if b is None:
        print('OVERALL_VERDICT=SAM7_NOT_FOUND');return
    diag=b.find(DIAG)
    print(f'V076_DIAG_REL={"0x%x"%diag if diag>=0 else "-"}')
    print(f'V076_DIAG_EXPECTED_MATCH={int(diag==EXPECTED_DIAG)}')
    if diag<0:
        print('OVERALL_VERDICT=DIAG_NOT_FOUND');return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    refs=find_diag_xrefs(md,b,diag)
    print(f'V076_DIAG_XREF_COUNT={len(refs)}')
    for a,k in refs:print(f'V076_DIAG_XREF=0x{a:x}|{k}')
    print(f'V076_EXPECTED_XREF_PRESENT={int(any(a==EXPECTED_XREF for a,_ in refs))}')

    entries=find_error_entries(md,b,ERROR_START,ERROR_END)
    print(f'V076_ERROR_ENTRY_COUNT={len(entries)}')
    for a,t,m,op in entries:print(f'V076_ERROR_ENTRY=0x{a:x}->0x{t:x}|{m} {op}')
    if not entries:
        print('OVERALL_VERDICT=ERROR_ENTRY_STILL_UNRESOLVED');return
    site=max(entries,key=lambda x:x[0])[0]
    st=find_func_start(md,b,site)
    print(f'V076_SELECTED_ENTRY=0x{site:x}')
    print(f'V076_FUNC_START={"0x%x"%st if st is not None else "-"}')
    if st is None:
        print('OVERALL_VERDICT=FUNC_START_UNRESOLVED');return
    seq=linear_decode(md,b,st,ERROR_END)
    input_reg=detect_input_reg(seq)
    print(f'V076_INPUT_BASE_REG={input_reg}')

    page_regs=set(); page_mem=[]; input_mem=[]; cmps=[]; ldrh=0;ldrsh=0
    for ins in seq:
        lv=pc_lit(ins,b)
        if lv and lv[1]==WB_PAGE:
            dst=ins.op_str.split(',')[0].strip().lower();page_regs.add(dst)
            print(f'V076_WB_PAGE_LITERAL=0x{ins.address:x}|pool=0x{lv[0]:x}|reg={dst}')
        mn=ins.mnemonic.lower();m=mem_base_offset(ins)
        if mn=='ldrh':ldrh+=1
        if mn=='ldrsh':ldrsh+=1
        if m and m[0]==input_reg and mn.startswith('ldr'):
            input_mem.append((ins.address,mn,m[1],ins.op_str))
        if m and m[0] in page_regs and mn.startswith(('ldr','str')):
            page_mem.append((ins.address,mn,m[1],ins.op_str))
        if mn in ('cmp','cmn','tst','teq'):
            cmps.append((ins.address,mn,ins.op_str))

    for ins in seq:
        extra='';lv=pc_lit(ins,b);bt=branch_target(ins)
        if lv:extra+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
        if bt is not None:extra+=f' ; branch=0x{bt:x}'
        print(f'V076_FUNC_DISASM={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{extra}'.rstrip())
    for a,m,o,op in input_mem:print(f'V076_INPUT_MEM=0x{a:x}|{m}|{input_reg}+0x{o:x}|{op}')
    for a,m,o,op in page_mem:print(f'V076_WB_PAGE_MEM=0x{a:x}|{m}|page+0x{o:x}|{op}')
    for a,m,op in cmps:print(f'V076_COMPARE=0x{a:x}|{m} {op}')

    half=sorted(set(o for _,m,o,_ in input_mem if m=='ldrh'))
    bytes_=sorted(set(o for _,m,o,_ in input_mem if m=='ldrb'))
    reg14=[x for x in page_mem if x[1].startswith('str') and x[2]==0x14]
    reg18=[x for x in page_mem if x[1].startswith('str') and x[2]==0x18]
    print(f'V076_LDRH_COUNT={ldrh}')
    print(f'V076_LDRSH_COUNT={ldrsh}')
    print('V076_INPUT_LDRH_OFFSETS='+(','.join(f'0x{x:x}' for x in half) or '-'))
    print('V076_INPUT_LDRB_OFFSETS='+(','.join(f'0x{x:x}' for x in bytes_) or '-'))
    print(f'V076_REG14_WRITE_COUNT={len(reg14)}')
    print(f'V076_REG18_WRITE_COUNT={len(reg18)}')
    print(f'V076_COMPARE_COUNT={len(cmps)}')
    raw16=(ldrsh==0 and len(half)>=4 and len(reg14)>0 and len(reg18)>0)
    print(f'V076_SAM7_UNSIGNED_RAW16_PATH={int(raw16)}')
    print('V076_FFFF_PHOTOMETRIC_MEANING_PROVEN=0')
    if raw16:
        print('OVERALL_VERDICT=SAM7_WBCLIP_UNSIGNED_RAW16_MMIO_ABI_PROVEN')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_FUNCTION_RECOVERED_NEEDS_ABI_FOLLOWUP')
if __name__=='__main__':main()
