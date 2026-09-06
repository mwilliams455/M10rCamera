#!/usr/bin/env python3
"""M10-R v0.63b: semantic neighborhood of the direct 0x20020780 writes.

v0.63 proved that only central owner 0x42154f84 references the 0x200207xx
page and that +0c/+10/+14 have no CPU-side external readers/writers. This
revision additionally resolves ADR-backed inline diagnostic strings so that
nearby parameter selectors can be named from direct code references rather
than string proximity alone.
"""
from pathlib import Path
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

CENTRAL=0x42154f84
WBCLIP_WRAP=0x42154d58
WBCLIP_DRIVER=0x420d42dc
WB_MMIO=0x20020080
SEEDS=[WBCLIP_WRAP,0x42154350,0x42153d24,0x42154bb4,0x420d038c,0x4215440c,0x42153dec]
DRIVER_LO=0x420c0000; DRIVER_HI=0x420e8000


def litrefs(ins,data,bias):
    out=[]
    try: ops=list(ins.operands)
    except Exception: return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            p=((ins.address+4)&~3)+int(op.mem.disp); v=u32(data,p-bias)
            if v is not None: out.append((p,v))
    return out


def bt(ins):
    if ins.mnemonic.lower() not in ('bl','blx','b','b.w'): return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def adr_target(ins):
    if ins.mnemonic.lower()!='adr': return None
    parts=ins.op_str.split('#')
    if len(parts)!=2: return None
    try: imm=int(parts[1],0)
    except ValueError: return None
    return ((ins.address+4)&~3)+imm


def inline_ascii_near(data,bias,va,span=0x50):
    off=va-bias
    if not (0<=off<len(data)): return []
    out=[]
    for d in range(0,span):
        p=off+d
        if p>=len(data) or not (32<=data[p]<127): continue
        if p>off and 32<=data[p-1]<127: continue
        j=p
        while j<len(data) and 32<=data[j]<127: j+=1
        if j-p>=8:
            out.append((bias+p,data[p:j].decode('ascii','replace')))
    return out


def decode(md,data,bias,st,maxlen=0x900):
    off=st-bias; seq=[]
    if not (0<=off<len(data)): return seq,st
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        seq.append(ins); m=ins.mnemonic.lower(); o=ins.op_str.lower()
        if (m=='pop' and 'pc' in o) or (m=='bx' and o.strip()=='lr'):
            return seq,ins.address+ins.size
    return seq,(seq[-1].address+seq[-1].size if seq else st)


def ascii_near(data,bias,va,r=0x180):
    lo=max(0,va-bias-r); hi=min(len(data),va-bias+r); b=data[lo:hi]; out=[]; i=0
    while i<len(b):
        if 32<=b[i]<127:
            j=i
            while j<len(b) and 32<=b[j]<127: j+=1
            if j-i>=8:
                s=b[i:j].decode('ascii','replace')
                if any(k in s.lower() for k in ('b2y','img:','clip','limit','gain','gamma','color','colour','range','window','offset')):
                    out.append((bias+lo+i,s))
            i=j
        else: i+=1
    return out


def emit(md,data,bias,st,label):
    seq,en=decode(md,data,bias,st)
    print(f'\n=== V063B_{label} 0x{st:08x}-0x{en:08x} ===')
    calls=[]; mm=[]; strings=[]; adr_strings=[]
    for ins in seq:
        t=bt(ins)
        if ins.mnemonic.lower() in ('bl','blx') and t is not None: calls.append((ins.address,t))
        for p,v in litrefs(ins,data,bias):
            if 0x20000000<=v<0x30000000: mm.append((ins.address,p,v))
            if bias<=v<bias+len(data):
                s=read_cstr_va(data,bias,v)
                if s: strings.append((ins.address,s))
        at=adr_target(ins)
        if at is not None:
            for sva,s in inline_ascii_near(data,bias,at): adr_strings.append((ins.address,at,sva,s))
        print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}')
    for a,t in calls: print(f'V063B_CALL={label}|0x{a:08x}->0x{t:08x}')
    for a,p,v in mm: print(f'V063B_MMIO={label}|0x{a:08x}|pool=0x{p:08x}|value=0x{v:08x}')
    for a,s in strings: print(f'V063B_DIRECT_STRING={label}|0x{a:08x}|{s}')
    for a,at,sva,s in adr_strings: print(f'V063B_ADR_STRING={label}|ins=0x{a:08x}|target=0x{at:08x}|string_va=0x{sva:08x}|{s}')
    for a,s in ascii_near(data,bias,st): print(f'V063B_NEAR_STRING={label}|0x{a:08x}|{s}')
    return calls,mm,adr_strings


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    imgs=get_img_section(Path(sys.argv[1])); print(f'V063B_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1: print('OVERALL_VERDICT=B2Y_20780_SEMANTIC_NEIGHBORHOOD_UNRESOLVED'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None: print('OVERALL_VERDICT=B2Y_20780_SEMANTIC_NEIGHBORHOOD_UNRESOLVED'); return
    print(f'V063B_MAP_BIAS=0x{bias:08x}'); print(f"V063B_SECTION={row['index']}:{row['name']}")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    seq,_=decode(md,data,bias,CENTRAL)
    print('\n=== V063B_CENTRAL_SLICE ===')
    for ins in seq:
        if 0x42154fa0<=ins.address<=0x42155080: print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}')

    all_calls=[]; evidence={}
    for st in SEEDS:
        calls,mm,adr_strings=emit(md,data,bias,st,f'WRAP_{st:08x}')
        all_calls+=calls; evidence[st]=(calls,mm,adr_strings)
    drivers=sorted({t for _,t in all_calls if DRIVER_LO<=t<DRIVER_HI})
    print('V063B_DRIVER_CALLEES='+(','.join(f'0x{x:08x}' for x in drivers) or '-'))
    driver_evidence={}
    for st in drivers: driver_evidence[st]=emit(md,data,bias,st,f'DRIVER_{st:08x}')

    wcalls,wmm,wadr=evidence[WBCLIP_WRAP]
    named=any('wbcliplevel' in s.lower() for _,_,_,s in wadr)
    calls_driver=any(t==WBCLIP_DRIVER for _,t in wcalls)
    dmm=driver_evidence.get(WBCLIP_DRIVER,([],[],[]))[1]
    driver_wb_page=any(v==WB_MMIO for _,_,v in dmm)
    print(f'V063B_WBCLIP_WRAPPER_NAMED={int(named)}')
    print(f'V063B_WBCLIP_CALLS_DRIVER_420D42DC={int(calls_driver)}')
    print(f'V063B_WBCLIP_DRIVER_USES_20020080={int(driver_wb_page)}')
    if named and calls_driver and driver_wb_page:
        print('V063B_DEDICATED_WBCLIP_CONTROL_PAGE=0x20020080')
        print('V063B_20780_IS_DEDICATED_WBCLIP_CONTROL=0')
        print('OVERALL_VERDICT=B2Y_20780_NOT_DEDICATED_WBCLIPLEVEL_CONTROL')
    else:
        print('OVERALL_VERDICT=B2Y_20780_SEMANTIC_NEIGHBORHOOD_CAPTURED_NEEDS_CLASSIFICATION')

if __name__=='__main__': main()
