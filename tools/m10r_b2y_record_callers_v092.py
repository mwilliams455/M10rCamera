#!/usr/bin/env python3
"""v0.92: crosswalk IMG-System B2Y calibration record IDs to lookup callers.

The common calibration lookup is the v0.72-proven Thumb function at section
offset 0x1a0fc4. For every BL to it, recover the nearest preceding assignment
to r1 (record id), caller prologue, and nearby printable diagnostics. Focus on
0x0b..0x18 and 0x26 but report every immediate id recovered.
"""
from __future__ import annotations
import csv,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_REG
LOOKUP_OFF=0x1a0fc4
FOCUS=set(range(0x0b,0x19))|{0x26}

def strings(data,lo,hi,minlen=8):
 out=[];i=max(0,lo);hi=min(len(data),hi)
 while i<hi:
  if 32<=data[i]<127:
   j=i
   while j<hi and 32<=data[j]<127:j+=1
   if j-i>=minlen:out.append((i,data[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: ... <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes();base=int(row['image_base'],16);target=base+LOOKUP_OFF
 print(f'V092_IMG_SYSTEM=file={row["file"]}|size=0x{len(data):x}|base=0x{base:08x}|lookup_va=0x{target:08x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
 # Decode full Thumb stream one instruction at a time so branch targets remain explicit.
 insns=[]
 for off in range(0,len(data)-4,2):
  ins=next(md.disasm(data[off:off+4],base+off,count=1),None)
  if ins:insns.append((off,ins))
 calls=[]
 for idx,(off,ins) in enumerate(insns):
  if ins.mnemonic not in ('bl','blx'):continue
  try:ops=list(ins.operands)
  except Exception:continue
  if not ops or ops[0].type!=ARM_OP_IMM or (int(ops[0].imm)&0xffffffff)!=(target&0xffffffff):continue
  rid=None;rid_off=None
  # Nearest explicit immediate write to r1 in preceding 12 instructions.
  for j in range(idx-1,max(-1,idx-13),-1):
   po,pi=insns[j]
   if off-po>0x30:break
   try:pops=list(pi.operands)
   except Exception:continue
   if len(pops)>=2 and pops[0].type==ARM_OP_REG and md.reg_name(pops[0].reg)=='r1' and pops[1].type==ARM_OP_IMM and pi.mnemonic in ('movs','mov','mov.w'):
    rid=int(pops[1].imm)&0xffffffff;rid_off=po;break
  # Nearest push{...,lr} prologue before call.
  start=None
  for j in range(idx-1,max(-1,idx-300),-1):
   po,pi=insns[j]
   if off-po>0x400:break
   if pi.mnemonic=='push' and 'lr' in pi.op_str:start=po;break
  calls.append((off,rid,rid_off,start))
 print(f'V092_LOOKUP_CALL_COUNT={len(calls)}')
 for off,rid,rid_off,start in calls:
  tag='FOCUS' if rid in FOCUS else 'OTHER'
  print(f'\nV092_CALL=off=0x{off:x}|va=0x{base+off:08x}|record={hex(rid) if rid is not None else "UNKNOWN"}|rid_set={hex(rid_off) if rid_off is not None else "NONE"}|func={hex(start) if start is not None else "NONE"}|{tag}')
  if rid in FOCUS:
   # Instruction context.
   nearby=[(o,i) for o,i in insns if off-0x30<=o<=off+0x30]
   for o,i in nearby:print(f'  V092_INS=0x{o:x}|{i.mnemonic} {i.op_str}')
   for so,s in strings(data,(start if start is not None else off)-0x180,off+0x300):
    if any(k.lower() in s.lower() for k in ('b2y','tone','clip','blend','yc','gamma','matrix','color','chroma','jpeg','wb')):
     print(f'  V092_ASCII=0x{so:x}|{s}')
 # Compact crosswalk.
 print('\n=== V092 RECORD CROSSWALK ===')
 by={}
 for off,rid,rid_off,start in calls:
  if rid is not None:by.setdefault(rid,[]).append((off,start))
 for rid in sorted(by):
  print(f'V092_RECORD=0x{rid:x}|calls={len(by[rid])}|sites={",".join(f"0x{o:x}" for o,_ in by[rid])}|funcs={",".join("NONE" if s is None else f"0x{s:x}" for _,s in by[rid])}')
 print('OVERALL_VERDICT=B2Y_CALIBRATION_RECORD_LOOKUP_CALLERS_CROSSWALKED_FROM_EXECUTABLE_CODE')
if __name__=='__main__':main()
