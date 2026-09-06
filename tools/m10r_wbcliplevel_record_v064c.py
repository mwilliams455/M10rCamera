#!/usr/bin/env python3
"""M10-R v0.64c: extract the actual B2Y.bin WBCLIPLEVEL record (ID 4).

v0.64 proved:
  img_b2y_select_wbcliplevel_paraset -> generic B2Y.bin lookup with record id 4
  -> driver 0x420d42dc -> MMIO 0x20020094/0x20020098.

The generic lookup uses the exact B2Y record layout already frozen by the B2Y
asset extractor (0xA90 record headers, payload after all headers).  This probe
parses record ID 4 from the decoded calibration section, inventories its names,
and reports the four uint16 values consumed by the driver at payload offsets
+0,+4,+8,+12.
"""
from pathlib import Path
import csv, struct, sys
from m10r_b2y_assets import (
    parse_records, RECORD_HEADER_OFF, RECORD_STRIDE, u32
)

RID=0x04
DRIVER_OFFSETS=(0,4,8,12)


def u16(b,o): return struct.unpack_from('<H',b,o)[0]

def cstr64(b,o):
    raw=b[o:o+0x40].split(b'\0',1)[0]
    return raw.decode('ascii','replace')


def hexdump(blob,base=0):
    for o in range(0,len(blob),16):
        c=blob[o:o+16]
        hx=' '.join(f'{x:02x}' for x in c)
        asc=''.join(chr(x) if 32<=x<127 else '.' for x in c)
        print(f'V064C_HEX=+0x{base+o:04x}|{hx:<47}|{asc}')


def candidate_sections(root):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    # Prefer explicit B2Y calibration paths but retain parseable calibration
    # sections as a fallback so this is robust to section-name spelling.
    scored=[]
    for r in rows:
        name=r['name'].lower()
        score=(10 if 'b2y.bin' in name else 5 if 'b2y' in name else 1 if 'calib' in name else 0)
        if score: scored.append((score,r))
    return [r for _,r in sorted(scored,key=lambda x:(-x[0],int(x[1]['index'])))]


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); found=[]
    for r in candidate_sections(root):
        b=(root/r['file']).read_bytes()
        try: recs=parse_records(b)
        except Exception as e:
            print(f"V064C_PARSE_SKIP=section={r['index']}:{r['name']}|{type(e).__name__}:{e}")
            continue
        matches=[x for x in recs if x.record_id==RID]
        print(f"V064C_PARSEABLE=section={r['index']}:{r['name']}|records={len(recs)}|id4={len(matches)}")
        for rec in matches: found.append((r,b,recs,rec))

    print(f'V064C_ID4_RECORDS={len(found)}')
    if len(found)!=1:
        print('OVERALL_VERDICT=WBCLIPLEVEL_RECORD_UNRESOLVED'); return

    r,b,recs,rec=found[0]
    print(f"V064C_SECTION={r['index']}:{r['name']}|file={r['file']}")
    print(f'V064C_RECORD=id=0x{rec.record_id:02x}|index={rec.index}|rel=0x{rec.rel_offset:x}|size=0x{rec.size:x}|payload=0x{rec.payload_offset:x}')
    hoff=RECORD_HEADER_OFF+rec.index*RECORD_STRIDE
    name_count=u32(b,hoff+0x0c)
    print(f'V064C_RECORD_NAME_COUNT={name_count}')
    names=[]
    for i in range(min(name_count, (RECORD_STRIDE-0x10)//0x40)):
        s=cstr64(b,hoff+0x10+i*0x40); names.append(s)
        print(f'V064C_RECORD_NAME={i}|{s!r}')
    print(f'V064C_HAS_EMPTY_DEFAULT_NAME={int(any(s=="" for s in names))}')

    payload=b[rec.payload_offset:rec.payload_offset+rec.size]
    print(f'V064C_PAYLOAD_BYTES={len(payload)}')
    hexdump(payload[:min(len(payload),0x100)])
    if len(payload)<16:
        print('OVERALL_VERDICT=WBCLIPLEVEL_RECORD_TOO_SHORT'); return

    vals=[u16(payload,o) for o in DRIVER_OFFSETS]
    u32s=[struct.unpack_from('<I',payload,o)[0] for o in DRIVER_OFFSETS]
    print('V064C_DRIVER_U16_VALUES='+','.join(str(v) for v in vals))
    print('V064C_DRIVER_U16_HEX='+','.join(f'0x{v:04x}' for v in vals))
    print('V064C_DRIVER_U32_AT_FIELDS='+','.join(f'0x{v:08x}' for v in u32s))
    print('V064C_DRIVER_MAPPING=0x20020094.upper<-field0|0x20020094.lower<-field1|0x20020098.upper<-field2|0x20020098.lower<-field3')
    print(f'V064C_ALL_15000={int(all(v==15000 for v in vals))}')
    print(f'V064C_ALL_16383={int(all(v==0x3fff for v in vals))}')
    print(f'V064C_ALL_65535={int(all(v==0xffff for v in vals))}')
    print(f'V064C_MAX={max(vals)}|MIN={min(vals)}')

    # Driver fallback when lookup fails ends by writing 0xffffffff to both
    # 32-bit words, i.e. all four 16-bit clip fields become 65535.  The record
    # values above are the data-driven normal branch and are therefore the
    # important active/default candidate.
    if any(s=='' for s in names):
        if all(v==0x3fff for v in vals):
            print('OVERALL_VERDICT=WBCLIPLEVEL_DEFAULT_RECORD_ALL_16383_PROVEN')
        elif all(v==15000 for v in vals):
            print('OVERALL_VERDICT=WBCLIPLEVEL_DEFAULT_RECORD_ALL_15000_PROVEN')
        else:
            print('OVERALL_VERDICT=WBCLIPLEVEL_DEFAULT_RECORD_VALUES_PROVEN_NONUNIFORM_OR_OTHER')
    else:
        print('OVERALL_VERDICT=WBCLIPLEVEL_RECORD_VALUES_PROVEN_DEFAULT_NAME_UNRESOLVED')

if __name__=='__main__': main()
