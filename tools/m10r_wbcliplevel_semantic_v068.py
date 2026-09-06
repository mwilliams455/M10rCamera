#!/usr/bin/env python3
"""M10-R v0.68 WBCLIPLEVEL semantic trace.

Research-only probe.  It does not alter renderer/application code.

Goals:
  * compare the proven direct-WB 11-bit programmer with WBCLIPLEVEL raw16 writes;
  * inventory literal consumers of the shared 0x20020080 WB hardware page;
  * locate WbClipEn / WbClipCcd strings across all extracted firmware sections
    and report pointer/xref/neighbour evidence without guessing their semantics;
  * enumerate every parseable B2Y record-ID 4 payload across sections;
  * bound the F82F / 07D0 / 07D1 numerical-coincidence question in relevant
    IMG-System code regions.
"""
from __future__ import annotations

from pathlib import Path
import csv, re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32
from m10r_b2y_assets import parse_records

WB_PAGE = 0x20020080
WBCLIP_DRIVER = 0x420D42DC
DIRECT_WB_DRIVER = 0x420D4380
CENTRAL_OWNER = 0x42154F84
B2Y_ID = 4
MAGIC = 0xCA11BF11
TARGET_STRINGS = (b"WbClipEn", b"WbClipCcd")


def u16(b: bytes, o: int):
    return struct.unpack_from('<H', b, o)[0] if 0 <= o <= len(b)-2 else None


def section_rows(root: Path):
    rows = list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    out=[]
    for r in rows:
        d=(root/r['file']).read_bytes()
        base=int(r.get('image_base','0'),0)
        out.append((r,d,base))
    return out


def read_ascii_neighbours(data: bytes, center: int, radius=0x180):
    a=max(0,center-radius); b=min(len(data),center+radius)
    out=[]
    for m in re.finditer(rb'[ -~]{4,}', data[a:b]):
        s=m.group().decode('ascii','replace')
        off=a+m.start()
        if len(s) <= 160:
            out.append((off,s))
    return out


def pc_literal_xrefs(md, data: bytes, bias: int, pool_va: int, radius=0x1000):
    po=pool_va-bias
    a=max(0,po-radius); b=min(len(data),po+radius)
    out=[]
    for off in range(a,b,2):
        ins=next(md.disasm(data[off:off+4],bias+off,count=1),None)
        if not ins: continue
        try: ops=list(ins.operands)
        except Exception: continue
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                p=((ins.address+4)&~3)+int(op.mem.disp)
                if p==pool_va:
                    out.append((ins.address,ins.mnemonic,ins.op_str))
    return out


def function_start(md,data:bytes,bias:int,va:int,back=0x180):
    start=max(bias,va-back)
    best=None
    for off in range(start-bias,va-bias+1,2):
        ins=next(md.disasm(data[off:off+4],bias+off,count=1),None)
        if not ins: continue
        if ins.mnemonic.lower()=='push' and 'lr' in ins.op_str.lower():
            best=ins.address
    return best


def decode_func(md,data:bytes,bias:int,st:int,maxlen=0x180):
    out=[]
    off=st-bias
    if not (0<=off<len(data)): return out
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        out.append(ins)
        m=ins.mnemonic.lower(); op=ins.op_str.lower()
        if (m=='pop' and 'pc' in op) or (m=='bx' and op.strip()=='lr'):
            break
    return out


def print_known_driver(md,data,bias,tag,st,maxlen):
    seq=decode_func(md,data,bias,st,maxlen)
    print(f'\n=== {tag} ===')
    for ins in seq:
        print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}'.rstrip())
    return seq


def count_halfword(data:bytes, value:int, a:int, b:int):
    needle=struct.pack('<H',value)
    aa=max(0,a); bb=min(len(data),b)
    pos=[]; p=aa
    while True:
        p=data.find(needle,p,bb)
        if p<0: break
        pos.append(p); p+=1
    return pos


