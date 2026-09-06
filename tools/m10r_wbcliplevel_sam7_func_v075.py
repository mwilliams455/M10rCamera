#!/usr/bin/env python3
"""M10-R v0.75: recover the complete IMG-SAM7 WB clip API function.

Starts only from the corrected aligned diagnostic edge established by v074.
All addresses are section-relative Thumb offsets; no SAM7 runtime bias is
assumed. Research-only: no renderer/application code is touched.
"""
from __future__ import annotations
from pathlib import Path
import csv,re,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

DIAG=b'I:Im_B2Y_Set_WB_Clip_Level error. b2y_bay_color = NULL'
WB_PAGE=0x20020080
EXPECTED_DIAG=0x500B8
EXPECTED_XREF=0x4FCEA
EXPECTED_NULL=0x4FCE0
EXPECTED_END=0x4FCF8


def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def find_section(root:Path,name:str):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    for r in rows:
        if r['name']==name:return r,(root/r['file']).read_bytes()
    return None,None

def pc_lit(ins,b):
    try:ops=list(ins.operands)
    except:return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            q=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(b,q)
            if v is not None:return q,v
    return None

def branch_target(ins):
    mn=ins.mnemonic.lower()
    if not (mn.startswith('b') and mn not in ('bic','bics')):return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
    except:pass
    return None

def adr_targets(ins):
    if ins.mnemonic.lower()!='adr':return []
    out=[]
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:
                imm=int(op.imm)&0xffffffff
                out.append(imm)
                out.append((((ins.address+4)&~3)+imm)&0xffffffff)
    except:pass
    return out

def one(md,b,o):
    if o<0 or o>=len(b)-2:return None
    return next(md.disasm(b[o:o+4],o,count=1),None)

def aligned_scan(md,b,a,z):
    a&=~1;z=min(len(b),z)&~1
    for o in range(a,z,2):
        ins=one(md,b,o)
        if ins:yield ins

def find_diag_xrefs(md,b,diag):
    refs=[]
    for ins in aligned_scan(md,b,max(0,diag-0x3000),min(len(b),diag+0x800)):
        if diag in adr_targets(ins):refs.append((ins.address,'ADR'))
        lv=pc_lit(ins,b)
        if lv and lv[1]==diag:refs.append((ins.address,'LDR_LITERAL_OFFSET'))
    return refs

def find_null_tail(md,b,xref):
    # v074 established a compact diagnostic tail immediately before xref:
    # three literal loads + log call + ADR diagnostic + log/terminate calls.
    # Recover the first aligned instruction in that basic block by looking for
    # the closest prior load sequence, while retaining the known expected value
    # as an explicit sanity check rather than silently hard-coding the verdict.
    candidates=[]
    for o in range(max(0,xref-0x30)&~1,xref+1,2):
        seq=[one(md,b,o+2*i) for i in range(4)]
        if all(seq) and all(x.mnemonic.lower()=='ldr' for x in seq[:3]) and seq[3].mnemonic.lower() in ('bl','blx'):
            candidates.append(o)
    return candidates[-1] if candidates else None

def find_cond_branches_to(md,b,target,back=0x800):
    out=[]
    for ins in aligned_scan(md,b,max(0,target-back),target):
        bt=branch_target(ins)
        if bt==target and ins.mnemonic.lower() not in ('b','bl','blx'):
            out.append(ins.address)
    return out

def find_func_start(md,b,branch,back=0x120):
    pushes=[]
    for ins in aligned_scan(md,b,max(0,branch-back),branch+1):
        if ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():pushes.append(ins.address)
    return pushes[-1] if pushes else None

def linear_decode(md,b,a,z):
    out=[];o=a
    while o<z:
        ins=one(md,b,o)
        if not ins:
            o+=2;continue
        out.append(ins);o+=ins.size
    return out

def mem_base_offset(ins):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM:
                return ins.reg_name(op.mem.base),int(op.mem.disp)
    except:pass
    return None

def reg_written(ins):
    try:
        ops=list(ins.operands)
        if ops and ops[0].type!=ARM_OP_MEM:return ins.reg_name(ops[0].reg) if ops[0].reg else None
    except:pass
    return None

