#!/usr/bin/env python3
"""M10-R v0.81: full-firmware WBCLIPLEVEL section census.

Search all extracted sections for the WB hardware page/register literal values,
known WBCLIP diagnostic/name strings, and the exact B2Y F82F x4 payload. This
is a software-ownership boundary check, not a claim about hardware semantics.
Research only; no renderer/application code is touched.
"""
from pathlib import Path
import csv,struct,sys

VALUES={
    'WB_PAGE_20020080':0x20020080,
    'WB_REG94_20020094':0x20020094,
    'WB_REG98_20020098':0x20020098,
    'WB_PAGE_BASE_20020000':0x20020000,
}
STRINGS=[
    b'WBCLIPLEVEL',
    b'WB_Clip_Level',
    b'Im_B2Y_Set_WB_Clip_Level',
    b'img_b2y_select_wbcliplevel_paraset',
]
F82F_X4=bytes.fromhex('2f f8 00 00 2f f8 00 00 2f f8 00 00 2f f8 00 00')


def all_offsets(b,needle):
    out=[];p=0
    while True:
        q=b.find(needle,p)
        if q<0:return out
        out.append(q);p=q+1

def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1])
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    value_sections={k:[] for k in VALUES};string_sections={s:[] for s in STRINGS};f82=[]
    for r in rows:
        b=(root/r['file']).read_bytes();idx=int(r['index']);name=r['name']
        for label,val in VALUES.items():
            offs=all_offsets(b,struct.pack('<I',val))
            if offs:
                value_sections[label].append((idx,name,offs))
                print(f'V081_VALUE_SECTION={label}|index={idx}|name={name}|count={len(offs)}|offs='+','.join(f'0x{x:x}' for x in offs))
        for s in STRINGS:
            offs=all_offsets(b,s)
            if offs:
                string_sections[s].append((idx,name,offs))
                print(f'V081_STRING_SECTION={s.decode("latin1")}|index={idx}|name={name}|count={len(offs)}|offs='+','.join(f'0x{x:x}' for x in offs))
        offs=all_offsets(b,F82F_X4)
        if offs:
            f82.append((idx,name,offs))
            print(f'V081_F82F_X4_SECTION=index={idx}|name={name}|count={len(offs)}|offs='+','.join(f'0x{x:x}' for x in offs))

    for label in VALUES:
        secs=value_sections[label]
        print(f'V081_{label}_SECTION_COUNT={len(secs)}')
        print(f'V081_{label}_SECTIONS='+(','.join(f'{i}:{n}' for i,n,_ in secs) or '-'))
    for s in STRINGS:
        key=s.decode('latin1').replace(' ','_')
        secs=string_sections[s]
        print(f'V081_STRING_{key}_SECTION_COUNT={len(secs)}')
    print(f'V081_F82F_X4_SECTION_COUNT={len(f82)}')
    print('V081_F82F_X4_SECTIONS='+(','.join(f'{i}:{n}' for i,n,_ in f82) or '-'))

    page=value_sections['WB_PAGE_20020080']
    page_names={n for _,n,_ in page}
    expected_subset={'IMG-System','IMG-SAM7'}
    only_known=int(page_names.issubset(expected_subset) and 'IMG-System' in page_names and 'IMG-SAM7' in page_names)
    print(f'V081_WB_PAGE_ONLY_IMG_SYSTEM_AND_SAM7={only_known}')
    print('V081_HARDWARE_TRANSFER_FUNCTION_PROVEN=0')
    if only_known:
        print('OVERALL_VERDICT=WBCLIP_SOFTWARE_OWNERSHIP_BOUNDARY_IMG_SYSTEM_PLUS_IMG_SAM7_ONLY_HARDWARE_SEMANTICS_REMAIN')
    else:
        print('OVERALL_VERDICT=WBCLIP_ADDITIONAL_SECTION_OWNER_CANDIDATES_REQUIRE_REVIEW')
if __name__=='__main__':main()
