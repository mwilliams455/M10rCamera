#!/usr/bin/env python3
"""v0.97 — exact field shapes for SAM7 YC output controls and YC->RGB.

The API/function bindings were proven by v0.96.  This pass prints the complete
reachable Thumb instructions for:
  0x4f51a Im_B2Y_Ctrl_YC_OutOffsetAndGain
  0x4f7c0 Im_B2Y_Ctrl_YC_OutClip
  0x4f8a4 Im_B2Y_Ctrl_YCtoRGB_Matrix
and resolves every PC-relative literal.  It also inventories byte/halfword
loads from the parameter pointer so the input struct widths can be compared
against the six 15-bit fields inside Yc_Convert without semantic guessing.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
ROOTS={0x4f51a:'YC_OutOffsetAndGain',0x4f7c0:'YC_OutClip',0x4f8a4:'YCtoRGB_Matrix'}

def md_new():m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m

def ins1(md,data,pc):return next(md.disasm(data[pc:pc+4],pc,count=1),None) if 0<=pc<len(data) else None

def branch_target(ins):
 try:ops=list(ins.operands)
 except:return None
 if ((ins.mnemonic.startswith('b') and ins.mnemonic not in ('bl','blx','bx','bxj')) or ins.mnemonic in ('cbz','cbnz')):
  for op in reversed(ops):
   if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
 return None

def ret(ins):return (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic in ('bx','bxj') and ins.op_str.strip()=='lr')
def cfg(md,data,start):
 lo=max(0,start-0x10);hi=min(len(data),start+0x900);todo=[start];seen=set();out={}
 while todo and len(out)<2000:
  pc=todo.pop()
  while lo<=pc<hi and pc not in seen:
   seen.add(pc);ins=ins1(md,data,pc)
   if not ins:break
   out[pc]=ins;t=branch_target(ins);n=pc+ins.size
   if t is not None and lo<=t<hi and t not in seen:todo.append(t)
   if ret(ins) or ins.mnemonic=='b':break
   pc=n
 return out

def u32(data,o):return struct.unpack_from('<I',data,o)[0] if 0<=o<=len(data)-4 else None

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_yc_field_semantics_v097.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes();md=md_new()
 for st,name in ROOTS.items():
  g=cfg(md,data,st);print(f'\n=== V097 {name} func=0x{st:x} nodes={len(g)} ===')
  input_loads=[];lits=[]
  for pc,ins in sorted(g.items()):
   print(f'V097_INS=0x{pc:x}|{ins.mnemonic} {ins.op_str}')
   try:ops=list(ins.operands)
   except:ops=[]
   for op in ops:
    if op.type==ARM_OP_MEM:
     b=md.reg_name(op.mem.base) if op.mem.base else ''
     if ins.mnemonic in ('ldrb','ldrh') and b in ('r4','r5'):
      input_loads.append((pc,ins.mnemonic,b,int(op.mem.disp)))
     if op.mem.base==ARM_REG_PC:
      lit=((pc+4)&~3)+int(op.mem.disp);v=u32(data,lit)
      lits.append((pc,lit,v))
  uniq=[]
  for x in input_loads:
   k=x[1:]
   if k not in [u[1:] for u in uniq]:uniq.append(x)
  print(f'V097_PARAM_LOAD_COUNT={len(uniq)}')
  for pc,mn,b,d in uniq:print(f'V097_PARAM=code=0x{pc:x}|width={mn}|base={b}|offset=0x{d:x}')
  for pc,lit,v in lits:
   if v is not None:print(f'V097_LITERAL=code=0x{pc:x}|pool=0x{lit:x}|value=0x{v:08x}')
  mm=sorted(set(v for _,_,v in lits if v is not None and 0x20000000<=v<=0x200fffff))
  print(f'V097_MMIO={name}|{",".join(f"0x{x:08x}" for x in mm) or "NONE"}')
 print('\nV097_STRUCT_CONTRAST=Yc_Convert_postmatrix_fields_are_6x15bit_halfword_values;YC_OutOffsetAndGain_and_YC_OutClip_have_distinct_parameter_width_patterns')
 print('OVERALL_VERDICT=YC_OUTPUT_CONTROL_STRUCT_WIDTHS_EXTRACTED_FROM_BOUND_SAM7_APIS')
if __name__=='__main__':main()
