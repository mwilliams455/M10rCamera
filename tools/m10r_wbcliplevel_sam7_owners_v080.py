#!/usr/bin/env python3
"""M10-R v0.80: strict IMG-SAM7 WBCLIPLEVEL register-owner proof.

Corrects v079's evidence-pollution risk by never decoding through literal/data
pools. Starting from each genuine load of the 0x20020080 page literal, decode
only the forward executable basic-function tail and stop at POP {...,pc}, BX LR,
or the first unconditional B. Record accesses to page offsets 0x14/0x18 and
FFFF-specific logic only within those bounded paths.

Research only; no renderer/application code is touched.
"""
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

WB_PAGE=0x20020080
TARGET_OFFS={0x14,0x18}
EXPECTED_SETTER_PAGE_SITE=0x4FB3C
EXPECTED_SETTER=0x4FB32


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

def is_terminal(ins):
    mn=ins.mnemonic.lower();op=ins.op_str.lower()
    if mn=='pop' and 'pc' in op:return True
    if mn=='bx' and op.strip()=='lr':return True
    if mn=='b':return True
    return False

def nearest_push(md,b,site,back=0x180):
    out=[]
    for ins in aligned(md,b,site-back,site+1):
        if ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():out.append(ins.address)
    return out[-1] if out else None

def bounded_tail(md,b,site,max_bytes=0x180):
    out=[];o=site
    while o<min(len(b),site+max_bytes):
        ins=one(md,b,o)
        if not ins:break
        out.append(ins);o+=ins.size
        if is_terminal(ins):break
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    b=find_section(Path(sys.argv[1]),'IMG-SAM7')
    print(f'V080_SAM7_FOUND={int(b is not None)}')
    if b is None:return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    sites=[]
    for ins in aligned(md,b,0,len(b)):
        lv=pc_lit(ins,b)
        if ins.mnemonic.lower()=='ldr' and lv and lv[1]==WB_PAGE:
            sites.append(ins.address)
    print(f'V080_WB_PAGE_LITERAL_SITE_COUNT={len(sites)}')
    print('V080_WB_PAGE_LITERAL_SITES='+(','.join(f'0x{x:x}' for x in sites) or '-'))

    true_owners=[];alternate_owners=[];total_special=0
    for site in sites:
        first=one(md,b,site);base=first.op_str.split(',')[0].strip().lower()
        st=nearest_push(md,b,site)
        seq=bounded_tail(md,b,site)
        touches=[];special=[];cmps=[]
        for ins in seq:
            m=mem(ins);mn=ins.mnemonic.lower();lv=pc_lit(ins,b)
            if m and m[0]==base and m[1] in TARGET_OFFS and mn.startswith(('ldr','str')):
                touches.append((ins.address,mn,m[1],ins.op_str))
            if lv and lv[1] in (0xffff,0xffffffff):special.append((ins.address,'literal',lv[1],ins.op_str))
            if '#0xffff' in ins.op_str.lower() or '#65535' in ins.op_str.lower():special.append((ins.address,'immediate',0xffff,ins.op_str))
            if mn.startswith('mvn'):special.append((ins.address,'mvn',None,ins.op_str))
            if mn in ('cmp','cmn','tst','teq'):cmps.append((ins.address,mn,ins.op_str))
        if touches:
            true_owners.append((site,st,touches))
            if site!=EXPECTED_SETTER_PAGE_SITE:alternate_owners.append(site)
        total_special+=len(special)
        term=seq[-1] if seq else None
        print(f'V080_SITE=0x{site:x}|func={"0x%x"%st if st is not None else "-"}|base={base}|bounded_insns={len(seq)}|terminal={term.mnemonic+" "+term.op_str if term else "-"}|target_touch_count={len(touches)}|special_count={len(special)}|cmp_count={len(cmps)}')
        for x in touches:print(f'V080_TOUCH=site0x{site:x}|0x{x[0]:x}|{x[1]}|page+0x{x[2]:x}|{x[3]}')
        for x in special:print(f'V080_SPECIAL=site0x{site:x}|0x{x[0]:x}|{x[1]}|{x[3]}')
        for x in cmps:print(f'V080_COMPARE=site0x{site:x}|0x{x[0]:x}|{x[1]} {x[2]}')

    print(f'V080_TARGET_OWNER_COUNT={len(true_owners)}')
    print('V080_TARGET_OWNER_PAGE_SITES='+(','.join(f'0x{x[0]:x}' for x in true_owners) or '-'))
    print(f'V080_ALTERNATE_OWNER_COUNT={len(alternate_owners)}')
    print(f'V080_FFFF_SPECIAL_LOGIC_COUNT={total_special}')
    setter=next((x for x in true_owners if x[0]==EXPECTED_SETTER_PAGE_SITE),None)
    setter_func_ok=int(setter is not None and setter[1]==EXPECTED_SETTER)
    print(f'V080_SETTER_FUNC_MATCH={setter_func_ok}')
    only=(setter_func_ok==1 and len(true_owners)==1 and not alternate_owners and total_special==0)
    print(f'V080_WBCLIP_REG14_REG18_SINGLE_STRICT_OWNER={int(only)}')
    print('V080_FFFF_PHOTOMETRIC_MEANING_PROVEN=0')
    if only:
        print('OVERALL_VERDICT=SAM7_WBCLIP_REG14_REG18_SINGLE_STRICT_OWNER_4FB32_NO_SEPARATE_FFFF_LOGIC')
    else:
        print('OVERALL_VERDICT=SAM7_WBCLIP_OWNER_SET_REQUIRES_FOLLOWUP')
if __name__=='__main__':main()
