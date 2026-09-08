#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

NEEDLES=[
 b'I:Im_B2Y_Ctrl_Yc_Convert error. b2y_ctrl_ycc = NULL',
 b'Im_B2Y_Ctrl_Yc_Convert',
 b'b2y_ctrl_ycc',
]

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def litaddr(ins):
 try:
  ops=list(ins.operands)
  if len(ops)>=2 and ops[1].type==ARM_OP_MEM and ops[1].mem.base==ARM_REG_PC:
   return ((int(ins.address)+4)&~3)+int(ops[1].mem.disp)
 except:pass
 return None

def ins1(md,b,pc,base):
 o=pc-base
 return next(md.disasm(b[o:o+4],pc,count=1),None) if 0<=o<len(b) else None

def find_prologues(md,b,base,x,span=0x800):
 out=[]
 for pc in range(max(base,x-span)&~1,x+1,2):
  i=ins1(md,b,pc,base)
  if i and i.mnemonic=='push' and 'lr' in i.op_str:out.append(pc)
 return out[-8:]

def dump(md,b,base,a,z,label):
 print(f'\n=== V124_DUMP {label} 0x{a:08x}..0x{z:08x} ===')
 o=max(0,a-base);zz=min(len(b),z-base)
 for i in md.disasm(b[o:zz],a):
  ann=[]
  la=litaddr(i)
  if la is not None:
   lo=la-base
   if 0<=lo<=len(b)-4:
    v=u32(b,lo);ann.append(f'LIT=0x{la:08x}->0x{v:08x}')
  try:ops=list(i.operands)
  except:ops=[]
  if i.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ops[0].imm)&0xffffffff:08x}')
  print(f'V124_INS=0x{i.address:08x}|{i.mnemonic} {i.op_str}'+(('|'+'|'.join(ann)) if ann else ''))

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v124 <sections>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 b=(root/r['file']).read_bytes();base=int(r['image_base'],16)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 print(f'V124_SAM7={r["file"]}|base=0x{base:x}|size=0x{len(b):x}')
 straddrs=[]
 for needle in NEEDLES:
  start=0
  while True:
   q=b.find(needle,start)
   if q<0:break
   va=base+q;straddrs.append(va)
   print(f'V124_STRING=needle={needle.decode("ascii")}|off=0x{q:x}|va=0x{va:x}')
   start=q+1
 straddrs=sorted(set(straddrs))
 print('V124_STRING_ADDRS='+','.join(f'0x{x:x}' for x in straddrs))
 # Scan Thumb LDR-literal instructions that resolve to any string address.
 xrefs=[]
 for pc in range(base,base+len(b)-4,2):
  i=ins1(md,b,pc,base)
  if not i or not i.mnemonic.startswith('ldr'):continue
  la=litaddr(i)
  if la is None:continue
  lo=la-base
  if 0<=lo<=len(b)-4:
   v=u32(b,lo)
   if v in straddrs:
    xrefs.append((pc,v,la))
    print(f'V124_STRING_XREF=ins=0x{pc:x}|string=0x{v:x}|pool=0x{la:x}|op={i.mnemonic} {i.op_str}')
 funcs=[]
 for pc,sv,la in xrefs:
  ps=find_prologues(md,b,base,pc)
  print(f'V124_PROLOGUES=xref=0x{pc:x}|'+','.join(f'0x{x:x}' for x in ps))
  if ps:funcs.append(ps[-1])
 funcs=sorted(set(funcs));print('V124_FUNC_CANDIDATES='+','.join(f'0x{x:x}' for x in funcs))
 for f in funcs:
  dump(md,b,base,f,min(base+len(b),f+0x500),f'yc_api_0x{f:x}')
  # direct BL/BLX callers and pointer words
  callers=[]
  for pc in range(base,base+len(b)-4,2):
   i=ins1(md,b,pc,base)
   if not i or i.mnemonic not in ('bl','blx'):continue
   try:ops=list(i.operands)
   except:continue
   if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&~1)==(f&~1):callers.append(pc)
  ptr=[]
  for o in range(0,len(b)-3,4):
   v=u32(b,o)
   if v in (f,f|1):ptr.append(base+o)
  print(f'V124_FUNC_REFS=func=0x{f:x}|direct_calls={len(callers)}|ptr_words={len(ptr)}')
  print('V124_CALLERS='+','.join(f'0x{x:x}' for x in callers))
  print('V124_PTRS='+','.join(f'0x{x:x}' for x in ptr))
  for c in callers[:12]:dump(md,b,base,max(base,c-0x80),min(base+len(b),c+0x80),f'caller_0x{c:x}')
 print('OVERALL_VERDICT=V124_SAM7_YCCONVERT_API_STRING_XREFS_CALLERS_EXTRACTED')
if __name__=='__main__':main()
