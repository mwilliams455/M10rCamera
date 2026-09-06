#!/usr/bin/env python3
"""Fast bounded v0.64b WBCLIPLEVEL semantic/data ABI probe.

Avoids whole-IMG disassembly. Uses already-proven selector/driver anchors and
only bounded function decoding plus raw section string scans.
"""
from pathlib import Path
import csv, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, read_cstr_va
from m10r_wbcliplevel_semantic_v064 import (
    WRAP, DRIVER, LOOKUP, CENTRAL, MMIO, REG0, REG1, INLINE_LO, INLINE_HI,
    SEARCH_NEEDLES, decode, emit_function, hex_dump_va, section_scan,
    classify_driver,
)


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); imgs=get_img_section(root)
    print(f'V064B_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=WBCLIPLEVEL_SEMANTICS_UNRESOLVED_IMG'); return
    row,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=WBCLIPLEVEL_SEMANTICS_UNRESOLVED_MAP'); return
    print(f'V064B_MAP_BIAS=0x{bias:08x}'); print(f"V064B_SECTION={row['index']}:{row['name']}")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True

    cseq,cen,clits,ccalls,cadrs=emit_function(md,data,bias,CENTRAL,'CENTRAL')
    wseq,wen,wlits,wcalls,wadrs=emit_function(md,data,bias,WRAP,'WBCLIP_WRAPPER')
    dseq,den,dlits,dcalls,dadrs=emit_function(md,data,bias,DRIVER,'WBCLIP_DRIVER')
    lseq,len_,llits,lcalls,ladrs=emit_function(md,data,bias,LOOKUP,'PARASET_LOOKUP')

    print('\n=== V064B_INLINE_DESCRIPTOR_HEXDUMP ===')
    hex_dump_va(data,bias,INLINE_LO,INLINE_HI)

    central_calls_wrap=[a for a,t in ccalls if t==WRAP]
    wrapper_calls_driver=[a for a,t in wcalls if t==DRIVER]
    wrapper_calls_lookup=[a for a,t in wcalls if t==LOOKUP]
    print('V064B_CENTRAL_CALLS_WBCLIP='+(','.join(f'0x{x:08x}' for x in central_calls_wrap) or '-'))
    print('V064B_WRAPPER_CALLS_DRIVER='+(','.join(f'0x{x:08x}' for x in wrapper_calls_driver) or '-'))
    print('V064B_WRAPPER_CALLS_LOOKUP='+(','.join(f'0x{x:08x}' for x in wrapper_calls_lookup) or '-'))

    hits=section_scan(root)
    print(f'V064B_WBCLIP_STRING_SECTION_HITS={len(hits)}')
    for r,p,ctx,lo in hits:
        asc=''.join(chr(x) if 32<=x<127 else '.' for x in ctx)
        hx=' '.join(f'{x:02x}' for x in ctx[:128])
        print(f"V064B_SECTION_HIT=section={r['index']}:{r['name']}|offset=0x{p:x}|context_start=0x{lo:x}|ascii={asc}")
        print(f"V064B_SECTION_HIT_HEX=section={r['index']}|offset=0x{p:x}|{hx}")

    # ADR-backed name proof: at least one wrapper ADR target reaches the
    # WBCLIPLEVEL inline string within a short local window.
    named=False
    for _,at in wadrs:
        off=at-bias
        if 0<=off<len(data) and b'WBCLIPLEVEL' in data[off:min(len(data),off+96)]: named=True

    abi_ok=classify_driver(dseq,dlits)
    mmio_values={v for _,_,v in dlits if 0x20000000<=v<0x30000000}
    nonaddr=sorted({v for _,_,v in dlits if v!=MMIO and not (bias<=v<bias+len(data))})
    print('V064B_DRIVER_NONADDRESS_LITERALS='+(','.join(f'0x{x:08x}' for x in nonaddr) or '-'))

    # Report the exact alternate/default branch literal sequence separately.
    alt=[]
    for a,p,v in dlits:
        if a>=0x420d4336 and v!=MMIO and not (bias<=v<bias+len(data)):
            alt.append((a,v))
    print('V064B_ALT_BRANCH_LITERALS='+(','.join(f'0x{a:08x}:0x{v:08x}' for a,v in alt) or '-'))

    print(f'V064B_WBCLIP_NAMED_SELECTOR={int(named)}')
    print(f'V064B_CENTRAL_CALLS_SELECTOR={int(bool(central_calls_wrap))}')
    print(f'V064B_SELECTOR_CALLS_LOOKUP={int(bool(wrapper_calls_lookup))}')
    print(f'V064B_SELECTOR_CALLS_DRIVER={int(bool(wrapper_calls_driver))}')
    print(f'V064B_DRIVER_MMIO_PAGE_OK={int(MMIO in mmio_values)}')
    print(f'V064B_DRIVER_ABI_OK={int(abi_ok)}')

    if named and central_calls_wrap and wrapper_calls_lookup and wrapper_calls_driver and abi_ok and MMIO in mmio_values:
        print('OVERALL_VERDICT=WBCLIPLEVEL_DRIVER_AND_DATA_ABI_PROVEN_NEEDS_ACTIVE_PARASET_VALUES')
    else:
        print('OVERALL_VERDICT=WBCLIPLEVEL_SEMANTICS_UNRESOLVED')

if __name__=='__main__': main()
