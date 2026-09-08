#!/usr/bin/env python3
from __future__ import annotations
import csv,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_R0,ARM_REG_PC

# Continuation addresses immediately after literal pools observed in the known setters.
RANGES=[
 (0x000d1e00,0x000d2300,'HF_TAIL_CONT'),
 (0x000d2a00,0x000d3100,'LF_MID_TAIL'),
]
WATCH_LO=0x0b0; WATCH_HI=0x1b0

def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v118 <sections_dir>')
 d=Path(sys.argv[1]);b,base,fn=load(d)
 print(f'V118_IMG={fn}|base=0x{base:x}|size=0x{len(b):x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
 for a,z,label in RANGES:
  print(f'\n=== V118_RANGE {label}|0x{a:08x}..0x{z:08x} ===')
  off=a-base
  for ins in md.disasm(b[off:off+(z-a)],a):
   ann=[];watch=False
   try:ops=list(ins.operands)
   except Exception:ops=[]
   if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
    ann.append('CALL=0x%08x'%(int(ops[0].imm)&0xffffffff))
   for op in ops:
    if op.type==ARM_OP_MEM:
     disp=int(op.mem.disp)
     if op.mem.base==ARM_REG_R0 and WATCH_LO<=disp<=WATCH_HI:
      ann.append(f'R0_FIELD=0x{disp:x}');watch=True
     if op.mem.base==ARM_REG_PC:
      pp=((int(ins.address)+4)&~3)+disp
      ann.append(f'PC_LIT=0x{pp:08x}')
   if watch or ann or ins.mnemonic in ('bx','pop','b','beq','bne','cbz','cbnz'):
    print(f'V118_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('\nV118_GOAL=map_tail_fields_0xb0_to_0x1a8_including_sharpness_500_1000_1500_groups_to_MMIO')
 print('OVERALL_VERDICT=V118_EDGE_SETTER_TAIL_SCANNED')
if __name__=='__main__':main()
