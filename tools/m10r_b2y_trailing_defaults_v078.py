#!/usr/bin/env python3
"""v0.78: characterize the unparsed trailing region of data_calib_B2Y.bin.

v0.76 proved the second exact RGB->YC matrix lies after the last parsed record.
This probe asks whether that tail is a coherent fallback/default bundle by
matching exact payloads from parsed small records (<=0x100 bytes) into it.
Repeated bytes alone are not treated as ownership; only exact payload matches
and their offsets are reported.
"""
from __future__ import annotations
import hashlib,importlib.util,sys
from pathlib import Path

def load_parser(repo:Path):
    p=repo/'tools'/'m10r_b2y_assets.py'
    s=importlib.util.spec_from_file_location('m10r_b2y_assets_v078',p)
    if s is None or s.loader is None:
        raise RuntimeError('parser')
    m=importlib.util.module_from_spec(s)
    sys.modules[s.name]=m
    s.loader.exec_module(m)
    return m

def main():
    if len(sys.argv)!=3:
        raise SystemExit('usage: m10r_b2y_trailing_defaults_v078.py <sections_dir> <repo_root>')
    root=Path(sys.argv[1]);repo=Path(sys.argv[2]);mod=load_parser(repo)
    p=root/'074_IMG_Calibration_Data_data_calib_B2Y.bin.bin';data=p.read_bytes();records=mod.parse_records(data)
    last=max(r.payload_offset+r.size for r in records);tail=data[last:]
    print(f'V078_TAIL=start=0x{last:x}|size=0x{len(tail):x}|sha256={hashlib.sha256(tail).hexdigest()}')
    matches=[]
    for r in records:
        if r.size<8 or r.size>0x100:continue
        blob=data[r.payload_offset:r.payload_offset+r.size]
        if not any(blob):continue
        if len(set(blob))<=2 and r.size>=0x20:continue
        pos=0
        while True:
            q=tail.find(blob,pos)
            if q<0:break
            matches.append((last+q,r.index,r.record_id,r.size,hashlib.sha256(blob).hexdigest()))
            pos=q+1
    for off,idx,rid,size,sha in sorted(matches):
        print(f'V078_MATCH=tail_off=0x{off:x}|record={idx}|id=0x{rid:x}|size=0x{size:x}|sha256={sha}')
    print(f'V078_MATCH_COUNT={len(matches)}')
    target=0x134974
    lo=max(last,target-0x80);hi=min(len(data),target+0x180)
    print(f'V078_DUPLICATE_CONTEXT=lo=0x{lo:x}|hi=0x{hi:x}|hex={data[lo:hi].hex()}')
    print('OVERALL_VERDICT=TRAILING_REGION_SMALL_RECORD_PAYLOAD_MATCHES_ENUMERATED')
if __name__=='__main__':main()
