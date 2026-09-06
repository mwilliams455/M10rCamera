#!/usr/bin/env python3
"""M10-R v0.69: reconcile WbClip strings and classify shared WB-page owners.
Research only; no renderer/application changes.
"""
from __future__ import annotations
from pathlib import Path
import re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

WB_PAGE=0x20020080
OWNERS=[
    (0x420d2448,0x260,'LOW_OWNER_A'),
    (0x420d35e0,0x120,'LOW_OWNER_B'),
    (0x420d42dc,0xa0,'WBCLIP_DRIVER'),
    (0x420d4380,0x100,'DIRECT_WB_DRIVER'),
    (0x42152f8c,0x500,'CENTRAL_PAGE_OWNER_A'),
    (0x421536bc,0x380,'CENTRAL_PAGE_OWNER_B'),
]
TARGETS=[b'WbClipEn',b'WbClipCcd',b'WBCLIPLEVEL']

def parse_sections(raw:bytes):
    n=u32(raw,0x14); ts=u32(raw,0x18); to=u32(raw,0x1c)
    es=ts//n; body=to+ts; out=[]
    for i in range(n):
        e=to+i*es; ent=raw[e:e+es]
        rel=u32(ent,0x18); sz=u32(ent,0x1c); base=u32(ent,0x24)
        name=ent[52:132].split(b'\0')[0].decode('latin1','replace') or 'unnamed'
        out.append((i,name,body+rel,sz,base))
    return body,out

def map_hit(off:int,secs):
    for i,n,a,s,b in secs:
        if a<=off<a+s: return i,n,off-a,b,(b+off-a)&0xffffffff
    return None

def ascii_near(data:bytes,off:int,r=0x100):
    a=max(0,off-r); b=min(len(data),off+r); out=[]
    for m in re.finditer(rb'[ -~]{4,}',data[a:b]):
        s=m.group().decode('ascii','replace')
        if len(s)<=140: out.append((a+m.start(),s))
    return out

def litval(ins,data,bias):
    try: ops=list(ins.operands)
    except Exception: return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            p=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(data,p-bias)
            if v is not None:return p,v
    return None

def decode(md,data,bias,st,maxlen):
    off=st-bias; out=[]
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        out.append(ins)
        m=ins.mnemonic.lower(); o=ins.op_str.lower()
        if (m=='pop' and 'pc' in o) or (m=='bx' and o.strip()=='lr'): break
    return out

def owner_summary(md,data,bias,st,maxlen,tag):
    seq=decode(md,data,bias,st,maxlen); page_loads=[]; strings=[]; mem=[]
    page_regs=set()
    print(f'V069_OWNER_BEGIN={tag}|0x{st:08x}|insns={len(seq)}')
    for ins in seq:
        lv=litval(ins,data,bias)
        if lv:
            p,v=lv
            if v==WB_PAGE:
                dst=ins.op_str.split(',')[0].strip().lower()
                page_regs.add(dst); page_loads.append((ins.address,dst,p))
                print(f'V069_PAGE_LOAD={tag}|0x{ins.address:08x}|reg={dst}|pool=0x{p:08x}')
            if 0x42000000<=v<0x43000000:
                s=read_cstr_va(data,bias,v)
                if s and len(s)<=180:
                    strings.append((ins.address,v,s))
        op=ins.op_str.lower().replace(' ','')
        if ins.mnemonic.lower().startswith(('ldr','str')) and '[' in op:
            for r in list(page_regs):
                if f'[{r}' in op:
                    mem.append((ins.address,ins.mnemonic,ins.op_str))
                    print(f'V069_PAGE_MEM={tag}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')
    for a,v,s in strings:
        print(f'V069_OWNER_STRING={tag}|0x{a:08x}->0x{v:08x}|{s}')
    print(f'V069_OWNER_SUMMARY={tag}|page_loads={len(page_loads)}|page_mem={len(mem)}|strings={len(strings)}')


def scan_blob(label:str,b:bytes,secs=None):
    low=b.lower()
    for t in TARGETS:
        variants=[(t,'ascii'),(t.decode().encode('utf-16le'),'utf16le')]
        for needle,enc in variants:
            hits=[]; p=0
            while True:
                p=(low if enc=='ascii' else b).find(needle.lower() if enc=='ascii' else needle,p)
                if p<0:break
                hits.append(p);p+=1
            key=t.decode().upper()
            print(f'V069_{label}_{key}_{enc.upper()}_HITS={len(hits)}')
            for h in hits[:32]:
                m=map_hit(h,secs) if secs else None
                if m:
                    i,n,rel,base,va=m
                    print(f'V069_{label}_{key}=off=0x{h:x}|section={i}:{n}|rel=0x{rel:x}|base=0x{base:08x}|va=0x{va:08x}|enc={enc}')
                else:
                    print(f'V069_{label}_{key}=off=0x{h:x}|section=NONE|enc={enc}')
                if enc=='ascii':
                    for no,s in ascii_near(b,h):
                        if abs(no-h)<=0x80:
                            print(f'V069_{label}_{key}_NEAR=rel={no-h:+#x}|{s}')
    # broader bounded inventory catches spelling/case variants omitted above
    pats=[]
    for m in re.finditer(rb'(?i)[A-Za-z0-9_./:-]{0,40}Wb[A-Za-z0-9_./:-]*Clip[A-Za-z0-9_./:-]{0,40}',b):
        s=m.group().decode('ascii','replace')
        if s not in pats:pats.append(s)
    print(f'V069_{label}_WBCLIP_FAMILY_COUNT={len(pats)}')
    for s in pats[:64]:print(f'V069_{label}_WBCLIP_FAMILY={s}')


def main():
    if len(sys.argv)!=4:raise SystemExit(f'usage: {sys.argv[0]} unpacked.bin original.FW sections_dir')
    raw=Path(sys.argv[1]).read_bytes(); fw=Path(sys.argv[2]).read_bytes(); root=Path(sys.argv[3])
    body,secs=parse_sections(raw)
    print(f'V069_UNPACKED_SIZE=0x{len(raw):x}|SECTION_BODY=0x{body:x}|SECTIONS={len(secs)}')
    scan_blob('UNPACKED',raw,secs)
    scan_blob('COMPRESSED_FW',fw,None)
    imgs=get_img_section(root)
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG');return
    _,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAP');return
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    for st,ml,tag in OWNERS:owner_summary(md,data,bias,st,ml,tag)
    print('OVERALL_VERDICT=WB_PAGE_OWNER_AND_RAW_STRING_RECONCILIATION_COMPLETE')
if __name__=='__main__':main()
