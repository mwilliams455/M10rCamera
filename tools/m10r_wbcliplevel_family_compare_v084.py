#!/usr/bin/env python3
"""M10-R v0.84: compare WBCLIPLEVEL B2Y record ID 4 across M10 generation.

Inputs are label=sections_dir pairs produced by the same firmware decoder and
m10r_sections.py. For each camera, locate data/calib/B2Y.bin, parse the frozen
B2Y record table (header 0x14, stride 0xA90), and report every record-ID-4
payload exactly as stored plus the four driver-visible U16 values at payload
byte offsets 0,4,8,12.

This is comparative firmware evidence only. Equal raw words across camera
models support a shared B2Y encoding but do not, by themselves, prove the
peripheral transfer function or justify a renderer clamp.
"""
from __future__ import annotations
from pathlib import Path
import csv, hashlib, struct, sys

SECTION_PREFIX=4
RECORD_HEADER_OFF=0x14
RECORD_STRIDE=0xA90
RID_WBCLIP=4
EXPECTED_M10R_WORDS=(0xF82F,0xF82F,0xF82F,0xF82F)


def u32(b,o):
    if o<0 or o+4>len(b): raise ValueError(f'u32 OOB at {o:#x}')
    return struct.unpack_from('<I',b,o)[0]

def u16(b,o):
    if o<0 or o+2>len(b): raise ValueError(f'u16 OOB at {o:#x}')
    return struct.unpack_from('<H',b,o)[0]

def sha256(b): return hashlib.sha256(b).hexdigest()

def find_b2y(root:Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    matches=[]
    for r in rows:
        n=r['name']
        if n=='IMG Calibration Data/data/calib/B2Y.bin' or n.endswith('/data/calib/B2Y.bin') or n.endswith('data/calib/B2Y.bin'):
            matches.append((int(r['index']),n,root/r['file']))
    if len(matches)!=1:
        raise ValueError(f'expected one B2Y section, found {len(matches)}: {[m[:2] for m in matches]}')
    return matches[0]

def parse_id4(b:bytes):
    if len(b)<RECORD_HEADER_OFF: raise ValueError('B2Y too small')
    count=u32(b,SECTION_PREFIX+8)
    payload_base=RECORD_HEADER_OFF+count*RECORD_STRIDE
    if payload_base>len(b): raise ValueError(f'table overruns: count={count} payload_base={payload_base:#x} size={len(b):#x}')
    out=[]
    for i in range(count):
        o=RECORD_HEADER_OFF+i*RECORD_STRIDE
        if o+12>len(b): raise ValueError(f'record header OOB index={i}')
        rid=u32(b,o); rel=u32(b,o+4); size=u32(b,o+8); p=payload_base+rel
        if p<payload_base or p+size>len(b): raise ValueError(f'payload OOB index={i} rid={rid:#x} p={p:#x} size={size:#x}')
        if rid==RID_WBCLIP:
            raw=b[p:p+min(size,0x40)]
            words=None
            if size>=14:
                words=(u16(b,p+0),u16(b,p+4),u16(b,p+8),u16(b,p+12))
            out.append((i,rel,size,p,raw,words))
    return count,payload_base,out

def fmt_words(w): return '-' if w is None else ','.join(f'0x{x:04x}' for x in w)

def main():
    if len(sys.argv)<3:
        raise SystemExit(f'usage: {sys.argv[0]} LABEL=sections_dir [LABEL=sections_dir ...]')
    entries=[]
    for arg in sys.argv[1:]:
        if '=' not in arg: raise SystemExit(f'bad input {arg!r}; expected LABEL=dir')
        label,path=arg.split('=',1); root=Path(path)
        idx,name,file=find_b2y(root); b=file.read_bytes(); count,pbase,recs=parse_id4(b)
        print(f'V084_CAMERA={label}|section_index={idx}|section_name={name}|b2y_size=0x{len(b):x}|b2y_sha256={sha256(b)}|record_count={count}|payload_base=0x{pbase:x}|id4_count={len(recs)}')
        for i,rel,size,p,raw,words in recs:
            print(f'V084_ID4={label}|index={i}|rel=0x{rel:x}|size=0x{size:x}|payload=0x{p:x}|words={fmt_words(words)}|raw40={raw.hex()}')
        entries.append((label,recs))

    # Compare only cameras with one parseable ID4 record and four driver words.
    comparable=[]
    for label,recs in entries:
        if len(recs)==1 and recs[0][5] is not None:
            comparable.append((label,recs[0][5]))
    print(f'V084_COMPARABLE_CAMERA_COUNT={len(comparable)}')
    for label,w in comparable:
        print(f'V084_WORDS={label}|{fmt_words(w)}')
    unique={w for _,w in comparable}
    all_same=int(len(comparable)==len(entries) and len(entries)>=2 and len(unique)==1)
    print(f'V084_ALL_CAMERAS_SINGLE_ID4_AND_SAME_WORDS={all_same}')
    m10r=next((w for label,w in comparable if label=='M10R'),None)
    print(f'V084_M10R_EXPECTED_F82F_X4={int(m10r==EXPECTED_M10R_WORDS)}')
    all_f82=int(all_same and next(iter(unique),None)==EXPECTED_M10R_WORDS)
    print(f'V084_ALL_COMPARABLE_F82F_X4={all_f82}')
    print('V084_HARDWARE_TRANSFER_FUNCTION_PROVEN=0')
    print('V084_RENDERER_CHANGE_JUSTIFIED=0')
    if all_f82:
        print('OVERALL_VERDICT=M10_GENERATION_SHARED_WBCLIP_RAW16_F82F_X4_ENCODING_SUPPORTED')
    elif all_same:
        print('OVERALL_VERDICT=M10_GENERATION_SHARED_WBCLIP_RAW16_ENCODING_SUPPORTED_NON_F82F')
    else:
        print('OVERALL_VERDICT=M10_GENERATION_WBCLIP_RECORDS_DIFFER_OR_REQUIRE_MODEL_SPECIFIC_FOLLOWUP')
if __name__=='__main__': main()
