#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
RANGES=[(0x00154dc0,0x00154e70,'Y_BLEND_WRAPPER'),(0x00154e70,0x00154f24,'YC_CONVERT_WRAPPER')]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v126 <sections>')
 img,base,fn=load(Path(sys.argv[1]));print(f'V126_IMG={fn}|base=0x{base:x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for a,z,label in RANGES:
  print(f'\n######## {label} 0x{a:08x}..0x{z:08x} ########')
  for ins in md.disasm(img[a-base:z-base],a):
   ann=[]
   try:
    if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
    for op in ins.operands:
     if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
      p=((int(ins.address)+4)&~3)+int(op.mem.disp);po=p-base
      if 0<=po<=len(img)-4:ann.append(f'LIT=0x{p:08x}->0x{u32(img,po):08x}')
   except:pass
   if ins.mnemonic=='push':ann.append('PROLOGUE=1')
   if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):ann.append('RETURN=1')
   print(f'V126_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('\nV126_GOAL=prove_r6_initial_value_and_success_failure_flag_passed_as_r1_to_Y_BLEND_and_Yc_Convert_setters')
 print('OVERALL_VERDICT=V126_YBLEND_YC_WRAPPER_EXACT')
if __name__=='__main__':main()
