#!/usr/bin/env python3
"""v0.75: search M10-R firmware/calibration for YC-domain inverse/reconstruction evidence.

Evidence targets are derived only from recovered B2Y record 0x0C:
  RGB->YC matrix Q12 =
    [ 1224,  2403,   469]
    [ -691, -1357,  2048]
    [ 2048, -1715,  -333]

The mathematical inverse is approximately Q12:
    [4096,   -4,  5743]
    [4096,-1414, -2925]
    [4096, 7254,    -1]

This tool searches exact/near binary fingerprints and related strings. A near
match is reported as evidence only; it is not promoted to a firmware symbol or
pixel-flow claim without code/xref support. The post-install trigger commit is
intentional so GitHub evaluates this workflow after it exists on the branch.
"""
from __future__ import annotations
import csv, re, struct, sys
from pathlib import Path

FWD=(1224,2403,469,-691,-1357,2048,2048,-1715,-333)
INV=(4096,-4,5743,4096,-1414,-2925,4096,7254,-1)
STD=(4096,0,5743,4096,-1410,-2925,4096,7258,0)

def pack(vals): return b''.join(struct.pack('<i',v) for v in vals)

def strings(data: bytes, minlen=5):
    out=[]; i=0
    while i<len(data):
        if 32<=data[i]<127:
            j=i
            while j<len(data) and 32<=data[j]<127: j+=1
            if j-i>=minlen: out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else: i+=1
    return out

def near_inverse_windows(data: bytes):
    hits=[]
    for off in range(0,len(data)-36+1,4):
        v=struct.unpack_from('<9i',data,off)
        if not all(abs(v[k]-4096)<=64 for k in (0,3,6)): continue
        if abs(v[1])>128 or not (5200<=v[2]<=6200): continue
        if not (-1800<=v[4]<=-1000 and -3400<=v[5]<=-2400): continue
        if not (6500<=v[7]<=8000) or abs(v[8])>128: continue
        err=sum(abs(v[i]-INV[i]) for i in range(9))
        hits.append((err,off,v))
    return sorted(hits)[:50]

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: m10r_yc_inverse_trace_v075.py <sections_dir>')
    root=Path(sys.argv[1])
    rows=list(csv.DictReader((root/'sections.csv').open()))
    files=[]
    for r in rows:
        p=root/r['file']
        if p.exists(): files.append((r['name'],p))
    seen={p.resolve() for _,p in files}
    for p in root.glob('*'):
        if p.is_file() and p.name!='sections.csv' and p.resolve() not in seen:
            files.append((p.name,p))

    print('=== V075 RECOVERED MATRIX TARGETS ===')
    print('V075_FWD_Q12='+','.join(map(str,FWD)))
    print('V075_INV_MATH_Q12='+','.join(map(str,INV)))
    print('V075_INV_STD601_Q12='+','.join(map(str,STD)))

    pats={'FWD_EXACT':pack(FWD),'INV_MATH_EXACT':pack(INV),'INV_STD601_EXACT':pack(STD)}
    for label,p in files:
        data=p.read_bytes()
        for n,pat in pats.items():
            start=0
            while True:
                q=data.find(pat,start)
                if q<0: break
                print(f'V075_BINARY_MATCH={n}|section={label}|file={p.name}|off=0x{q:x}')
                start=q+1

    print('\n=== V075 NEAR INVERSE WINDOWS ===')
    total=0
    for label,p in files:
        data=p.read_bytes()
        for err,off,v in near_inverse_windows(data):
            print(f"V075_NEAR_INV=section={label}|file={p.name}|off=0x{off:x}|l1err={err}|vals={','.join(map(str,v))}")
            total+=1
    print(f'V075_NEAR_INV_COUNT={total}')

    print('\n=== V075 YC/RGB RELATED ASCII ===')
    terms=re.compile(r'(ycc|ycbcr|yuv|rgb.?2|2.?rgb|yc.?conversion|y.?blend|b2y|chroma|luma)',re.I)
    scount=0
    for label,p in files:
        data=p.read_bytes()
        for off,s in strings(data):
            if terms.search(s):
                print(f'V075_STRING=section={label}|file={p.name}|off=0x{off:x}|{s}')
                scount+=1
    print(f'V075_STRING_COUNT={scount}')
    print('\nOVERALL_VERDICT=YC_INVERSE_AND_RECONSTRUCTION_EVIDENCE_ENUMERATED_WITHOUT_FORCED_TOPOLOGY')

if __name__=='__main__': main()
