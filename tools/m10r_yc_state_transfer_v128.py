#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
A=0x000d3088;Z=0x000d327a;TARGET=A

def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def sx(v,bits):return (v^(1<<(bits-1)))-(1<<(bits-1))
def bl_target(img,base,o):
 if o+4>len(img):return None
 h1=u16(img,o);h2=u16(img,o+2)
 if (h1&0xf800)!=0xf000 or (h2&0xd000)!=0xd000:return None
 S=(h1>>10)&1;imm10=h1&0x3ff;J1=(h2>>13)&1;J2=(h2>>11)&1;imm11=h2&0x7ff;I1=(~(J1^S))&1;I2=(~(J2^S))&1
 imm=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
 return ((base+o+4)+sx(imm,25))&0xffffffff

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v128 <sections>')
 img,base,fn=load(Path(sys.argv[1]));print(f'V128_IMG={fn}|base=0x{base:x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 print(f'\n######## STATE_TRANSFER 0x{A:08x}..0x{Z:08x} ########')
 for ins in md.disasm(img[A-base:Z-base],A):
  ann=[]
  try:
   for op in ins.operands:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     p=((int(ins.address)+4)&~3)+int(op.mem.disp);oo=p-base
     if 0<=oo<=len(img)-4:ann.append(f'LIT=0x{p:08x}->0x{u32(img,oo):08x}')
   if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
  except:pass
  print(f'V128_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('\n######## DIRECT BL CALLERS ########')
 hs=[]
 for o in range(0,len(img)-3,2):
  if bl_target(img,base,o)==TARGET:hs.append(base+o)
 print('V128_CALLERS='+','.join(f'0x{x:08x}' for x in hs))
 for ca in hs:
  a=max(base,ca-80)&~1;z=min(base+len(img),ca+24)
  print(f'V128_CALLER_CONTEXT=0x{ca:08x}')
  for ins in md.disasm(img[a-base:z-base],a):
   print(f'V128_CTX=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+('|CALLSITE=1' if ins.address==ca else ''))
 print('\nV128_GOAL=determine_direction_packing_and_call_role_of_B2Y_register_state_transfer_at_0xD3088')
 print('OVERALL_VERDICT=V128_B2Y_STATE_TRANSFER_COMPLETE')
if __name__=='__main__':main()
