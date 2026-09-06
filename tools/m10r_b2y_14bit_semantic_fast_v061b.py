#!/usr/bin/env python3
from pathlib import Path
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

XREFS=[0x420d357a,0x420d3598,0x420d35b8]
SEARCH_BACK=0x300
SEARCH_FWD=0x120

def refs(ins,data,bias):
    out=[]
    try: ops=list(ins.operands)
    except: return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            p=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(data,p-bias)
            if v is not None: out.append((p,v))
    return out

def nearest_push(md,data,bias,x):
    c=[]
    for va in range(x-SEARCH_BACK,x,2):
        off=va-bias
        ins=next(md.disasm(data[off:off+4],va,count=1),None)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower(): c.append(va)
    return c[-1] if c else None

def main():
    root=Path(sys.argv[1]); imgs=get_img_section(root)
    if len(imgs)!=1: print('OVERALL_VERDICT=UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None: print('OVERALL_VERDICT=UNRESOLVED_MAP'); return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    print(f'V061B_MAP_BIAS=0x{bias:08x}')
    starts=[]
    for x in XREFS:
        st=nearest_push(md,data,bias,x)
        print(f'V061B_XREF=0x{x:08x}|nearest_push={"-" if st is None else f"0x{st:08x}"}')
        if st is not None and st not in starts: starts.append(st)
    any_mmio=False
    for st in starts:
        print(f'=== V061B_FUNCTION_CANDIDATE 0x{st:08x} ===')
        off=st-bias
        for ins in md.disasm(data[off:off+0x500],st):
            rr=refs(ins,data,bias)
            tail=''
            if rr:
                ps=[]
                for p,v in rr:
                    cls='MMIO' if 0x20000000<=v<0x30000000 else 'RAM' if 0x40000000<=v<0x50000000 else 'VALUE'
                    if cls=='MMIO': any_mmio=True
                    s=read_cstr_va(data,bias,v) if 0x42000000<=v<0x43000000 else None
                    ps.append(f'pool=0x{p:08x}->0x{v:08x}:{cls}:str={s!r}')
                tail=' ; '+' ; '.join(ps)
            print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{tail}'.rstrip())
            if ins.mnemonic.lower()=='pop' and 'pc' in ins.op_str.lower(): break
        print('V061B_NEAR_STRINGS')
        lo=max(0,st-bias-0x600); hi=min(len(data),st-bias+0x900); b=data[lo:hi]
        i=0
        while i<len(b):
            if 32<=b[i]<127:
                j=i
                while j<len(b) and 32<=b[j]<127: j+=1
                if j-i>=10:
                    print(f'  0x{bias+lo+i:08x}: '+b[i:j].decode('ascii','replace'))
                i=j
            else: i+=1
    print('OVERALL_VERDICT=' + ('EXPLICIT_MMIO_FUNCTION_CONTEXT_RECOVERED' if any_mmio else 'NO_MMIO_CONTEXT_RECOVERED'))
if __name__=='__main__': main()
