#!/usr/bin/env python3
"""M10-R v0.79: census IMG-SAM7 owners of WBCLIPLEVEL registers.

Enumerates code paths that load the 0x20020080 B2Y page and then touch offsets
0x14/0x18. Looks specifically for alternate writers, reads, FFFF literals,
MVN/all-ones construction, and comparison logic that could imply bypass/reset
semantics outside the v078 setter. Research only.
"""
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

WB_PAGE=0x20020080
TARGET_OFFS={0x14,0x18}


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

def mem(ins):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM:return ins.reg_name(op.mem.base),int(op.mem.disp)
    except:pass
    return None

def nearest_func_start(md,b,site,back=0x300):
    pushes=[]
    for ins in aligned(md,b,site-back,site+1):
        if ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():pushes.append(ins.address)
    return pushes[-1] if pushes else None

def decode_func(md,b,st,maxlen=0x300):
    out=[];o=st
    while o<min(len(b),st+maxlen):
        ins=one(md,b,o)
        if not ins:o+=2;continue
        out.append(ins);o+=ins.size
        mn=ins.mnemonic.lower()
        if mn=='pop' and 'pc' in ins.op_str.lower():break
        if mn=='bx' and ins.op_str.strip().lower()=='lr':break
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    b=find_section(Path(sys.argv[1]),'IMG-SAM7')
    print(f'V079_SAM7_FOUND={int(b is not None)}')
    if b is None:return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    page_sites=[]
    for ins in aligned(md,b,0,len(b)):
        lv=pc_lit(ins,b)
        if ins.mnemonic.lower()=='ldr' and lv and lv[1]==WB_PAGE:
            page_sites.append(ins.address)
    print(f'V079_WB_PAGE_LITERAL_SITE_COUNT={len(page_sites)}')
    print('V079_WB_PAGE_LITERAL_SITES='+(','.join(f'0x{x:x}' for x in page_sites) or '-'))

    funcs={}
    for s in page_sites:
        st=nearest_func_start(md,b,s)
        if st is not None:funcs.setdefault(st,set()).add(s)
    print(f'V079_CANDIDATE_FUNC_COUNT={len(funcs)}')

    owners=[]
    for st,sites in sorted(funcs.items()):
        seq=decode_func(md,b,st)
        page_regs=set();touches=[];ffff=[];cmps=[];allones=[]
        for ins in seq:
            lv=pc_lit(ins,b)
            if lv and lv[1]==WB_PAGE:
                page_regs.add(ins.op_str.split(',')[0].strip().lower())
            m=mem(ins);mn=ins.mnemonic.lower()
            if m and m[0] in page_regs and m[1] in TARGET_OFFS and mn.startswith(('ldr','str')):
                touches.append((ins.address,mn,m[1],ins.op_str))
            if lv and lv[1] in (0xffff,0xffffffff):ffff.append((ins.address,lv[0],lv[1],ins.op_str))
            if '#0xffff' in ins.op_str.lower() or '#65535' in ins.op_str.lower():ffff.append((ins.address,None,0xffff,ins.op_str))
            if mn in ('cmp','cmn','tst','teq'):cmps.append((ins.address,mn,ins.op_str))
            if mn.startswith('mvn') or (mn.startswith('mov') and '#-1' in ins.op_str.replace(' ','')):
                allones.append((ins.address,mn,ins.op_str))
        if not touches:continue
        owners.append(st)
        print(f'V079_OWNER_FUNC=0x{st:x}|page_sites={",".join(f"0x{x:x}" for x in sorted(sites))}|touch_count={len(touches)}')
        for x in touches:print(f'V079_TOUCH=func0x{st:x}|0x{x[0]:x}|{x[1]}|page+0x{x[2]:x}|{x[3]}')
        for x in ffff:print(f'V079_FFFF_REF=func0x{st:x}|0x{x[0]:x}|{x[3]}')
        for x in allones:print(f'V079_ALLONES_BUILD=func0x{st:x}|0x{x[0]:x}|{x[1]} {x[2]}')
        for x in cmps:print(f'V079_COMPARE=func0x{st:x}|0x{x[0]:x}|{x[1]} {x[2]}')
        for ins in seq:
            print(f'V079_OWNER_DISASM=func0x{st:x}|{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}')

    print('V079_OWNER_FUNCS='+(','.join(f'0x{x:x}' for x in owners) or '-'))
    setter_only=(owners==[0x4fb32])
    print(f'V079_WBCLIP_MMIO_OWNER_SETTER_ONLY={int(setter_only)}')
    print('V079_FFFF_PHOTOMETRIC_MEANING_PROVEN=0')
    if setter_only:
        print('OVERALL_VERDICT=SAM7_WBCLIP_REG14_REG18_ONLY_RECOVERED_SETTER_OWNER_NO_SEPARATE_FFFF_LOGIC')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_ADDITIONAL_OWNER_REQUIRES_REVIEW')
if __name__=='__main__':main()
