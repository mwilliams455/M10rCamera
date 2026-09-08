#!/usr/bin/env python3
from __future__ import annotations
import csv, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

SECTION_PREFIX=4
RECORD_HEADER_OFF=SECTION_PREFIX+0x10
RECORD_STRIDE=0xA90
TARGET_IDS={
  0x0D:'Y_BLEND', 0x12:'TEXTURE_ENHANCEMENT', 0x11:'EDGE_SYNTHESIS',
  0x0F:'HIGH_FREQ_EDGE_CTRL', 0x10:'LOW_FREQ_EDGE_CTRL',
  0x1E:'HIGH_FREQ_TABLE_1',0x1F:'HIGH_FREQ_TABLE_2',0x20:'HIGH_FREQ_TABLE_3',0x21:'HIGH_FREQ_TABLE_4',
  0x22:'LOW_FREQ_TABLE_1',0x23:'LOW_FREQ_TABLE_2',0x24:'LOW_FREQ_TABLE_3',0x25:'LOW_FREQ_TABLE_4',
}
ROOTS={
  0x000D4480:'Y_BLEND_SETTER',
  0x000D36F4:'TEXTURE_ENHANCEMENT_SETTER',
  0x000D16DC:'EDGE_SYNTHESIS_SETTER',
  0x000D19F8:'HIGH_FREQ_EDGE_CTRL_SETTER',
  0x000D263C:'LOW_FREQ_EDGE_CTRL_SETTER',
  0x000D3640:'EDGE_TABLE_WRITER',
}

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def u16s(blob,n=48):
    m=min(len(blob)//2,n); return list(struct.unpack_from('<'+'H'*m,blob,0)) if m else []
def u32s(blob,n=24):
    m=min(len(blob)//4,n); return list(struct.unpack_from('<'+'I'*m,blob,0)) if m else []
def s16(x): return x-0x10000 if x&0x8000 else x

def parse_records(data):
    count=u32(data,SECTION_PREFIX+8); payload_base=RECORD_HEADER_OFF+count*RECORD_STRIDE
    out=[]
    for i in range(count):
        o=RECORD_HEADER_OFF+i*RECORD_STRIDE
        rid,rel,size=u32(data,o),u32(data,o+4),u32(data,o+8)
        out.append((i,rid,rel,size,payload_base+rel))
    return out

def pc_target(ins,disp): return ((int(ins.address)+4)&~3)+int(disp)

def dump_func(data,base,va,label):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    off=va-base
    print(f'V101_FUNC=0x{va:08x}|label={label}')
    if off<0 or off>=len(data):
        print('  V101_OOB=1'); return
    for k,ins in enumerate(md.disasm(data[off:off+0x500],va)):
        print(f'  V101_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')
        try: ops=list(ins.operands)
        except Exception: ops=[]
        if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
            print(f'  V101_CALL=0x{ins.address:08x}->0x{int(ops[0].imm)&0xffffffff:08x}')
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                p=pc_target(ins,op.mem.disp); po=p-base
                if 0<=po<=len(data)-4:
                    v=u32(data,po); extra=''
                    if 0x20000000<=v<=0x20ffffff: extra='|MMIO=1'
                    print(f'  V101_LITERAL=ins=0x{ins.address:08x}|pool=0x{p:08x}|value=0x{v:08x}{extra}')
        if k>3 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):
            break

def main():
    if len(sys.argv)!=3: raise SystemExit('usage: m10r_yblend_texture_edge_v101.py <sections_dir> <b2y_section>')
    sections=Path(sys.argv[1]); b2yp=Path(sys.argv[2]); b2y=b2yp.read_bytes()
    recs=parse_records(b2y)
    print(f'V101_B2Y_SIZE=0x{len(b2y):x}|records={len(recs)}')
    for rid,name in TARGET_IDS.items():
        hits=[r for r in recs if r[1]==rid]
        print(f'\n=== V101_RECORD {name} id=0x{rid:02x} count={len(hits)} ===')
        for i,(idx,_,rel,size,payload) in enumerate(hits):
            blob=b2y[payload:payload+size]
            head=blob[:min(size,192)]
            print(f'V101_REC=occ={i}|index={idx}|rel=0x{rel:x}|size=0x{size:x}|payload=0x{payload:x}')
            print('V101_U32='+','.join(str(x) for x in u32s(head)))
            vals=u16s(head)
            print('V101_U16='+','.join(str(x) for x in vals))
            print('V101_S16='+','.join(str(s16(x)) for x in vals))
            print('V101_HEX='+head.hex())
    rows=list(csv.DictReader((sections/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System')
    img=(sections/row['file']).read_bytes(); base=int(row['image_base'],16)
    print(f'\nV101_IMG_SYSTEM={row["file"]}|base=0x{base:08x}|size=0x{len(img):x}')
    for va,label in ROOTS.items():
        print('\n=== '+label+' ==='); dump_func(img,base,va,label)
    print('\nOVERALL_VERDICT=V101_YBLEND_TEXTURE_EDGE_RECORDS_AND_MMIO_SETTERS_EXTRACTED')

if __name__=='__main__': main()
