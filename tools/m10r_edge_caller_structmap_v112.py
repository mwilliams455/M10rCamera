#!/usr/bin/env python3
from __future__ import annotations
import csv, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

RANGES=[
    (0x00154180,0x00154370,'HF_SELECT_PROGRAM_PATH'),
    (0x00154520,0x001546f0,'LF_SELECT_PROGRAM_PATH'),
]
ROOTS={0x000d19f8:'HF_SETTER',0x000d263c:'LF_SETTER',0x000d3640:'EDGE_TABLE_WRITER'}
PFX=4; HDR=PFX+0x10; STRIDE=0xA90

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def s32(x): return x-0x100000000 if x&0x80000000 else x

def load_section(sections,name):
    rows=list(csv.DictReader((sections/'sections.csv').open()))
    r=next(x for x in rows if x['name']==name)
    return (sections/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def dump(md,b,base,a,z,label):
    print(f'\n=== V112_{label} 0x{a:08x}..0x{z:08x} ===')
    off=a-base
    for ins in md.disasm(b[off:off+(z-a)],a):
        ann=[]
        try: ops=list(ins.operands)
        except Exception: ops=[]
        if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
            t=int(ops[0].imm)&0xffffffff
            ann.append('CALL=0x%08x%s'%(t,'|'+ROOTS[t] if t in ROOTS else ''))
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                pc=((ins.address+4)&~3)+int(op.mem.disp)
                po=pc-base
                if 0<=po<=len(b)-4:
                    v=u32(b,po); ann.append('LIT@0x%08x=0x%08x'%(pc,v))
        print(f'V112_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))

def parse_record(b2y,rid,idxwanted=None):
    count=u32(b2y,PFX+8); payload=HDR+count*STRIDE
    out=[]
    for idx in range(count):
        o=HDR+idx*STRIDE; rr,rel,size=u32(b2y,o),u32(b2y,o+4),u32(b2y,o+8)
        if rr!=rid: continue
        p=payload+rel; blob=b2y[p:p+size]
        out.append((idx,size,blob))
    return out

def main():
    if len(sys.argv)!=3: raise SystemExit('usage: v112 <sections_dir> <B2Y>')
    sections=Path(sys.argv[1]); b2yp=Path(sys.argv[2]); b2y=b2yp.read_bytes()
    img,base,fn=load_section(sections,'IMG-System')
    print(f'V112_IMG_SYSTEM={fn}|base=0x{base:x}|size=0x{len(img):x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    for a,z,label in RANGES: dump(md,img,base,a,z,label)
    print('\n=== V112_SELECTED_RECORD_WORD_MAP ===')
    for rid,label in [(0x0f,'HF'),(0x10,'LF')]:
        recs=parse_record(b2y,rid)
        for idx,size,blob in recs[:1]:
            vals=struct.unpack_from('<'+'I'*(min(size,0x1b0)//4),blob)
            print(f'V112_REC={label}|index={idx}|size=0x{size:x}')
            for i,v in enumerate(vals):
                print(f'V112_DWORD={label}|i={i}|off=0x{i*4:03x}|u={v}|s={s32(v)}|hex=0x{v:08x}')
    print('\nV112_GOAL=map_calibration_fields_to_runtime_setter_struct_and_identify_coring_gain_limit_semantics')
    print('OVERALL_VERDICT=V112_EDGE_CALLER_STRUCTMAP_DUMPED')

if __name__=='__main__': main()
