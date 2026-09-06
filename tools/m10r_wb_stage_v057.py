#!/usr/bin/env python3
"""M10-R v0.57 B2Y named-driver / MMIO ownership inventory.

Goal: place the proven direct WB gain block structurally without inferring pixel
order from programmer/call order.  We recover the IMG-System virtual mapping
only if two independent archived string anchors agree, enumerate exact
`drv_img_b2y_*` strings, recover Thumb ADR xrefs in the bounded B2Y driver
region, and report each named routine's MMIO literals.

This is a routing/ownership probe only.  It does NOT claim that register address
order or setter call order equals pixel processing order.
"""
from __future__ import annotations

from pathlib import Path
import csv, re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

MAP_ANCHORS = [
    (0x420A40AF, b'Gain R: %4.f | G: %4.f | B: %4.f'),
    (0x421E9CCD, b'ca9_cm_ColorManagementFinished'),
]
DRIVER_START = 0x420D2000
DRIVER_END   = 0x420D5200
MMIO_MIN = 0x20000000
MMIO_MAX = 0x2003FFFF
KEYWORDS = ('wbgain','white','gain','cc','color','tone','gamma','deknee','knee','demosaic','debayer','bayer','operation','mode','link')


def load_img(root: Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    hits=[]
    for r in rows:
        if r['name']=='IMG-System': hits.append((r,(root/r['file']).read_bytes()))
    return hits


def all_hits(data: bytes, needle: bytes):
    out=[]; p=0
    while True:
        p=data.find(needle,p)
        if p<0: return out
        out.append(p); p+=1


def derive_bias(data: bytes):
    ev=[]
    for va,s in MAP_ANCHORS:
        hs=all_hits(data,s); ev.append((va,s,hs))
    if any(len(x[2])!=1 for x in ev): return ev,None
    bs=[va-hs[0] for va,_,hs in ev]
    return ev,bs[0] if len(set(bs))==1 else None


def printable_strings(data: bytes, bias: int):
    # Exact NUL-terminated printable strings, length >= 6.
    out=[]
    for m in re.finditer(rb'[\x20-\x7e]{6,}\x00',data):
        raw=m.group()[:-1]
        if b'drv_img_b2y_' not in raw: continue
        try: txt=raw.decode('ascii')
        except UnicodeDecodeError: continue
        out.append((bias+m.start(),txt))
    return out


def adr_target(ins):
    if ins.mnemonic.lower()!='adr': return None
    # Capstone Thumb ADR immediate is printed as #imm relative to aligned PC.
    m=re.search(r'#(0x[0-9a-fA-F]+|\d+)',ins.op_str)
    if not m: return None
    imm=int(m.group(1),0)
    return ((ins.address+4)&~3)+imm


def literal_values(ins,data,bias):
    vals=[]
    try: ops=list(ins.operands)
    except Exception: return vals
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            pva=((ins.address+4)&~3)+int(op.mem.disp)
            off=pva-bias
            if 0<=off<=len(data)-4:
                vals.append((pva,struct.unpack_from('<I',data,off)[0]))
    return vals


def is_ret(ins):
    mn=ins.mnemonic.lower(); s=ins.op_str.lower()
    return (mn=='pop' and 'pc' in s) or (mn=='bx' and 'lr' in s)


def recover_function_start(insns, idx):
    # Walk back max 0x100 bytes to nearest plausible prologue. Deliberately
    # conservative; ambiguity is reported rather than guessed.
    addr=insns[idx].address
    cand=[]
    j=idx
    while j>=0 and addr-insns[j].address<=0x100:
        mn=insns[j].mnemonic.lower(); s=insns[j].op_str.lower()
        if mn=='push' and 'lr' in s: cand.append(insns[j].address)
        j-=1
    return max(cand) if cand else None


def function_slice(insns,start):
    if start is None: return []
    out=[]; active=False
    for ins in insns:
        if ins.address==start: active=True
        if not active: continue
        out.append(ins)
        if is_ret(ins): break
        if ins.address-start>0x300: break
    return out


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); imgs=load_img(root)
    print(f'V057_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG_SECTION'); return
    row,data=imgs[0]
    ev,bias=derive_bias(data)
    for va,s,hs in ev:
        print(f"V057_MAP_ANCHOR=0x{va:08x}|{s.decode('ascii')}|hits={len(hs)}|offsets={','.join(hex(x) for x in hs) or '-'}")
        for h in hs: print(f'V057_MAP_BIAS_CANDIDATE=0x{va-h:08x}')
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAPPING'); return
    print(f'V057_MAP_BIAS=0x{bias:08x}')

    strings=printable_strings(data,bias)
    print(f'V057_B2Y_DRIVER_STRINGS={len(strings)}')
    for va,txt in strings:
        mark='KEY' if any(k in txt.lower() for k in KEYWORDS) else 'OTHER'
        print(f'V057_STRING=0x{va:08x}|{mark}|{txt}')

    off0=max(0,DRIVER_START-bias); off1=min(len(data),DRIVER_END-bias)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    insns=list(md.disasm(data[off0:off1],DRIVER_START))
    smap={va:txt for va,txt in strings}
    xrefs=[]
    for i,ins in enumerate(insns):
        at=adr_target(ins)
        if at in smap:
            fs=recover_function_start(insns,i)
            xrefs.append((i,ins.address,at,smap[at],fs))
    print(f'V057_NAMED_XREFS={len(xrefs)}')

    seen=set()
    for i,xva,sva,txt,fs in xrefs:
        print(f"V057_XREF=0x{xva:08x}->0x{sva:08x}|func={('0x%08x'%fs) if fs else '-'}|{txt}")
        if fs is None or fs in seen: continue
        seen.add(fs)
        body=function_slice(insns,fs)
        names=[]; mmio=[]; lits=[]
        for ins in body:
            at=adr_target(ins)
            if at in smap: names.append(smap[at])
            for pool,val in literal_values(ins,data,bias):
                lits.append((ins.address,pool,val))
                if MMIO_MIN<=val<=MMIO_MAX: mmio.append((ins.address,val))
        key=any(any(k in n.lower() for k in KEYWORDS) for n in names)
        if not key: continue
        print(f"V057_FUNCTION=0x{fs:08x}|end={('0x%08x'%body[-1].address) if body else '-'}|names={' || '.join(names) or '-'}")
        uniq=[]
        for a,v in mmio:
            if v not in [x[1] for x in uniq]: uniq.append((a,v))
        print('V057_MMIO=' + ('|'.join(f'0x{v:08x}@0x{a:08x}' for a,v in uniq) if uniq else '-'))
        # Print compact disassembly for WB / operation / possible Bayer/CC routing only.
        nl=' '.join(names).lower()
        if any(k in nl for k in ('wbgain','operation','demosaic','debayer','bayer')):
            print(f'=== V057_BODY 0x{fs:08x} ===')
            for ins in body:
                extra=[]
                at=adr_target(ins)
                if at in smap: extra.append('STR='+smap[at])
                for pool,val in literal_values(ins,data,bias):
                    if MMIO_MIN<=val<=MMIO_MAX: extra.append(f'MMIO=0x{val:08x}')
                print(f"{ins.address:08x}: {ins.mnemonic:<9} {ins.op_str}" + ((' ; '+' ; '.join(extra)) if extra else ''))

    wb=[(fs,txt) for _,_,_,txt,fs in xrefs if 'wbgain' in txt.lower() and fs]
    bayer=[(fs,txt) for _,_,_,txt,fs in xrefs if any(k in txt.lower() for k in ('demosaic','debayer','bayer')) and fs]
    op=[(fs,txt) for _,_,_,txt,fs in xrefs if 'operation' in txt.lower() and fs]
    print(f'V057_WB_NAMED_FUNCTIONS={len(set(x[0] for x in wb))}')
    print(f'V057_BAYER_NAMED_FUNCTIONS={len(set(x[0] for x in bayer))}')
    print(f'V057_OPERATION_NAMED_FUNCTIONS={len(set(x[0] for x in op))}')
    if wb and bayer:
        print('OVERALL_VERDICT=NAMED_WB_AND_BAYER_DRIVERS_FOUND_NEEDS_ROUTING_RELATION')
    elif wb:
        print('OVERALL_VERDICT=WB_DRIVER_PROVEN_NO_NAMED_BAYER_ROUTING_EDGE')
    else:
        print('OVERALL_VERDICT=UNRESOLVED_WB_DRIVER_XREF')

if __name__=='__main__': main()
