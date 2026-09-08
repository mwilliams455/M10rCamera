#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
A=0x00051f50;Z=0x00052440

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v130 <sections>')
 b,base,fn=load(Path(sys.argv[1]));print(f'V130_SAM7={fn}|base=0x{base:08x}|range=0x{A:08x}..0x{Z:08x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for ins in md.disasm(b[A-base:Z-base],A):
  ann=[]
  try:
   for op in ins.operands:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     p=((int(ins.address)+4)&~3)+int(op.mem.disp);o=p-base
     if 0<=o<=len(b)-4:
      v=u32(b,o);ann.append(f'LIT=0x{p:08x}->0x{v:08x}')
      vo=v-base
      if 0<=vo<len(b):
       e=b.find(b'\0',vo,min(len(b),vo+180));q=b[vo:e]
       if e>vo and all(32<=x<127 for x in q):ann.append('STR='+q.decode('ascii','replace'))
   if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
  except:pass
  if ins.mnemonic=='push':ann.append('PROLOGUE=1')
  if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):ann.append('RETURN=1')
  print(f'V130_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('\nV130_GOAL=isolate_Im_B2Y_Ctrl_Yc_Convert_and_map_b2y_ctrl_ycc_structure_fields_to_hardware_bits')
 print('OVERALL_VERDICT=V130_SAM7_YC_CONTROL_DUMP')
if __name__=='__main__':main()
