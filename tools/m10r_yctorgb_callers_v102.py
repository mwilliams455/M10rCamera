#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

TARGET=0x0004F8A4
SCAN_PAD=0x180

def mdnew():
 m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m

def u32(data,o):
 if o<0 or o+4>len(data):return None
 return struct.unpack_from('<I',data,o)[0]

def isret(ins):return (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic in ('bx','bxj') and ins.op_str.strip()=='lr')

def ins1(md,data,pc):return next(md.disasm(data[pc:pc+4],pc,count=1),None) if 0<=pc<len(data) else None

def direct_calls(md,data):
 out=[]
 for pc in range(0,len(data)-4,2):
  ins=ins1(md,data,pc)
  if not ins or ins.mnemonic not in ('bl','blx'):continue
  try:ops=list(ins.operands)
  except Exception:continue
  if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&0xffffffff)==TARGET:out.append(pc)
 return out

def starts(md,data,xref):
 cand=[]
 for pc in range(max(0,xref-0x800)&~1,xref+1,2):
  ins=ins1(md,data,pc)
  if ins and ins.mnemonic=='push' and 'lr' in ins.op_str:cand.append(pc)
 return cand[-8:]

def dump_window(md,data,lo,hi,label):
 print(f'\n=== V102_WINDOW {label} 0x{lo:x}..0x{hi:x} ===')
 for ins in md.disasm(data[lo:hi],lo):
  print(f'V102_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')
  try:ops=list(ins.operands)
  except Exception:ops=[]
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    lit=((int(ins.address)+4)&~3)+int(op.mem.disp);v=u32(data,lit)
    if v is not None:
     extra=''
     if 0x20000000<=v<=0x20ffffff:extra='|MMIO=1'
     if 0<=v<len(data):extra+='|IN_IMAGE=1'
     print(f'V102_LITERAL=ins=0x{ins.address:08x}|pool=0x{lit:08x}|value=0x{v:08x}{extra}')

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_yctorgb_callers_v102.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes();md=mdnew()
 print(f'V102_SAM7={row["file"]}|size=0x{len(data):x}|target=0x{TARGET:x}')
 calls=direct_calls(md,data);print(f'V102_DIRECT_CALL_COUNT={len(calls)}')
 for i,x in enumerate(calls):
  print(f'V102_DIRECT_CALL=idx={i}|site=0x{x:x}|target=0x{TARGET:x}')
  ss=starts(md,data,x)
  print('V102_PROLOGUE_CANDIDATES='+','.join(f'0x{s:x}' for s in ss))
  lo=max(0,(ss[-1] if ss else x-SCAN_PAD));hi=min(len(data),x+SCAN_PAD)
  dump_window(md,data,lo,hi,f'call_{i}')

 # Thumb function pointers can carry bit0=1; scan for both aligned and Thumb values.
 ptrs=[]
 for pc in range(0,len(data)-3,4):
  v=u32(data,pc)
  if v in (TARGET,TARGET|1):ptrs.append((pc,v))
 print(f'\nV102_POINTER_WORD_COUNT={len(ptrs)}')
 for pc,v in ptrs:print(f'V102_POINTER_WORD=at=0x{pc:x}|value=0x{v:08x}')

 # Dump the target itself, including all mode branches and literals.
 dump_window(md,data,TARGET,min(len(data),TARGET+0x260),'YCtoRGB_target')
 print('OVERALL_VERDICT=V102_YCTORGB_DIRECT_CALLERS_POINTERS_AND_CALL_ARGUMENT_CONTEXT_EXTRACTED')
if __name__=='__main__':main()
