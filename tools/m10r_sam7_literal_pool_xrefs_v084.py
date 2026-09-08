#!/usr/bin/env python3
"""v0.84: trace IMG-SAM7 B2Y MMIO literal pools in ARM and Thumb modes.

v0.83 proved several diagnostic strings are immediately preceded by exact B2Y
MMIO page literals; the literal's high byte 0x20 had been mistaken for a
leading ASCII space. This probe resolves code references to those exact literal
slots in ARM and Thumb/Thumb-2 and emits bounded disassembly context.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

TARGET_LITS={
 'YNR_PAGE_20900':0x50624,
 'GAMMA_PAGE_20800':0x51f88,
 'YCC_PAGE_20900':0x51ff8,
 'PAGE_20A00_A':0x50658,
 'PAGE_20A00_B':0x7b4fa,
}

def ref_scan(data,lit,mode_name,mode,step):
 md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True;out=[]
 lo=max(0,lit-0x10000);hi=min(len(data)-4,lit+0x200)
 start=(lo//step)*step
 for off in range(start,hi,step):
  ins=next(md.disasm(data[off:off+4],off,count=1),None)
  if ins is None:continue
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    pc=(off+8) if mode_name=='ARM' else ((off+4)&~3)
    target=pc+int(op.mem.disp)
    if target==lit:
     out.append((off,ins.mnemonic,ins.op_str));break
 return out

def ctx(data,center,mode_name,mode,step,before=0x50,after=0x70):
 md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=False
 lo=max(0,center-before);hi=min(len(data),center+after)
 lo=(lo//step)*step
 return [(i.address,i.mnemonic,i.op_str) for i in md.disasm(data[lo:hi],lo)]

def ascii_after(data,lit,maxn=96):
 s=lit+4;e=s
 while e<len(data) and e<s+maxn and 32<=data[e]<127:e+=1
 return data[s:e].decode('ascii','replace')

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_literal_pool_xrefs_v084.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 print(f'V084_SAM7=file={row["file"]}|size=0x{len(data):x}|kind={row["kind"]}')
 total=0
 for label,lit in TARGET_LITS.items():
  val=struct.unpack_from('<I',data,lit)[0] if lit+4<=len(data) else None
  print(f'\nV084_LITERAL={label}|off=0x{lit:x}|value=0x{val:08x}|ascii_after={ascii_after(data,lit)}')
  for mode_name,mode,step in [('ARM',CS_MODE_ARM,4),('THUMB',CS_MODE_THUMB,2)]:
   refs=ref_scan(data,lit,mode_name,mode,step)
   print(f'V084_REFCOUNT={label}|mode={mode_name}|count={len(refs)}')
   for off,mn,ops in refs:
    total+=1
    print(f'V084_XREF={label}|mode={mode_name}|code=0x{off:x}|literal=0x{lit:x}|{mn} {ops}')
    for a,m,o in ctx(data,off,mode_name,mode,step):
     print(f'  V084_CTX={label}|mode={mode_name}|0x{a:x}|{m} {o}')
 print(f'\nV084_TOTAL_XREFS={total}')
 print('OVERALL_VERDICT=SAM7_MMIO_LITERAL_POOL_XREFS_TRACED_IN_ARM_AND_THUMB')
if __name__=='__main__':main()
