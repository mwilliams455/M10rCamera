#!/usr/bin/env python3
from pathlib import Path
import csv, re, struct, sys

def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]

def clean_name(raw):
    s = raw[52:132].split(b'\0')[0]
    return s.decode('latin1', 'replace') or 'unnamed'

def main(src: Path, out_dir: Path):
    b = src.read_bytes()
    sec_count = u32(b, 0x14)
    table_size = u32(b, 0x18)
    table_off = u32(b, 0x1c)
    if not sec_count or table_size % sec_count:
        raise SystemExit('unexpected firmware section table')
    entry_size = table_size // sec_count
    body = table_off + table_size
    out_dir.mkdir(parents=True, exist_ok=True)
    rows=[]
    for i in range(sec_count):
        e = table_off + i*entry_size
        raw = b[e:e+entry_size]
        rel_off = u32(raw, 0x18)
        size = u32(raw, 0x1c)
        kind = u32(raw, 0x20)
        image_base = u32(raw, 0x24)
        aux = u32(raw, 0x28)
        name = clean_name(raw)
        safe = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('_') or f'section_{i:03d}'
        payload = b[body+rel_off:body+rel_off+size]
        fn = out_dir / f'{i:03d}_{safe}.bin'
        fn.write_bytes(payload)
        rows.append([i,name,f'0x{rel_off:08x}',size,f'0x{kind:08x}',f'0x{image_base:08x}',f'0x{aux:08x}',fn.name])
    with (out_dir/'sections.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['index','name','relative_offset','size','kind','image_base','aux','file']); w.writerows(rows)
    print(f'sections={sec_count} entry_size={entry_size} body=0x{body:x}')
    for r in rows:
        print('\t'.join(map(str,r[:-1])))

if __name__ == '__main__':
    if len(sys.argv)!=3:
        raise SystemExit(f'usage: {sys.argv[0]} decoded.bin output_dir')
    main(Path(sys.argv[1]), Path(sys.argv[2]))
