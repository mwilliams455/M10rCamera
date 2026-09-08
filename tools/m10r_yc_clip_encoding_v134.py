#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys,re
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
LO=0x0004f840;HI=0x0004fc40
STRINGS=[b'Im_B2Y_Ctrl_YC_OutClip',b'Im_B2Y_Ctrl_YC_OutOffsetAndGain',b'Im_B2Y_Ctrl_JpegXR_OutClip']

def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def str_at(b,base,a,n=160):
 o=a-base
 if not 0<=o<len(b):return None
 e=b.find(b'\0',o,min(len(b),o+n));q=b[o:e]
 if e>o and q and all(32<=x<127 for x in q):return q.decode('ascii','replace')
 return None

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v134 <sections>')
 b,base,fn=load(Path(sys.argv[1]));print(f'V134_SAM7={fn}|base=0x{base:08x}|scan=0x{LO:08x}..0x{HI:08x}')
 for needle in STRINGS:
  p=0;loc=[]
  while True:
   q=b.find(needle,p)
   if q<0:break
   loc.append(base+q);p=q+1
  print(f'V134_STRING={needle.decode()}|'+','.join(f'0x{x:08x}' for x in loc))
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 cands=[]
 for a in range(LO,HI,2):
  h=u16(b,a-base)
  if (h&0xfe00)==0xb400 and (h&0x0100):cands.append(a)
 print('V134_PROLOGUES='+','.join(f'0x{x:08x}' for x in cands))
 for a in cands:
  print(f'\n######## FUNC 0x{a:08x} ########')
  for ins in md.disasm(b[a-base:min(len(b),a-base+0x300)],a):
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
     imm=int(ins.operands[1].imm)
     for v in (imm,((int(ins.address)+4)&~3)+imm):
      s=str_at(b,base,v)
      if s:ann.append(f'ADRSTR=0x{v:08x}|{s}')
   except:pass
   if ins.mnemonic=='push':ann.append('PROLOGUE=1')
   if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):ann.append('RETURN=1')
   print(f'V134_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
   if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):break
 print('\nV134_GOAL=compare_explicit_YC_OutClip_struct_and_register_encoding_with_Yc_Convert_15bit_16bit_pairs_to_test_signed_clip_magnitude_hypothesis')
 print('OVERALL_VERDICT=V134_YC_CLIP_ENCODING_COMPARISON_COMPLETE')
if __name__=='__main__':main()