def b2y_variants(rows):
    variants=[]
    for r,d,_ in rows:
        # B2Y calibration sections have the CA11BF11 magic at +4.  Name is
        # retained as an independent sanity signal; parser success is required.
        magic=u32(d,4) if len(d)>=8 else None
        if magic!=MAGIC and 'b2y.bin' not in r['name'].lower():
            continue
        try:
            recs=parse_records(d)
        except Exception:
            continue
        for rec in recs:
            if rec.record_id!=B2Y_ID: continue
            blob=d[rec.payload_offset:rec.payload_offset+rec.size]
            fields=[]
            for o in (0,4,8,12):
                fields.append(u16(blob,o) if len(blob)>=o+2 else None)
            variants.append((r,rec,blob,fields))
    return variants


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); rows=section_rows(root)
    imgs=get_img_section(root)
    print(f'V068_SECTION_COUNT={len(rows)}')
    print(f'V068_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG_SECTION'); return
    _,data=imgs[0]
    _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_IMG_MAPPING'); return
    print(f'V068_MAP_BIAS=0x{bias:08x}')
    print(f'V068_WB_PAGE_BASE=0x{WB_PAGE:08x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    # Known code-path comparison.  These are independently anchored addresses,
    # decoded again here from the same firmware to prevent conclusion drift.
    dw=print_known_driver(md,data,bias,'DIRECT_WB_DRIVER',DIRECT_WB_DRIVER,0x100)
    wc=print_known_driver(md,data,bias,'WBCLIP_DRIVER',WBCLIP_DRIVER,0xa4)
    dw_txt='\n'.join(f'{i.mnemonic} {i.op_str}'.lower() for i in dw)
    wc_txt='\n'.join(f'{i.mnemonic} {i.op_str}'.lower() for i in wc)
    direct_800 = ('#0xb' in dw_txt and 'cmp' in dw_txt)
    direct_raw11 = ('#0x15' in dw_txt and '#0x10' in dw_txt)
    clip_ldrh = sum(1 for i in wc if i.mnemonic.lower()=='ldrh')
    clip_signed = sum(1 for i in wc if i.mnemonic.lower()=='ldrsh')
    clip_ffff = ('#0xffff' in wc_txt) or ('mvns' in wc_txt) or ('mvn' in wc_txt)
    print(f'V068_DIRECT_WB_DRIVER=0x{DIRECT_WB_DRIVER:08x}')
    print('V068_DIRECT_WB_FIELD_MASK=0x07ff|packed_low_and_bits26_16')
    print(f'V068_DIRECT_WB_RANGE_CHECK_0X800={int(direct_800)}')
    print(f'V068_DIRECT_WB_11BIT_PACKING={int(direct_raw11)}')
    print(f'V068_WBCLIP_DRIVER=0x{WBCLIP_DRIVER:08x}')
    print('V068_WBCLIP_REGS=0x20020094,0x20020098')
    print(f'V068_WBCLIP_LDRH_COUNT={clip_ldrh}')
    print(f'V068_WBCLIP_LDRSH_COUNT={clip_signed}')
    print(f'V068_WBCLIP_DRIVER_HAS_FFFF_CONSTRUCTION={int(clip_ffff)}')

    # Inventory every literal WB_PAGE occurrence in IMG-System and every Thumb
    # PC-relative LDR that targets each pool word.
    needle=struct.pack('<I',WB_PAGE); pools=[]; p=0
    while True:
        p=data.find(needle,p)
        if p<0: break
        pools.append(p); p+=1
    owners=[]
    print(f'V068_WB_PAGE_LITERAL_COUNT={len(pools)}')
    for po in pools:
        pva=bias+po
        xrefs=pc_literal_xrefs(md,data,bias,pva)
        print(f'V068_WB_PAGE_LITERAL=pool=0x{pva:08x}|xrefs={len(xrefs)}')
        for a,m,o in xrefs:
            fs=function_start(md,data,bias,a)
            owners.append(fs or a)
            print(f'V068_WB_PAGE_XREF=0x{a:08x}|func={"0x%08x"%fs if fs else "?"}|{m} {o}')
    uniq=sorted(set(owners))
    print(f'V068_WB_PAGE_OWNER_COUNT={len(uniq)}')
    print('V068_WB_PAGE_OWNERS='+(','.join(f'0x{x:08x}' for x in uniq) or '-'))

    # String location + structural pointer evidence across all sections.
    for target in TARGET_STRINGS:
        hits=[]
        for r,d,base in rows:
            p=0
            while True:
                p=d.find(target,p)
                if p<0: break
                hits.append((r,d,base,p)); p+=1
        key=target.decode('ascii').upper()
        print(f'V068_{key}_HITS={len(hits)}')
        for r,d,base,off in hits:
            va=(base+off)&0xffffffff if base else None
            print(f'V068_{key}=section={r["index"]}:{r["name"]}|off=0x{off:x}|image_base=0x{base:08x}|va={"0x%08x"%va if va is not None else "-"}')
            for no,s in read_ascii_neighbours(d,off):
                if abs(no-off)<=0x100:
                    print(f'V068_{key}_NEAR=section={r["index"]}|rel={no-off:+#x}|{s}')
            if va is not None:
                ptr=struct.pack('<I',va); refs=[]
                for rr,dd,bb in rows:
                    q=0
                    while True:
                        q=dd.find(ptr,q)
                        if q<0: break
                        refs.append((rr,bb,q)); q+=1
                print(f'V068_{key}_ABS_PTR_REFS={len(refs)}')
                for rr,bb,q in refs[:32]:
                    print(f'V068_{key}_ABS_PTR=section={rr["index"]}:{rr["name"]}|off=0x{q:x}|image_base=0x{bb:08x}')

    variants=b2y_variants(rows)
    print(f'V068_B2Y_ID4_VARIANTS={len(variants)}')
    for r,rec,blob,fields in variants:
        fh=','.join('NA' if x is None else f'0x{x:04x}' for x in fields)
        print(f'V068_B2Y_ID4=section={r["index"]}:{r["name"]}|index={rec.index}|size=0x{rec.size:x}|payload=0x{rec.payload_offset:x}|fields={fh}')
        print(f'V068_B2Y_ID4_HEX={blob[:32].hex()}')

    # Numeric-context test only around the two known hardware drivers and the
    # central owner.  Raw global coincidences are deliberately excluded.
    regions=[('WB_DRIVERS',WBCLIP_DRIVER-0x100,DIRECT_WB_DRIVER+0x180),('CENTRAL',CENTRAL_OWNER-0x300,CENTRAL_OWNER+0x500)]
    for name,a_va,b_va in regions:
        a=a_va-bias; b=b_va-bias
        for val,label in ((0xF82F,'F82F'),(0x07D0,'07D0'),(0x07D1,'07D1')):
            pos=count_halfword(data,val,a,b)
            print(f'V068_{label}_{name}_HITS={len(pos)}|'+(','.join(f'0x{bias+x:08x}' for x in pos) or '-'))

    id4_f82f = bool(variants) and all(v==0xF82F for _,_,_,fs in variants for v in fs if v is not None)
    signed_ops = clip_signed>0
    print(f'V068_WBCLIP_SUCCESS_FIELDS_F82F_X4={int(id4_f82f and any(fs==[0xF82F]*4 for _,_,_,fs in variants))}')
    print('V068_WBCLIP_FALLBACK_FIELDS=0xffff,0xffff,0xffff,0xffff')
    print(f'V068_SIGNED_MINUS2001_SUPPORTED={int(signed_ops)}')
    print('V068_FFFF_DISABLE_OR_MAX_PROVEN=0')
    if clip_ldrh>=4 and clip_signed==0 and direct_800 and direct_raw11:
        print('OVERALL_VERDICT=WBCLIP_RAW16_UNSIGNED_LOAD_PATH_PROVEN_ENABLE_SEMANTICS_STILL_UNRESOLVED')
    else:
        print('OVERALL_VERDICT=WBCLIP_SEMANTIC_TRACE_INCOMPLETE')

if __name__=='__main__': main()
