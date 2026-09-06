#!/usr/bin/env python3
"""M10-R v0.57 B2Y named-driver / MMIO ownership inventory.

Goal: place the proven direct WB gain block structurally without inferring pixel
order from programmer/call order. We recover IMG-System virtual mapping only if
two independent archived string anchors agree, enumerate exact `drv_img_b2y_*`
strings, then recover Thumb ADR xrefs with candidate-seeded local decoding.

Why candidate seeded: a long linear Thumb disassembly can terminate on embedded
data and falsely miss later routines. Each string is therefore searched only in
a bounded backwards window, and a candidate function start is accepted only if
sequential decoding from a plausible PUSH/LR prologue reaches the exact xref.

This is a routing/ownership probe only. Register address order and setter call
order are NOT treated as pixel processing order.
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
XREF_BACK = 0x180
FUNC_BACK = 0x100
FUNC_MAX  = 0x380
MMIO_MIN = 0x20000000
MMIO_MAX = 0x2003FFFF
KEYWORDS = ('wbgain','white','gain','cc','color','tone','gamma','deknee','knee','demosaic','debayer','bayer','operation','mode','link')


def load_img(root: Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    return [(r,(root/r['file']).read_bytes()) for r in rows if r['name']=='IMG-System']


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


def decode_one(md,data,bias,va):
    off=va-bias
    if not (0<=off<len(data)-2): return None
    got=list(md.disasm(data[off:off+4],va,count=1))
    return got[0] if got else None


def seeded_xrefs(md,data,bias,sva):
    out=[]
    lo=max(bias,(sva-XREF_BACK)&~1)
    hi=sva&~1
    for va in range(lo,hi,2):
        ins=decode_one(md,data,bias,va)
        if ins and adr_target(ins)==sva:
            out.append(va)
    return out


def sequential(md,data,bias,start,limit):
    off=start-bias
    if not (0<=off<len(data)): return []
    return list(md.disasm(data[off:min(len(data),off+limit)],start))


def recover_function(md,data,bias,xva):
    # Candidate PUSH/LR prologues are independently detected, then verified by
    # sequential decode reaching the exact ADR xref. Nearest valid wins.
    cand=[]
    lo=max(bias,(xva-FUNC_BACK)&~1)
    for va in range(lo,xva+1,2):
        ins=decode_one(md,data,bias,va)
        if ins and ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():
            cand.append(va)
    valid=[]
    for fs in cand:
        body=sequential(md,data,bias,fs,FUNC_MAX)
        addrs={i.address for i in body}
        if xva not in addrs: continue
        # xref must occur before first return.
        first_ret=next((i.address for i in body if is_ret(i)),None)
        if first_ret is not None and xva>first_ret: continue
        valid.append((fs,body))
    if not valid: return None,[]
    fs,body=max(valid,key=lambda x:x[0])
    trimmed=[]
    for ins in body:
        trimmed.append(ins)
        if is_ret(ins): break
        if ins.address-fs>FUNC_MAX: break
    return fs,trimmed


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

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    xrefs=[]
    for sva,txt in strings:
        for xva in seeded_xrefs(md,data,bias,sva):
            fs,body=recover_function(md,data,bias,xva)
            xrefs.append((xva,sva,txt,fs,body))
    print(f'V057_NAMED_XREFS={len(xrefs)}')

    seen=set()
    for xva,sva,txt,fs,body in sorted(xrefs):
        print(f"V057_XREF=0x{xva:08x}->0x{sva:08x}|func={('0x%08x'%fs) if fs else '-'}|{txt}")
        if fs is None or fs in seen: continue
        seen.add(fs)
        names=[]; mmio=[]
        for ins in body:
            at=adr_target(ins)
            if at is not None:
                for ssva,stxt in strings:
                    if at==ssva: names.append(stxt)
            for pool,val in literal_values(ins,data,bias):
                if MMIO_MIN<=val<=MMIO_MAX: mmio.append((ins.address,val))
        key=any(any(k in n.lower() for k in KEYWORDS) for n in names)
        if not key: continue
        print(f"V057_FUNCTION=0x{fs:08x}|end={('0x%08x'%body[-1].address) if body else '-'}|names={' || '.join(names) or '-'}")
        uniq=[]
        for a,v in mmio:
            if v not in [x[1] for x in uniq]: uniq.append((a,v))
        print('V057_MMIO=' + ('|'.join(f'0x{v:08x}@0x{a:08x}' for a,v in uniq) if uniq else '-'))
        nl=' '.join(names).lower()
        if any(k in nl for k in ('wbgain','operation','demosaic','debayer','bayer')):
            print(f'=== V057_BODY 0x{fs:08x} ===')
            for ins in body:
                extra=[]
                at=adr_target(ins)
                for ssva,stxt in strings:
                    if at==ssva: extra.append('STR='+stxt)
                for _,val in literal_values(ins,data,bias):
                    if MMIO_MIN<=val<=MMIO_MAX: extra.append(f'MMIO=0x{val:08x}')
                print(f"{ins.address:08x}: {ins.mnemonic:<9} {ins.op_str}" + ((' ; '+' ; '.join(extra)) if extra else ''))

    wb=[(fs,txt) for _,_,txt,fs,_ in xrefs if 'wbgain' in txt.lower() and fs]
    bayer=[(fs,txt) for _,_,txt,fs,_ in xrefs if any(k in txt.lower() for k in ('demosaic','debayer','bayer')) and fs]
    op=[(fs,txt) for _,_,txt,fs,_ in xrefs if 'operation' in txt.lower() and fs]
    tone=[(fs,txt) for _,_,txt,fs,_ in xrefs if 'tone' in txt.lower() and fs]
    gamma=[(fs,txt) for _,_,txt,fs,_ in xrefs if 'gamma' in txt.lower() and fs]
    print(f'V057_WB_NAMED_FUNCTIONS={len(set(x[0] for x in wb))}')
    print(f'V057_BAYER_NAMED_FUNCTIONS={len(set(x[0] for x in bayer))}')
    print(f'V057_OPERATION_NAMED_FUNCTIONS={len(set(x[0] for x in op))}')
    print(f'V057_TONE_NAMED_FUNCTIONS={len(set(x[0] for x in tone))}')
    print(f'V057_GAMMA_NAMED_FUNCTIONS={len(set(x[0] for x in gamma))}')
    if wb and bayer:
        print('OVERALL_VERDICT=NAMED_WB_AND_BAYER_DRIVERS_FOUND_NEEDS_ROUTING_RELATION')
    elif wb:
        print('OVERALL_VERDICT=WB_DRIVER_PROVEN_NO_NAMED_BAYER_ROUTING_EDGE')
    else:
        print('OVERALL_VERDICT=UNRESOLVED_WB_DRIVER_XREF')

if __name__=='__main__': main()
