#!/usr/bin/env python3
from __future__ import annotations
import csv,re,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

TARGETS={0x000d4480:'Y_BLEND_SETTER',0x000d4570:'YC_CONVERT_SETTER'}
STRINGS={0x00154e98:'Y_BLEND_SELECT_STRING',0x00154f2c:'YC_CONVERSION_STRING'}
DUMP_A=0x000d4460; DUMP_Z=0x000d47c0

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def pc_lit(ins):
 try:
  if ins.mnemonic.startswith('ldr') and len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base==ARM_REG_PC:
   return ((int(ins.address)+4)&~3)+int(ins.operands[1].mem.disp)
 except: pass
 return None

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v124 <sections>')
 img,base,fn=load(Path(sys.argv[1]));print(f'V124_IMG={fn}|base=0x{base:x}|size=0x{len(img):x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 print(f'\n######## V124_EXACT_DISASM 0x{DUMP_A:08x}..0x{DUMP_Z:08x} ########')
 off=DUMP_A-base
 for ins in md.disasm(img[off:off+(DUMP_Z-DUMP_A)],DUMP_A):
  ann=[];p=pc_lit(ins)
  if p is not None:
   po=p-base
   if 0<=po<=len(img)-4: ann.append(f'LIT=0x{p:08x}->0x{u32(img,po):08x}')
  if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:
   ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
  if ins.mnemonic=='push':ann.append('PROLOGUE=1')
  if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):ann.append('RETURN=1')
  print(f'V124_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))

 print('\n######## V124_DIRECT_CALLERS ########')
 allins=list(md.disasm(img,base))
 for ins in allins:
  if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:
   t=int(ins.operands[0].imm)&~1
   if t in TARGETS: print(f'V124_CALLER={TARGETS[t]}|at=0x{ins.address:08x}|target=0x{t:08x}')

 print('\n######## V124_STORED_POINTERS ########')
 for t,name in TARGETS.items():
  pats=[struct.pack('<I',t),struct.pack('<I',t|1)]
  hits=[]
  for pat in pats:
   start=0
   while True:
    q=img.find(pat,start)
    if q<0:break
    hits.append(base+q);start=q+1
  print(f'V124_POINTERS={name}|'+','.join(f'0x{x:08x}' for x in sorted(set(hits))))

 print('\n######## V124_STRING_XREFS ########')
 for sa,sname in STRINGS.items():
  print(f'V124_STRING_TARGET={sname}|0x{sa:08x}')
  # PC-relative LDR refs whose literal pool contains exact string address.
  for ins in allins:
   p=pc_lit(ins)
   if p is None:continue
   po=p-base
   if 0<=po<=len(img)-4 and u32(img,po)==sa:
    print(f'V124_STRING_XREF={sname}|ins=0x{ins.address:08x}|pool=0x{p:08x}')
  # raw stored pointer refs
  pat=struct.pack('<I',sa);start=0
  while True:
   q=img.find(pat,start)
   if q<0:break
   print(f'V124_STRING_PTR={sname}|0x{base+q:08x}');start=q+1

 print('\n######## V124_NEARBY_STRINGS ########')
 for m in re.finditer(rb'[ -~]{7,}',img):
  a=base+m.start()
  if 0x00154d00<=a<=0x00155100:
   print(f'V124_CSTR=0x{a:08x}|{m.group().decode("ascii","ignore")}')
 print('\nV124_GOAL=prove_function_boundaries_and_trace_selector_or_dispatch_paths_for_Y_BLEND_and_Yc_Convert')
 print('OVERALL_VERDICT=V124_YBLEND_YC_CALLER_TRACE_COMPLETE')
if __name__=='__main__':main()