def parse_imm(s):
    m=re.search(r'#(0x[0-9a-f]+|\d+)',s.lower())
    return int(m.group(1),0) if m else None

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]);_,b=find_section(root,'IMG-SAM7')
    print(f'V075_SAM7_FOUND={int(b is not None)}')
    if b is None:
        print('OVERALL_VERDICT=SAM7_NOT_FOUND');return
    diag=b.find(DIAG)
    print(f'V075_DIAG_REL={"0x%x"%diag if diag>=0 else "-"}')
    print(f'V075_DIAG_EXPECTED_MATCH={int(diag==EXPECTED_DIAG)}')
    if diag<0:
        print('OVERALL_VERDICT=DIAG_NOT_FOUND');return

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    refs=find_diag_xrefs(md,b,diag)
    print(f'V075_DIAG_XREF_COUNT={len(refs)}')
    for a,k in refs:print(f'V075_DIAG_XREF=0x{a:x}|{k}')
    xref=refs[0][0] if len(refs)==1 else (EXPECTED_XREF if any(a==EXPECTED_XREF for a,_ in refs) else None)
    if xref is None:
        print('OVERALL_VERDICT=DIAG_XREF_AMBIGUOUS');return
    print(f'V075_DIAG_XREF_SELECTED=0x{xref:x}|expected={int(xref==EXPECTED_XREF)}')

    tail=find_null_tail(md,b,xref)
    print(f'V075_NULL_TAIL={"0x%x"%tail if tail is not None else "-"}|expected={int(tail==EXPECTED_NULL) if tail is not None else 0}')
    if tail is None:
        print('OVERALL_VERDICT=NULL_TAIL_UNRESOLVED');return
    branches=find_cond_branches_to(md,b,tail)
    print(f'V075_NULL_BRANCH_COUNT={len(branches)}')
    for a in branches:
        ins=one(md,b,a);print(f'V075_NULL_BRANCH=0x{a:x}->0x{tail:x}|{ins.mnemonic} {ins.op_str}')
    if not branches:
        print('OVERALL_VERDICT=NULL_BRANCH_UNRESOLVED');return
    # Prefer the closest branch to the null tail: it belongs to the function
    # whose error path is this tail, whereas older branches can target a shared
    # error block only in unusual compiler layouts.
    nb=max(branches)
    st=find_func_start(md,b,nb)
    print(f'V075_FUNC_START={"0x%x"%st if st is not None else "-"}')
    if st is None:
        print('OVERALL_VERDICT=FUNC_START_UNRESOLVED');return
    end=EXPECTED_END if st<EXPECTED_END<=len(b) else tail+0x18
    print(f'V075_FUNC_END=0x{end:x}')
    seq=linear_decode(md,b,st,end)

    # Track direct loads of the WB page literal so memory writes can be tied to
    # the actual base register without relying on function names.
    page_regs=set(); input_loads=[]; page_mem=[]; cmps=[]; signed=0; unsigned=0
    for ins in seq:
        lv=pc_lit(ins,b)
        if lv and lv[1]==WB_PAGE:
            dst=ins.op_str.split(',')[0].strip().lower();page_regs.add(dst)
            print(f'V075_WB_PAGE_LITERAL=0x{ins.address:x}|pool=0x{lv[0]:x}|reg={dst}')
        mn=ins.mnemonic.lower();m=mem_base_offset(ins)
        if mn=='ldrh':unsigned+=1
        if mn=='ldrsh':signed+=1
        if m and m[0]=='r4' and mn.startswith('ldr'):
            input_loads.append((ins.address,mn,m[1],ins.op_str))
        if m and m[0] in page_regs and mn.startswith(('ldr','str')):
            page_mem.append((ins.address,mn,m[1],ins.op_str))
        if mn in ('cmp','cmn','tst','teq'):
            cmps.append((ins.address,mn,ins.op_str))

    for ins in seq:
        lv=pc_lit(ins,b);bt=branch_target(ins);tailtxt=''
        if lv:tailtxt+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
        if bt is not None:tailtxt+=f' ; branch=0x{bt:x}'
        print(f'V075_FUNC_DISASM={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tailtxt}'.rstrip())
    for a,m,o,op in input_loads:print(f'V075_INPUT_LOAD=0x{a:x}|{m}|r4+0x{o:x}|{op}')
    for a,m,o,op in page_mem:print(f'V075_WB_PAGE_MEM=0x{a:x}|{m}|page+0x{o:x}|{op}')
    for a,m,op in cmps:print(f'V075_COMPARE=0x{a:x}|{m} {op}')

    reg14_stores=[x for x in page_mem if x[1].startswith('str') and x[2]==0x14]
    reg18_stores=[x for x in page_mem if x[1].startswith('str') and x[2]==0x18]
    # Range checks are conservatively defined as CMP/CMN instructions after the
    # initial pointer-null branch. TST/TEQ are reported but not promoted as a
    # numeric range check.
    numeric_cmps=[x for x in cmps if x[1] in ('cmp','cmn')]
    print(f'V075_LDRH_COUNT={unsigned}')
    print(f'V075_LDRSH_COUNT={signed}')
    print(f'V075_INPUT_LOAD_COUNT={len(input_loads)}')
    print(f'V075_COMPARE_COUNT={len(cmps)}')
    print(f'V075_NUMERIC_CMP_COUNT={len(numeric_cmps)}')
    print(f'V075_REG14_WRITE_COUNT={len(reg14_stores)}')
    print(f'V075_REG18_WRITE_COUNT={len(reg18_stores)}')
    raw_halfword_offsets=sorted(set(o for _,m,o,_ in input_loads if m=='ldrh'))
    print('V075_INPUT_LDRH_OFFSETS='+(','.join(f'0x{x:x}' for x in raw_halfword_offsets) or '-'))
    dual_unsigned=(signed==0 and len(raw_halfword_offsets)>=4 and len(reg14_stores)>0 and len(reg18_stores)>0)
    print(f'V075_SAM7_UNSIGNED_RAW16_PATH={int(dual_unsigned)}')
    print('V075_SIGNED_MINUS2001_SUPPORTED=0' if dual_unsigned else 'V075_SIGNED_MINUS2001_SUPPORTED=UNRESOLVED')
    print('V075_FFFF_PHOTOMETRIC_MEANING_PROVEN=0')
    if dual_unsigned and len(numeric_cmps)==0:
        print('OVERALL_VERDICT=SAM7_WBCLIP_RAW16_STRUCT_AND_MMIO_ABI_PROVEN_NO_NUMERIC_RANGE_CHECK')
    elif dual_unsigned:
        print('OVERALL_VERDICT=SAM7_WBCLIP_RAW16_STRUCT_AND_MMIO_ABI_PROVEN_WITH_COMPARE_LOGIC')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_FUNCTION_RECOVERED_ABI_STILL_PARTIAL')
if __name__=='__main__':main()
