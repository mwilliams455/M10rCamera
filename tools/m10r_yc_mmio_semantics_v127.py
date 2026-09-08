#!/usr/bin/env python3
from __future__ import annotations
import csv,re,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
BASEPTR=0x20020900
REGS={0x20,0x24,0x28,0x2c,0x30,0x34}
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def finds(b,pat):
 out=[];s=0
 while 1:
  q=b.find(pat,s)
  if q<0:return out
  out.append(q);s=q+1

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v127 <sections>')
 img,base,fn=load(Path(sys.argv[1]));print(f'V127_IMG={fn}|base=0x{base:x}|size=0x{len(img):x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 pools=finds(img,struct.pack('<I',BASEPTR));print('V127_BASE_POOLS='+','.join(f'0x{base+x:08x}' for x in pools))
 seen=set()
 for po in pools:
  pa=base+po
  # bounded search for instructions loading this literal pool entry
  a=max(base,pa-0x1200)&~1;z=min(base+len(img),pa+0x100)
  for ins in md.disasm(img[a-base:z-base],a):
   hit=False
   try:
    for op in ins.operands:
     if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
      p=((int(ins.address)+4)&~3)+int(op.mem.disp)
      if p==pa:hit=True
   except:pass
   if not hit or ins.address in seen:continue
   seen.add(ins.address)
   # disassemble local function-sized neighborhood and report only references to target registers
   ca=max(base,ins.address-0x100)&~1;cz=min(base+len(img),ins.address+0x280)
   local=list(md.disasm(img[ca-base:cz-base],ca))
   print(f'\nV127_BASE_XREF=0x{ins.address:08x}|pool=0x{pa:08x}')
   for q in local:
    relevant=(q.address==ins.address)
    try:
     for op in q.operands:
      if op.type==ARM_OP_MEM:
       disp=int(op.mem.disp)
       if disp in REGS: relevant=True
    except:pass
    if q.mnemonic=='push' or ((q.mnemonic=='pop' and 'pc' in q.op_str) or (q.mnemonic=='bx' and q.op_str.strip()=='lr')):relevant=True
    if relevant:
     ann=[]
     try:
      for op in q.operands:
       if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
        p=((int(q.address)+4)&~3)+int(op.mem.disp);oo=p-base
        if 0<=oo<=len(img)-4:ann.append(f'LIT=0x{p:08x}->0x{u32(img,oo):08x}')
     except:pass
     print(f'V127_INS=0x{q.address:08x}|{q.mnemonic} {q.op_str}'+(('|'+'|'.join(ann)) if ann else ''))

 print('\n######## B2Y / YC / BLEND STRING INVENTORY ########')
 for m in re.finditer(rb'[ -~]{6,}',img):
  s=m.group().decode('ascii','ignore');sl=s.lower()
  if any(k in sl for k in ('yblend','y_blend','yc_convert','yctorgb','rgbtoyc','yc to rgb','rgb to yc','b2y')):
   if len(s)<=220:print(f'V127_STRING=0x{base+m.start():08x}|{s}')
 print('\nV127_GOAL=find_getters_diagnostics_or_adjacent_APIs_reading_YcConvert_and_Y_BLEND_local_registers_and_surface_symbolic_terminology')
 print('OVERALL_VERDICT=V127_YC_MMIO_SEMANTICS_COMPLETE')
if __name__=='__main__':main()
