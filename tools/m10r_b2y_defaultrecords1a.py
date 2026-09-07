#!/usr/bin/env python3
"""Extract unnamed/default B2Y records for interpolation gamma (ID 9) and de-knee (ID 1)."""
from pathlib import Path
import csv, struct, sys
from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE, u32

TARGETS=(0x01,0x09)

def cstr64(b,o):
    return b[o:o+0x40].split(b'\0',1)[0].decode('ascii','replace')

def names_for(b,rec):
    h=RECORD_HEADER_OFF+rec.index*RECORD_STRIDE
    n=u32(b,h+0x0c)
    cap=(RECORD_STRIDE-0x10)//0x40
    return [cstr64(b,h+0x10+i*0x40) for i in range(min(n,cap))]

def hx(blob,n=64):
    return ' '.join(f'{x:02x}' for x in blob[:n])

def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1])
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    rows=[r for r in rows if 'b2y.bin' in r['name'].lower()]
    if not rows: raise SystemExit('B2Y.bin section not found')
    # Canonical decoded firmware contains one explicit data/calib/B2Y.bin section.
    r=sorted(rows,key=lambda x:int(x['index']))[0]
    b=(root/r['file']).read_bytes(); recs=parse_records(b)
    print(f'DEFAULTRECORDS1A_SECTION={r["index"]}:{r["name"]}|file={r["file"]}|records={len(recs)}')
    for rid in TARGETS:
        matches=[rec for rec in recs if rec.record_id==rid]
        print(f'DEFAULTRECORDS1A_ID=0x{rid:02x}|records={len(matches)}')
        empty=[]
        for rec in matches:
            names=names_for(b,rec)
            payload=b[rec.payload_offset:rec.payload_offset+rec.size]
            has_empty=any(s=='' for s in names)
            print(f'DEFAULTRECORDS1A_RECORD=id=0x{rid:02x}|index={rec.index}|rel=0x{rec.rel_offset:x}|size=0x{rec.size:x}|payload=0x{rec.payload_offset:x}|name_count={len(names)}|names={names!r}|empty={int(has_empty)}')
            print(f'DEFAULTRECORDS1A_HEAD=id=0x{rid:02x}|index={rec.index}|hex={hx(payload)}')
            if payload:
                print(f'DEFAULTRECORDS1A_BYTE0=id=0x{rid:02x}|index={rec.index}|value=0x{payload[0]:02x}|bit0={payload[0]&1}')
            if has_empty: empty.append((rec,payload,names))
        print(f'DEFAULTRECORDS1A_EMPTY_RECORDS=id=0x{rid:02x}|count={len(empty)}')
        if len(empty)==1:
            rec,payload,names=empty[0]
            print(f'DEFAULTRECORDS1A_SELECTED_CANDIDATE=id=0x{rid:02x}|index={rec.index}|size=0x{rec.size:x}|byte0=0x{payload[0]:02x}|bit0={payload[0]&1}')
        elif len(empty)==0:
            print(f'DEFAULTRECORDS1A_SELECTED_CANDIDATE=id=0x{rid:02x}|UNRESOLVED_NO_EMPTY_NAME')
        else:
            print(f'DEFAULTRECORDS1A_SELECTED_CANDIDATE=id=0x{rid:02x}|UNRESOLVED_MULTIPLE_EMPTY_NAMES')

if __name__=='__main__': main()
