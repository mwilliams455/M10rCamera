#!/usr/bin/env python3
"""v0.99 — resolve the tiny OFFSET/TONE downstream targets from v0.98.

0xd3284 (OFFSET) and 0xd3c20 (TONE CONTROL) did not decode like the direct
MMIO setters.  Dump exact bytes/instructions, resolve PC literals, branch
immediates and all code xrefs so we can distinguish no-op/state setters from
veneers before using them for topology.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
ROOTS={0x000d3284:'OFFSET',0x000d3c20:'TONE_CONTROL',0x000d4480:'Y_BLEND_CONTROL'}

def u32(b,o):return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: ... <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes()
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
 for va,name in ROOTS.items():
  print(f'\n=== V099 {name} 0x{va:08x} ===')
  print(f'V099_BYTES={data[va:va+0x60].hex()}')
  for ins in md.disasm(data[va:va+0x100],va):
   print(f'V099_INS=0x{ins.address:08x}|{ins.bytes.hex()}|{ins.mnemonic} {ins.op_str}')
   try:ops=list(ins.operands)
   except:ops=[]
   for op in ops:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     lit=((int(ins.address)+4)&~3)+int(op.mem.disp);v=u32(data,lit)
     print(f'  V099_LITERAL=pool=0x{lit:08x}|value={"NONE" if v is None else f"0x{v:08x}"}')
   if ins.mnemonic in ('bl','blx') or (ins.mnemonic.startswith('b') and ins.mnemonic not in ('bic','bics')):
    for op in ops:
     if op.type==ARM_OP_IMM:print(f'  V099_BRANCH_TARGET=0x{int(op.imm)&0xffffffff:08x}')
   if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic in ('bx','bxj') and ins.op_str.strip()=='lr'):
    print(f'V099_FIRST_RETURN=0x{ins.address:08x}');break
  print('V099_XREFS:')
  count=0
  lo=max(0,va-0x100000);hi=min(len(data)-4,va+0x100000)
  for off in range(lo&~1,hi,2):
   ins=next(md.disasm(data[off:off+4],off,count=1),None)
   if not ins or ins.mnemonic not in ('bl','blx'):continue
   try:ops=list(ins.operands)
   except:continue
   if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&0xffffffff)==va:
    count+=1;print(f'V099_XREF=0x{off:08x}|{ins.mnemonic} {ins.op_str}')
  print(f'V099_XREF_COUNT={count}')
 print('OVERALL_VERDICT=OFFSET_AND_TONE_TINY_TARGETS_CLASSIFIED_FROM_EXACT_INSTRUCTIONS')
if __name__=='__main__':main()
