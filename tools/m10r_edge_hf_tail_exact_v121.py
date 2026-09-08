#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

A=0x000d2040; Z=0x000d2438

def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v121 <sections>')
 d=Path(sys.argv[1]);b,base,fn=load(d);md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
 print(f'V121_IMG={fn}|base=0x{base:x}|range=0x{A:x}..0x{Z:x}')
 off=A-base
 for ins in md.disasm(b[off:off+(Z-A)],A):
  ann=[]
  try:ops=list(ins.operands)
  except Exception:ops=[]
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    p=((int(ins.address)+4)&~3)+int(op.mem.disp);po=p-base
    if 0<=po<=len(b)-4:ann.append(f'LITERAL=0x{p:08x}->0x{u32(b,po):08x}')
  print(f'V121_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('V121_GROUP_HYPOTHESIS=0x120..0x160 and 0x164..end are repeated 6x13bit scale + 6 wider affine/offset + 5 breakpoint structures; verify from exact masks/registers')
 print('OVERALL_VERDICT=V121_HF_TAIL_EXACT_DUMP')
if __name__=='__main__':main()
