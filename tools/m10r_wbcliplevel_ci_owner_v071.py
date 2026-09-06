#!/usr/bin/env python3
"""M10-R v0.71: locate CI:Im_B2Y_Set_WB_Clip_Level in the unpacked image.
Research-only; no renderer/application changes.
"""
from __future__ import annotations
from pathlib import Path
import csv, re, struct, sys

TARGET=b'CI:Im_B2Y_Set_WB_Clip_Level'
PREFIX=b'CI:Im_B2Y_Set_'

def u32(b,o):
    return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def parse_layout(raw:bytes):
    n=u32(raw,0x14); ts=u32(raw,0x18); to=u32(raw,0x1c)
    if not n or ts%n: raise ValueError('bad section table')
    es=ts//n; body=to+ts; out=[]
    for i in range(n):
        e=to+i*es; ent=raw[e:e+es]
        rel=u32(ent,0x18); sz=u32(ent,0x1c); kind=u32(ent,0x20); base=u32(ent,0x24); aux=u32(ent,0x28)
        name=ent[52:132].split(b'\0')[0].decode('latin1','replace') or 'unnamed'
        out.append(dict(index=i,name=name,start=body+rel,end=body+rel+sz,size=sz,rel=rel,kind=kind,base=base,aux=aux))
    return to,ts,body,out

def findall(b:bytes,n:bytes):
    out=[]; p=0
    while True:
        p=b.find(n,p)
        if p<0:return out
        out.append(p); p+=1

def cstrings_near(b:bytes,off:int,r=0x300):
    a=max(0,off-r); z=min(len(b),off+r); out=[]
    for m in re.finditer(rb'[ -~]{5,}',b[a:z]):
        s=m.group().decode('ascii','replace')
        if len(s)<=200: out.append((a+m.start(),s))
    return out

def owner(off,secs):
    for s in secs:
        if s['start']<=off<s['end']: return s
    return None

def nearest(off,secs):
    prev=max((s for s in secs if s['end']<=off),key=lambda s:s['end'],default=None)
    nxt=min((s for s in secs if s['start']>off),key=lambda s:s['start'],default=None)
    return prev,nxt

def section_family(root:Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    total=[]
    for r in rows:
        d=(root/r['file']).read_bytes()
        for p in findall(d,PREFIX):
            e=d.find(b'\0',p,min(len(d),p+180)); e=len(d) if e<0 else e
            raw=d[p:e]
            try:s=raw.decode('ascii')
            except:s=raw.decode('latin1','replace')
            total.append((r,p,s))
    return total

def main():
    if len(sys.argv)!=3: raise SystemExit(f'usage: {sys.argv[0]} unpacked.bin sections_dir')
    raw=Path(sys.argv[1]).read_bytes(); root=Path(sys.argv[2])
    to,ts,body,secs=parse_layout(raw)
    print(f'V071_UNPACKED_SIZE=0x{len(raw):x}')
    print(f'V071_SECTION_TABLE=off=0x{to:x}|size=0x{ts:x}|body=0x{body:x}|count={len(secs)}')
    hits=findall(raw,TARGET)
    print(f'V071_TARGET_UNPACKED_HITS={len(hits)}')
    for k,h in enumerate(hits):
        s=owner(h,secs)
        if s:
            print(f'V071_TARGET_OWNER={k}|off=0x{h:x}|section={s["index"]}:{s["name"]}|section_rel=0x{h-s["start"]:x}|kind=0x{s["kind"]:08x}|base=0x{s["base"]:08x}|aux=0x{s["aux"]:08x}')
        else:
            p,n=nearest(h,secs)
            print(f'V071_TARGET_OWNER={k}|off=0x{h:x}|section=NONE')
            if p: print(f'V071_PREV_SECTION={k}|{p["index"]}:{p["name"]}|end=0x{p["end"]:x}|distance=0x{h-p["end"]:x}')
            if n: print(f'V071_NEXT_SECTION={k}|{n["index"]}:{n["name"]}|start=0x{n["start"]:x}|distance=0x{n["start"]-h:x}')
        a=max(0,h-0x60); z=min(len(raw),h+len(TARGET)+0x60)
        print(f'V071_TARGET_HEX={k}|base=0x{a:x}|{raw[a:z].hex()}')
        for no,text in cstrings_near(raw,h):
            if abs(no-h)<=0x240:
                print(f'V071_TARGET_NEAR={k}|rel={no-h:+#x}|off=0x{no:x}|{text}')

    fam=section_family(root)
    print(f'V071_EXTRACTED_CI_B2Y_SET_FAMILY={len(fam)}')
    for r,p,s in fam:
        print(f'V071_EXTRACTED_CI_STRING=section={r["index"]}:{r["name"]}|rel=0x{p:x}|{s}')

    # Whole-unpacked family inventory, with owner for each occurrence.
    uf=[]
    for p in findall(raw,PREFIX):
        e=raw.find(b'\0',p,min(len(raw),p+180)); e=len(raw) if e<0 else e
        try:s=raw[p:e].decode('ascii')
        except:s=raw[p:e].decode('latin1','replace')
        uf.append((p,s,owner(p,secs)))
    print(f'V071_UNPACKED_CI_B2Y_SET_FAMILY={len(uf)}')
    for p,s,o in uf:
        own=f'{o["index"]}:{o["name"]}' if o else 'NONE'
        print(f'V071_UNPACKED_CI_STRING=off=0x{p:x}|owner={own}|{s}')

    if hits and all(owner(h,secs) is not None for h in hits):
        print('OVERALL_VERDICT=CI_WBCLIP_OWNING_SECTION_PROVEN')
    elif hits:
        print('OVERALL_VERDICT=CI_WBCLIP_EXISTS_OUTSIDE_EXTRACTED_SECTION_PAYLOADS')
    else:
        print('OVERALL_VERDICT=CI_WBCLIP_STRING_NOT_FOUND_IN_VERIFIED_UNPACKED_IMAGE')
if __name__=='__main__': main()
