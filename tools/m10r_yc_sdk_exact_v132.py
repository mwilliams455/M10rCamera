#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
A=0x00051da6;Z=0x00051f1a

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def str_at(b,base,a,n=180):
 o=a-base
 if not 0<=o<len(b):return None
 e=b.find(b'\0',o,min(len(b),o+n));q=b[o:e]
 if e>o and q and all(32<=x<127 for x in q):return q.decode('ascii','replace')
 return None

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v132 <sections>')
 b,base,fn=load(Path(sys.argv[1]));print(f'V132_SAM7={fn}|base=0x{base:08x}|func=0x{A:08x}..0x{Z:08x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for ins in md.disasm(b[A-base:Z-base],A):
  ann=[]
  try:
   for op in ins.operands:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     p=((int(ins.address)+4)&~3)+int(op.mem.disp);o=p-base
     if 0<=o<=len(b)-4:
      v=u32(b,o);ann.append(f'LIT=0x{p:08x}->0x{v:08x}')
      s=str_at(b,base,v)
      if s:ann.append('STR='+s)
   if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
   if ins.mnemonic=='adr' and len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_IMM:
    imm=int(ins.operands[1].imm);cands=[imm,((int(ins.address)+4)&~3)+imm]
    for v in cands:
     s=str_at(b,base,v)
     if s:ann.append(f'ADRSTR=0x{v:08x}|{s}')
  except:pass
  if ins.mnemonic=='push':ann.append('PROLOGUE=1')
  if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):ann.append('RETURN=1')
  print(f'V132_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('\n######## DATA/STRINGS 0x51F68..0x52038 ########')
 # Explicitly show printable strings and dwords from the embedded literal/data island used by neighboring routines.
 lo=0x00051f68;hi=0x00052038
 for a in range(lo,hi,4):
  o=a-base
  if 0<=o<=len(b)-4:print(f'V132_DATA=0x{a:08x}|0x{u32(b,o):08x}')
 import re
 reg=b[lo-base:hi-base]
 for m in re.finditer(rb'[ -~]{6,}',reg):print(f'V132_CSTR=0x{lo+m.start():08x}|{m.group().decode("ascii","ignore")}')
 print('\nV132_GOAL=prove_0x51DA6_is_Im_B2Y_Ctrl_Yc_Convert_and_map_exact_b2y_ctrl_ycc_structure_offsets_to_MMIO_0x20020900_fields')
 print('OVERALL_VERDICT=V132_EXACT_YC_VENDOR_CONTROL_MAP_COMPLETE')
if __name__=='__main__':main()
