#!/usr/bin/env python3
"""M10-R v0.83: test 0x20020000 base aliases for hidden WBCLIP owners.

v081 showed many raw 0x20020000 occurrences in IMG-FPGA System and two in
CTRL-System. A hidden owner could theoretically load that broader base and
address WBCLIP as +0x94/+0x98 (or add +0x80 then use +0x14/+0x18). Require a
real Thumb/ARM literal xref and perform small forward alias tracking before
classifying any WBCLIP access.

Research only; no renderer/application code is touched.
"""
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC

SECS=['IMG-FPGA System','CTRL-System']
BASE=0x20020000
TARGET_ABS={0x94,0x98}


def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def load_sections(root):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    out={}
    for r in rows:
        if r['name'] in SECS:out[r['name']]=(int(r['index']),(root/r['file']).read_bytes())
    return out

def occs(b,needle):
    out=[];p=0
    while True:
        q=b.find(needle,p)
        if q<0:return out
        out.append(q);p=q+1

def lit_ref(ins,b,thumb):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                q=(((ins.address+4)&~3) if thumb else ins.address+8)+int(op.mem.disp)
                v=u32(b,q)
                if v is not None:return q,v
    except:pass
    return None

def terminal(ins):
    mn=ins.mnemonic.lower();op=ins.op_str.lower().strip()
    return (mn=='pop' and 'pc' in op) or (mn=='bx' and op=='lr') or mn=='b'

def bounded(md,b,a,maxbytes=0x140):
    out=[];o=a
    while o<min(len(b),a+maxbytes):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if not ins:break
        out.append(ins);o+=ins.size
        if terminal(ins):break
    return out

def scan_xrefs(md,b,step,thumb,targets):
    out=[]
    for o in range(0,len(b)-4,step):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if not ins or ins.mnemonic.lower()!='ldr':continue
        lv=lit_ref(ins,b,thumb)
        if lv and lv[0] in targets and lv[1]==BASE:
            out.append((ins.address,lv[0],ins))
    return out

def first_mem(ins):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM:return ins.reg_name(op.mem.base),int(op.mem.disp)
    except:pass
    return None

def update_alias(ins,aliases):
    mn=ins.mnemonic.lower()
    try: ops=list(ins.operands)
    except:return
    if mn in ('mov','movs') and len(ops)>=2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_REG:
        d=ins.reg_name(ops[0].reg);s=ins.reg_name(ops[1].reg)
        if s in aliases:aliases[d]=aliases[s]
        elif d in aliases:aliases.pop(d,None)
        return
    if mn in ('add','adds','sub','subs'):
        if len(ops)>=3 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM:
            d=ins.reg_name(ops[0].reg);s=ins.reg_name(ops[1].reg);imm=int(ops[2].imm)
            if s in aliases:aliases[d]=aliases[s]+(imm if mn.startswith('add') else -imm)
            elif d in aliases:aliases.pop(d,None)
            return
        if len(ops)>=2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_IMM:
            d=ins.reg_name(ops[0].reg);imm=int(ops[1].imm)
            if d in aliases:aliases[d]+=imm if mn.startswith('add') else -imm
            return
    # Conservative clobber for ordinary destination-register writers.
    if ops and ops[0].type==ARM_OP_REG and mn not in ('cmp','cmn','tst','teq','str','strh','strb'):
        d=ins.reg_name(ops[0].reg)
        if d in aliases and mn not in ('ldr',):aliases.pop(d,None)

def analyze(md,b,xrefs,mode,sec):
    owners=[]
    for a,pool,first in xrefs:
        dest=first.op_str.split(',')[0].strip().lower();aliases={dest:0};touch=[]
        seq=bounded(md,b,a)
        for n,ins in enumerate(seq):
            if n>0:update_alias(ins,aliases)
            m=first_mem(ins);mn=ins.mnemonic.lower()
            if m and m[0] in aliases and mn.startswith(('ldr','str')):
                eff=aliases[m[0]]+m[1]
                if eff in TARGET_ABS:touch.append((ins.address,mn,m[0],aliases[m[0]],m[1],eff,ins.op_str))
        print(f'V083_XREF={sec}|{mode}|insn=0x{a:x}|pool=0x{pool:x}|dest={dest}|touch_count={len(touch)}')
        for x in touch:print(f'V083_TOUCH={sec}|{mode}|xref0x{a:x}|0x{x[0]:x}|{x[1]}|alias={x[2]}+0x{x[3]:x}|mem=0x{x[4]:x}|effective=0x{x[5]:x}|{x[6]}')
        if touch:owners.append(a)
    return owners

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]);secs=load_sections(root)
    th=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);th.detail=True
    ar=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);ar.detail=True
    total_owners=[]
    for sec in SECS:
        item=secs.get(sec);print(f'V083_SECTION_FOUND={sec}|{int(item is not None)}')
        if item is None:continue
        idx,b=item;raw=occs(b,struct.pack('<I',BASE));targets=set(raw)
        tx=scan_xrefs(th,b,2,True,targets);ax=scan_xrefs(ar,b,4,False,targets)
        print(f'V083_SECTION={sec}|index={idx}|raw_base_count={len(raw)}|thumb_xrefs={len(tx)}|arm_xrefs={len(ax)}')
        to=analyze(th,b,tx,'thumb',sec);ao=analyze(ar,b,ax,'arm',sec)
        for x in to:total_owners.append((sec,'thumb',x))
        for x in ao:total_owners.append((sec,'arm',x))
    print(f'V083_HIDDEN_WBCLIP_OWNER_COUNT={len(total_owners)}')
    for s,m,a in total_owners:print(f'V083_HIDDEN_OWNER={s}|{m}|0x{a:x}')
    rejected=int(len(total_owners)==0)
    print(f'V083_BASE_ALIAS_HIDDEN_OWNER_REJECTED={rejected}')
    print('V083_HARDWARE_TRANSFER_FUNCTION_PROVEN=0')
    if rejected:
        print('OVERALL_VERDICT=NO_FPGA_OR_CTRL_WBCLIP_OWNER_VIA_20020000_BASE_ALIAS')
    else:
        print('OVERALL_VERDICT=BASE_ALIAS_WBCLIP_OWNER_CANDIDATE_REQUIRES_FOLLOWUP')
if __name__=='__main__':main()
