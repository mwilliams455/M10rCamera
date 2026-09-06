#!/usr/bin/env python3
"""M10-R v0.82: test IMG-FPGA System 0x20020080 matches for real code xrefs.

v081 found ten raw byte occurrences of the WB page in section 84. This probe
separates accidental/data matches from executable ownership by requiring an
aligned Thumb or ARM PC-relative literal load that resolves to the exact word,
then checking the bounded forward code path for accesses to WBCLIP offsets
0x14/0x18.

Research only; no renderer/application code is touched.
"""
from pathlib import Path
import csv,struct,sys
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

SEC='IMG-FPGA System'
WB_PAGE=0x20020080
TARGET={0x14,0x18}


def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def find_section(root,name):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    for r in rows:
        if r['name']==name:return int(r['index']), (root/r['file']).read_bytes()
    return None,None

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
                if thumb:q=((ins.address+4)&~3)+int(op.mem.disp)
                else:q=ins.address+8+int(op.mem.disp)
                v=u32(b,q)
                if v is not None:return q,v
    except:pass
    return None

def mem(ins):
    try:
        for op in ins.operands:
            if op.type==ARM_OP_MEM:return ins.reg_name(op.mem.base),int(op.mem.disp)
    except:pass
    return None

def terminal(ins):
    mn=ins.mnemonic.lower();op=ins.op_str.lower().strip()
    if mn=='pop' and 'pc' in op:return True
    if mn=='bx' and op=='lr':return True
    if mn=='b':return True
    return False

def scan_xrefs(md,b,step,thumb,targets):
    out=[]
    for o in range(0,len(b)-4,step):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if not ins or ins.mnemonic.lower()!='ldr':continue
        lv=lit_ref(ins,b,thumb)
        if lv and lv[0] in targets and lv[1]==WB_PAGE:
            out.append((ins.address,lv[0],ins.op_str))
    return out

def bounded(md,b,a,maxbytes=0x100):
    out=[];o=a
    while o<min(len(b),a+maxbytes):
        ins=next(md.disasm(b[o:o+4],o,count=1),None)
        if not ins:break
        out.append(ins);o+=ins.size
        if terminal(ins):break
    return out

def analyze(md,b,xrefs,mode):
    owner=[]
    for a,pool,op in xrefs:
        first=next(md.disasm(b[a:a+4],a,count=1),None)
        base=first.op_str.split(',')[0].strip().lower()
        seq=bounded(md,b,a)
        touches=[]
        for ins in seq:
            m=mem(ins);mn=ins.mnemonic.lower()
            if m and m[0]==base and m[1] in TARGET and mn.startswith(('ldr','str')):
                touches.append((ins.address,mn,m[1],ins.op_str))
        print(f'V082_XREF={mode}|insn=0x{a:x}|pool=0x{pool:x}|base={base}|op={op}|touch_count={len(touches)}')
        for x in touches:print(f'V082_TOUCH={mode}|xref0x{a:x}|0x{x[0]:x}|{x[1]}|page+0x{x[2]:x}|{x[3]}')
        if touches:owner.append(a)
    return owner

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    idx,b=find_section(Path(sys.argv[1]),SEC)
    print(f'V082_SECTION_FOUND={int(b is not None)}')
    if b is None:return
    raw=occs(b,struct.pack('<I',WB_PAGE)); targets=set(raw)
    print(f'V082_SECTION_INDEX={idx}')
    print(f'V082_RAW_OCCURRENCE_COUNT={len(raw)}')
    for o in raw:print(f'V082_RAW=0x{o:x}|mod2={o%2}|mod4={o%4}')

    th=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);th.detail=True
    ar=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);ar.detail=True
    tx=scan_xrefs(th,b,2,True,targets)
    ax=scan_xrefs(ar,b,4,False,targets)
    print(f'V082_THUMB_LITERAL_XREF_COUNT={len(tx)}')
    print(f'V082_ARM_LITERAL_XREF_COUNT={len(ax)}')
    to=analyze(th,b,tx,'thumb'); ao=analyze(ar,b,ax,'arm')
    print(f'V082_WBCLIP_TARGET_OWNER_XREF_COUNT={len(to)+len(ao)}')
    print('V082_OWNER_XREFS='+(','.join([f'thumb:0x{x:x}' for x in to]+[f'arm:0x{x:x}' for x in ao]) or '-'))
    no_owner=int(not to and not ao)
    print(f'V082_IMG_FPGA_WBCLIP_OWNER_REJECTED={no_owner}')
    print('V082_HARDWARE_TRANSFER_FUNCTION_PROVEN=0')
    if no_owner:
        print('OVERALL_VERDICT=IMG_FPGA_RAW_WB_PAGE_MATCHES_HAVE_NO_PROVEN_WBCLIP_CODE_OWNER')
    else:
        print('OVERALL_VERDICT=IMG_FPGA_EXECUTABLE_WBCLIP_OWNER_CANDIDATE_REQUIRES_FOLLOWUP')
if __name__=='__main__':main()
