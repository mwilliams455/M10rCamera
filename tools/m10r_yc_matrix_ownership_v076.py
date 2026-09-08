#!/usr/bin/env python3
"""v0.76: map every exact recovered RGB->YC matrix occurrence to B2Y records.

This answers whether the second matrix fingerprint found by v0.75 belongs to a
live calibration record or to unreferenced/trailing auxiliary data. No pixel
stage ordering is inferred from file layout.
"""
from __future__ import annotations
import importlib.util, struct, sys
from pathlib import Path

FWD=(1224,2403,469,-691,-1357,2048,2048,-1715,-333)
PAT=b''.join(struct.pack('<i',x) for x in FWD)

def load_parser(repo: Path):
    p=repo/'tools'/'m10r_b2y_assets.py'
    spec=importlib.util.spec_from_file_location('m10r_b2y_assets_v076',p)
    if spec is None or spec.loader is None: raise RuntimeError('cannot load parser')
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def main():
    if len(sys.argv)!=3: raise SystemExit('usage: m10r_yc_matrix_ownership_v076.py <sections_dir> <repo_root>')
    root=Path(sys.argv[1]);repo=Path(sys.argv[2]);mod=load_parser(repo)
    hits=list(root.glob('*data_calib_B2Y*.bin*'))
    if len(hits)!=1: raise SystemExit(f'expected one B2Y auxiliary file, got {hits}')
    p=hits[0];data=p.read_bytes();records=mod.parse_records(data)
    last=max(r.payload_offset+r.size for r in records)
    print(f'V076_B2Y=file={p.name}|size=0x{len(data):x}|records={len(records)}|last_record_end=0x{last:x}|trailing=0x{len(data)-last:x}')
    start=0;count=0
    while True:
        off=data.find(PAT,start)
        if off<0:break
        owners=[r for r in records if r.payload_offset<=off and off+len(PAT)<=r.payload_offset+r.size]
        if owners:
            for r in owners:
                print(f'V076_MATRIX=off=0x{off:x}|owner_record={r.index}|id=0x{r.record_id:x}|payload=0x{r.payload_offset:x}|size=0x{r.size:x}|within=0x{off-r.payload_offset:x}')
        else:
            zone='TRAILING_AFTER_RECORD_PAYLOADS' if off>=last else 'NON_PAYLOAD_TABLE_OR_GAP'
            lo=max(0,off-32);hi=min(len(data),off+len(PAT)+64)
            print(f'V076_MATRIX=off=0x{off:x}|owner_record=NONE|zone={zone}|context={data[lo:hi].hex()}')
        count+=1;start=off+1
    print(f'V076_MATRIX_COUNT={count}')
    # Explicit known record-0x0C inventory.
    c=[r for r in records if r.record_id==0x0c]
    print(f"V076_ID0C_COUNT={len(c)}|indices={','.join(str(r.index) for r in c)}")
    print('OVERALL_VERDICT=MATRIX_OCCURRENCE_OWNERSHIP_RECORDED_WITHOUT_STAGE_ORDER_INFERENCE')
if __name__=='__main__':main()
