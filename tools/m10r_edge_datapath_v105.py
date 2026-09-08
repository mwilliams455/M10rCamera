#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, struct, sys
from collections import Counter
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM

SECTION_PREFIX=4
HDR=SECTION_PREFIX+0x10
STRIDE=0xA90
IDS={
    0x0F:'HIGH_FREQ_EDGE', 0x10:'LOW_FREQ_EDGE', 0x11:'EDGE_SYNTHESIS',
    0x1E:'HIGH_FREQ_TABLE_1',0x1F:'HIGH_FREQ_TABLE_2',0x20:'HIGH_FREQ_TABLE_3',0x21:'HIGH_FREQ_TABLE_4',
    0x22:'LOW_FREQ_TABLE_1',0x23:'LOW_FREQ_TABLE_2',0x24:'LOW_FREQ_TABLE_3',0x25:'LOW_FREQ_TABLE_4',
}
ROOTS={
    0x000D16DC:'EDGE_SYNTHESIS_SETTER',
    0x000D19F8:'HIGH_FREQ_EDGE_SETTER',
    0x000D263C:'LOW_FREQ_EDGE_SETTER',
    0x000D3640:'EDGE_TABLE_WRITER',
    0x0004F21C:'EDGE_TABLE_COPY_HELPER',
    0x0009F98C:'THUMB_SWITCH_HELPER',
}

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def s32s(b,n=32):
    m=min(len(b)//4,n)
    return list(struct.unpack_from('<'+'i'*m,b,0)) if m else []
def u16s(b):
    n=len(b)//2
    return struct.unpack_from('<'+'H'*n,b,0) if n else ()

def ascii_runs(b,minlen=8):
    out=[]; i=0
    while i<len(b):
        if 32 <= b[i] < 127:
            j=i
            while j<len(b) and 32 <= b[j] < 127: j+=1
            if j-i>=minlen: out.append((i,b[i:j].decode('ascii','replace')))
            i=j
        else: i+=1
    return out

def parse_records(data):
    count=u32(data,SECTION_PREFIX+8)
    payload_base=HDR+count*STRIDE
    out=[]
    for idx in range(count):
        o=HDR+idx*STRIDE
        rid,rel,size=u32(data,o),u32(data,o+4),u32(data,o+8)
        header=data[o:o+STRIDE]
        payload=data[payload_base+rel:payload_base+rel+size]
        out.append({'idx':idx,'rid':rid,'rel':rel,'size':size,'header':header,'payload':payload})
    return out

def selectors(rec):
    return [s for _,s in ascii_runs(rec['header']) if '_B2YMODE:' in s]

def table_stats(name,blob):
    vals=u16s(blob)
    c=Counter(vals)
    first=list(vals[:16]); last=list(vals[-16:]) if vals else []
    print(f'V105_TABLE={name}|bytes=0x{len(blob):x}|u16={len(vals)}|sha256={hashlib.sha256(blob).hexdigest()}')
    print(f'V105_TABLE_STATS={name}|min={min(vals) if vals else -1}|max={max(vals) if vals else -1}|unique={len(c)}|most_common={c.most_common(8)}')
    print(f'V105_TABLE_FIRST={name}|{first}')
    print(f'V105_TABLE_LAST={name}|{last}')
    # Compact run/change census. Useful for determining whether these are identity/constant/shaping LUTs.
    changes=[]
    prev=None
    for i,v in enumerate(vals):
        if i==0 or v!=prev:
            if len(changes)<32: changes.append((i,v))
        prev=v
    print(f'V105_TABLE_FIRST_CHANGES={name}|{changes}')
    ident=sum(1 for i,v in enumerate(vals) if v==i)
    print(f'V105_TABLE_IDENTITY_COUNT={name}|{ident}/{len(vals)}')

def find_img_system(sections):
    rows=list(csv.DictReader((sections/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System')
    return (sections/row['file']).read_bytes(), int(row['image_base'],16), row['file']

def disasm_block(img,base,va,nbytes=0x100):
    off=va-base
    if off<0 or off>=len(img): return []
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    return list(md.disasm(img[off:off+nbytes],va))

def direct_calls(img,base,targets):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True; md.skipdata=True
    hits={t:[] for t in targets}
    for ins in md.disasm(img,base):
        if ins.mnemonic not in ('bl','blx'): continue
        try: ops=list(ins.operands)
        except Exception: continue
        if not ops or ops[0].type!=ARM_OP_IMM: continue
        t=int(ops[0].imm)&0xffffffff
        if t in hits: hits[t].append(ins.address)
    return hits

def main():
    if len(sys.argv)!=3:
        raise SystemExit('usage: m10r_edge_datapath_v105.py <sections_dir> <b2y_section>')
    sections=Path(sys.argv[1]); b2y=Path(sys.argv[2]).read_bytes()
    recs=parse_records(b2y)
    print(f'V105_B2Y_SIZE=0x{len(b2y):x}|records={len(recs)}')

    # 1) Exact STILL/MEDIUM selection census for HF/LF and edge synthesis.
    for rid in (0x0F,0x10,0x11):
        print(f'\n=== V105_STILL_MEDIUM {IDS[rid]} id=0x{rid:02x} ===')
        for r in recs:
            if r['rid']!=rid: continue
            sels=selectors(r)
            med=[s for s in sels if ('STILL_SHARPNESS:MEDIUM' in s or 'STILLLINK_SHARPNESS:MEDIUM' in s)]
            # EDGE_SYNTHESIS selectors do not necessarily spell SHARPNESS; retain all STILL selectors there.
            if rid==0x11:
                med=[s for s in sels if '_B2YMODE:STILL_' in s or '_B2YMODE:STILLLINK_' in s]
            if not med: continue
            vals=s32s(r['payload'],32)
            print(f'V105_REC=id=0x{rid:02x}|idx={r["idx"]}|rel=0x{r["rel"]:x}|size=0x{r["size"]:x}|selectors={med}')
            print('V105_PAYLOAD_S32='+','.join(str(x) for x in vals))

    # 2) Full edge-table characterization + HF/LF equality checks.
    tables={r['rid']:r['payload'] for r in recs if r['rid'] in range(0x1E,0x26)}
    print('\n=== V105_EDGE_TABLES ===')
    for rid in range(0x1E,0x26):
        if rid in tables: table_stats(IDS[rid],tables[rid])
    print('\n=== V105_EDGE_TABLE_EQUALITY ===')
    for a,b in ((0x1E,0x22),(0x1F,0x23),(0x20,0x24),(0x21,0x25)):
        if a in tables and b in tables:
            print(f'V105_TABLE_EQUAL={IDS[a]}=={IDS[b]}|{tables[a]==tables[b]}')
    for a,b in ((0x1E,0x1F),(0x20,0x21),(0x22,0x23),(0x24,0x25)):
        if a in tables and b in tables:
            print(f'V105_TABLE_EQUAL={IDS[a]}=={IDS[b]}|{tables[a]==tables[b]}')

    # 3) Decode the D3640 selector jump table. Firmware calls the common Thumb
    # byte-switch helper at 0x9F98C. For this call LR is 0xD3651 (Thumb bit set),
    # so table bytes start at physical 0xD3651 and branch offsets are halfwords
    # relative to 0xD3650. Print both bytes and computed targets, then disassemble
    # each target rather than letting Capstone misread inline table bytes as code.
    img,base,imgfile=find_img_system(sections)
    print(f'\nV105_IMG_SYSTEM={imgfile}|base=0x{base:08x}|size=0x{len(img):x}')
    sw=0x000D3640
    raw=img[sw-base:sw-base+0x98]
    print(f'V105_D3640_RAW={raw.hex()}')
    helper=disasm_block(img,base,0x0009F98C,0x40)
    print('=== V105_SWITCH_HELPER ===')
    for ins in helper[:24]: print(f'V105_HELPER_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')
    table_phys=0x000D3651
    table=img[table_phys-base:table_phys-base+8]
    print('V105_SWITCH_TABLE_BYTES='+','.join(f'0x{x:02x}' for x in table))
    for i,v in enumerate(table):
        rid=0x1E+i; target=0x000D3650+2*v
        print(f'V105_SWITCH_MAP=selector=0x{rid:02x}|{IDS.get(rid,"?")}|entry=0x{v:02x}|target=0x{target:08x}')
        insns=disasm_block(img,base,target,0x18)
        for ins in insns[:8]: print(f'  V105_CASE_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')

    # 4) Direct caller census for configuration order clues.
    print('\n=== V105_DIRECT_CALLERS ===')
    hits=direct_calls(img,base,ROOTS)
    for t,label in ROOTS.items():
        hs=hits.get(t,[])
        print(f'V105_CALLERS=target=0x{t:08x}|{label}|count={len(hs)}|sites='+','.join(f'0x{x:08x}' for x in hs[:64]))

    # Stored Thumb function pointers (odd address) can reveal dispatch tables even
    # when direct callers are absent.
    print('\n=== V105_POINTER_REFS ===')
    for t,label in ROOTS.items():
        needle=struct.pack('<I',t|1)
        pos=[]; start=0
        while True:
            q=img.find(needle,start)
            if q<0: break
            pos.append(base+q); start=q+1
        print(f'V105_PTRREF=target=0x{t:08x}|{label}|count={len(pos)}|sites='+','.join(f'0x{x:08x}' for x in pos[:64]))

    # Structural facts important to renderer decisions.
    hf_med=[r for r in recs if r['rid']==0x0F and any('STILL_SHARPNESS:MEDIUM' in s for s in selectors(r))]
    lf_med=[r for r in recs if r['rid']==0x10 and any('STILL_SHARPNESS:MEDIUM' in s for s in selectors(r))]
    hf_en=sorted({s32s(r['payload'],1)[0] for r in hf_med if r['payload']})
    lf_en=sorted({s32s(r['payload'],1)[0] for r in lf_med if r['payload']})
    print('\n=== V105_RENDERER_RELEVANT_FACTS ===')
    print(f'V105_STILL_MEDIUM_HF_ENABLE_VALUES={hf_en}')
    print(f'V105_STILL_MEDIUM_LF_ENABLE_VALUES={lf_en}')
    print('V105_CORRECTION=HIGH_FREQ_SETTER_IS_0xD19F8_MMIO_0x20020A00;LOW_FREQ_SETTER_IS_0xD263C_MMIO_0x20020C00')
    print('V105_NOTE=Do_not_modify_renderer_strength_from_this_probe_alone;use_it_to_constrain_HF_LF_EDGE_SYNTHESIS_combination')
    print('OVERALL_VERDICT=V105_EDGE_DATAPATH_TABLE_AND_CALLER_EVIDENCE_EXTRACTED')

if __name__=='__main__': main()
