#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

CALLS=[0x00154E68,0x00154F1C]
TARGETS={0x000D4480:'Y_BLEND_SETTER',0x000D4570:'YC_CONVERT_SETTER'}

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def ins1(md,b,base,pc):
 o=pc-base
 return next(md.disasm(b[o:o+4],pc,count=1),None) if 0<=o<len(b) else None

def prologues(md,b,base,x,span=0x1000):
 out=[]
 for pc in range(max(base,x-span)&~1,x+1,2):
  i=ins1(md,b,base,pc)
  if i and i.mnemonic=='push' and 'lr' in i.op_str:out.append(pc)
 return out[-12:]

def fmt(i,b,base):
 ann=[]
 try:ops=list(i.operands)
 except:ops=[]
 for op in ops:
  if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
   la=((int(i.address)+4)&~3)+int(op.mem.disp);o=la-base
   if 0<=o<=len(b)-4:
    v=u32(b,o);ann.append(f'LIT=0x{la:08x}->0x{v:08x}')
    if 0x20000000<=v<=0x20ffffff:ann.append('MMIO=1')
 if i.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
  t=int(ops[0].imm)&0xffffffff;ann.append(f'CALL=0x{t:08x}')
  if (t&~1) in {k&~1 for k in TARGETS}:ann.append('TARGET='+TARGETS[next(k for k in TARGETS if (k&~1)==(t&~1))])
 return f'0x{i.address:08x}|{i.mnemonic} {i.op_str}'+(('|'+'|'.join(ann)) if ann else '')

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v125 <sections>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 b=(root/r['file']).read_bytes();base=int(r['image_base'],16);md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 print(f'V125_IMG={r["file"]}|base=0x{base:x}|size=0x{len(b):x}')
 starts=[]
 for c in CALLS:
  ps=prologues(md,b,base,c);print(f'V125_PROLOGUES=call=0x{c:x}|'+','.join(f'0x{x:x}' for x in ps))
  if ps:starts.append(ps[-1])
 if starts:
  a=min(starts);z=max(CALLS)+0x180
 else:a=min(CALLS)-0x300;z=max(CALLS)+0x180
 print(f'V125_RANGE=0x{a:x}..0x{z:x}')
 for i in md.disasm(b[a-base:z-base],a):print('V125_INS='+fmt(i,b,base))
 # Report every direct call in function-sized region and known setter ordering.
 seq=[]
 for i in md.disasm(b[a-base:z-base],a):
  try:ops=list(i.operands)
  except:ops=[]
  if i.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
   t=int(ops[0].imm)&0xffffffff;seq.append((i.address,t))
 print('V125_CALLSEQ='+','.join(f'0x{x:x}->0x{t:x}' for x,t in seq))
 known=[(x,t,TARGETS[t&~1]) for x,t in seq if (t&~1) in TARGETS]
 print('V125_KNOWN_ORDER='+','.join(f'0x{x:x}:{n}' for x,t,n in known))
 print('OVERALL_VERDICT=V125_YBLEND_YCCONVERT_APPLICATION_CALLER_ORDER_EXTRACTED')
if __name__=='__main__':main()
