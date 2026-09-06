#!/usr/bin/env python3
"""M10-R v0.78: prove the IMG-SAM7 WBCLIPLEVEL setter ABI and callers.

Starts from the v077-recovered function at section-relative 0x4FB32. Verifies
its exact U16->MMIO mapping, checks for FFFF-specific logic, and enumerates all
aligned branch/call xrefs into the setter with bounded caller context.
Research only; no renderer/application code is touched.
"""
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

SETTER=0x4FB32
SETTER_END=0x4FB7A
WB_PAGE=0x20020080


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
                q=((ins.address+4)&~3)+int(op.mem.disp);v=u32(b,q)
                if v is not None:return q,v
    except:pass
    return None

def bt(ins):
    mn=ins.mnemonic.lower()
    if not (mn.startswith('b') or mn in ('cbz','cbnz')) or mn in ('bic','bics'):return None
    try:
        vals=[int(op.imm)&0xffffffff for op in ins.operands if op.type==ARM_OP_IMM]
        return vals[-1] if vals else None
    except:return None

def mem(ins):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM:return ins.reg_name(op.mem.base),int(op.mem.disp)
    except:pass
    return None

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    b=find_section(Path(sys.argv[1]),'IMG-SAM7')
    print(f'V078_SAM7_FOUND={int(b is not None)}')
    if b is None:return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    seq=list(aligned(md,b,SETTER,SETTER_END))
    print(f'V078_SETTER_START=0x{SETTER:x}')
    print(f'V078_SETTER_INSN_COUNT={len(seq)}')

    page_reg=None;loads=[];stores=[];cmps=[];ffff_refs=[]
    for ins in seq:
        lv=pc_lit(ins,b)
        if lv and lv[1]==WB_PAGE:
            page_reg=ins.op_str.split(',')[0].strip().lower()
            print(f'V078_WB_PAGE_LITERAL=0x{ins.address:x}|pool=0x{lv[0]:x}|reg={page_reg}')
        m=mem(ins);mn=ins.mnemonic.lower()
        if m and m[0]=='r4' and mn in ('ldrh','ldrsh','ldrb','ldr'):
            loads.append((ins.address,mn,m[1],ins.op_str))
        if page_reg and m and m[0]==page_reg and mn.startswith('str'):
            stores.append((ins.address,mn,m[1],ins.op_str))
        if mn in ('cmp','cmn','tst','teq'):cmps.append((ins.address,mn,ins.op_str))
        if lv and lv[1] in (0xffff,0xffffffff):ffff_refs.append((ins.address,lv[0],lv[1]))
        if '#0xffff' in ins.op_str.lower() or '#65535' in ins.op_str.lower():ffff_refs.append((ins.address,None,0xffff))
        extra=''
        if lv:extra+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
        t=bt(ins)
        if t is not None:extra+=f' ; branch=0x{t:x}'
        print(f'V078_SETTER_DISASM={ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{extra}'.rstrip())

    for x in loads:print(f'V078_INPUT_LOAD=0x{x[0]:x}|{x[1]}|r4+0x{x[2]:x}|{x[3]}')
    for x in stores:print(f'V078_MMIO_STORE=0x{x[0]:x}|{x[1]}|page+0x{x[2]:x}|{x[3]}')
    for x in cmps:print(f'V078_COMPARE=0x{x[0]:x}|{x[1]} {x[2]}')
    print(f'V078_FFFF_SPECIAL_REF_COUNT={len(ffff_refs)}')
    print(f'V078_LDRSH_COUNT={sum(1 for x in loads if x[1]=="ldrsh")}')
    offs=[x[2] for x in loads if x[1]=='ldrh']
    print('V078_LDRH_OFFSETS='+(','.join(f'0x{x:x}' for x in offs) or '-'))
    print('V078_MMIO_STORE_OFFSETS='+(','.join(f'0x{x[2]:x}' for x in stores) or '-'))

    xrefs=[]
    for ins in aligned(md,b,0,len(b)):
        t=bt(ins)
        if t==SETTER:xrefs.append((ins.address,ins.mnemonic,ins.op_str))
    print(f'V078_SETTER_XREF_COUNT={len(xrefs)}')
    for a,mn,op in xrefs:
        print(f'V078_SETTER_XREF=0x{a:x}|{mn} {op}')
        for ci in aligned(md,b,a-0x30,a+0x20):
            lv=pc_lit(ci,b);extra=''
            if lv:extra+=f' ; lit[0x{lv[0]:x}]=0x{lv[1]:08x}'
            t=bt(ci)
            if t is not None:extra+=f' ; branch=0x{t:x}'
            print(f'V078_CALLER_CONTEXT={ci.address:08x}: {ci.mnemonic:<8} {ci.op_str}{extra}'.rstrip())

    exact=(offs==[0,2,4,6] and sum(1 for x in loads if x[1]=='ldrsh')==0 and any(x[2]==0x14 for x in stores) and any(x[2]==0x18 for x in stores) and len(cmps)==0 and len(ffff_refs)==0)
    print(f'V078_DIRECT_U16_X4_NO_SPECIAL_FFFF_LOGIC={int(exact)}')
    print('V078_FFFF_PHOTOMETRIC_MEANING_PROVEN=0')
    if exact:
        print('OVERALL_VERDICT=SAM7_WBCLIP_SETTER_DIRECT_U16_X4_TO_MMIO_PROVEN_CALLERS_ENUMERATED')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_SETTER_NEEDS_FOLLOWUP')
if __name__=='__main__':main()
