#!/usr/bin/env python3
"""v1.01 — trace differential-gamma targets in their actual Thumb state."""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
ROOTS={0x000d15ec:'DG_record_0x0B',0x000d164c:'DG_record_0x1C',0x000d1694:'DG_record_0x1D'}

def md_new():m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m
def ins1(md,data,pc):return next(md.disasm(data[pc:pc+4],pc,count=1),None) if 0<=pc<len(data) else None
def bt(ins):
 try:ops=list(ins.operands)
 except:return None
 if ((ins.mnemonic.startswith('b') and ins.mnemonic not in ('bl','blx','bx','bxj','bic','bics')) or ins.mnemonic in ('cbz','cbnz')):
  for op in reversed(ops):
   if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
 return None
def ret(ins):return (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic in ('bx','bxj') and ins.op_str.strip()=='lr')
def cfg(md,data,start,span=0x800):
 lo=start;hi=min(len(data),start+span);todo=[start];seen=set();out={}
 while todo and len(out)<1200:
  pc=todo.pop()
  while lo<=pc<hi and pc not in seen:
   seen.add(pc);ins=ins1(md,data,pc)
   if not ins:break
   out[pc]=ins;t=bt(ins);n=pc+ins.size
   if t is not None and lo<=t<hi and t not in seen:todo.append(t)
   if ret(ins) or ins.mnemonic=='b':break
   pc=n
 return out
def u32(data,o):return struct.unpack_from('<I',data,o)[0] if 0<=o<=len(data)-4 else None
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: ... <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes();md=md_new()
 print(f'V101_IMG_SYSTEM=file={row["file"]}|mode=THUMB')
 for start,name in ROOTS.items():
  g=cfg(md,data,start);pages=set();calls=[]
  print(f'\n=== V101 {name} start=0x{start:08x} nodes={len(g)} ===')
  print(f'V101_ROOT_BYTES={data[start:start+32].hex()}')
  for pc in sorted(g):
   ins=g[pc];print(f'V101_INS=0x{pc:08x}|{ins.bytes.hex()}|{ins.mnemonic} {ins.op_str}')
   try:ops=list(ins.operands)
   except:ops=[]
   for op in ops:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     lit=((pc+4)&~3)+int(op.mem.disp);v=u32(data,lit)
     print(f'  V101_LITERAL=code=0x{pc:08x}|pool=0x{lit:08x}|value={"NONE" if v is None else f"0x{v:08x}"}')
     if v is not None and 0x20000000<=v<=0x200fffff:
      pages.add(v);print(f'  V101_MMIO=code=0x{pc:08x}|value=0x{v:08x}')
   if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
    t=int(ops[0].imm)&0xffffffff;calls.append(t);print(f'  V101_CALL=0x{pc:08x}->0x{t:08x}|{ins.mnemonic}')
  print(f'V101_ROOT_SUMMARY={name}|nodes={len(g)}|calls={len(calls)}|mmio={",".join(f"0x{x:08x}" for x in sorted(pages)) if pages else "NONE"}')
 print('OVERALL_VERDICT=DG_TARGETS_TRACED_IN_ACTUAL_THUMB_STATE')
if __name__=='__main__':main()
