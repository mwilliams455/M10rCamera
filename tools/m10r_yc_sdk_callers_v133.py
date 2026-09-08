#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC,ARM_REG_R0
TARGET=0x00051da6

def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def sx(v,n):return (v^(1<<(n-1)))-(1<<(n-1))
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def blt(b,base,o):
 if o+4>len(b):return None
 h1=u16(b,o);h2=u16(b,o+2)
 if (h1&0xf800)!=0xf000 or (h2&0xd000)!=0xd000:return None
 S=(h1>>10)&1;imm10=h1&0x3ff;J1=(h2>>13)&1;J2=(h2>>11)&1;imm11=h2&0x7ff;I1=(~(J1^S))&1;I2=(~(J2^S))&1
 imm=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
 return ((base+o+4)+sx(imm,25))&0xffffffff

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v133 <sections>')
 b,base,fn=load(Path(sys.argv[1]));print(f'V133_SAM7={fn}|base=0x{base:08x}|target=0x{TARGET:08x}')
 hs=[]
 for o in range(0,len(b)-3,2):
  if blt(b,base,o)==TARGET:hs.append(base+o)
 print('V133_DIRECT_CALLERS='+','.join(f'0x{x:08x}' for x in hs))
 # Stored function pointers too.
 for val,kind in ((TARGET,'EVEN'),(TARGET|1,'THUMB')):
  pat=struct.pack('<I',val);p=0;rr=[]
  while 1:
   q=b.find(pat,p)
   if q<0:break
   rr.append(base+q);p=q+1
  print(f'V133_FUNC_PTR={kind}|'+','.join(f'0x{x:08x}' for x in rr))
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for ca in hs:
  print(f'\n######## CALLER 0x{ca:08x} ########')
  a=max(base,ca-0x120)&~1;z=min(base+len(b),ca+0x40)
  const={}
  for ins in md.disasm(b[a-base:z-base],a):
   ann=[]
   try:
    # PC literal resolution
    for op in ins.operands:
     if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
      p=((int(ins.address)+4)&~3)+int(op.mem.disp);oo=p-base
      if 0<=oo<=len(b)-4:
       v=u32(b,oo);ann.append(f'LIT=0x{p:08x}->0x{v:08x}')
       # if looks like in-image pointer, dump prospective 40-byte ycc structure
       if base<=v<=base+len(b)-40:
        raw=b[v-base:v-base+40];h=list(struct.unpack('<20H',raw))
        ann.append('YCC40_U16='+','.join(str(x) for x in h))
    if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
   except:pass
   if ins.address==ca:ann.append('TARGET_CALL=1')
   print(f'V133_CTX=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
 print('\nV133_GOAL=find_all_Im_B2Y_Ctrl_Yc_Convert_callers_and_static_b2y_ctrl_ycc_instances_to_infer_local_pair_semantics_from_variation')
 print('OVERALL_VERDICT=V133_YC_CALLER_SURVEY_COMPLETE')
if __name__=='__main__':main()
