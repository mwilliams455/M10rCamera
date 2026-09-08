#!/usr/bin/env python3
"""v0.98 — trace IMG-System OFFSET and TONE CONTROL downstream call trees.

v0.95 binds:
  record 0x02 OFFSET -> 0x000d3284
  records 0x08/0x19/0x1a TONE CONTROL -> 0x000d3c20
This probe follows reachable direct calls (bounded depth) and resolves all
0x200xxxxx PC-relative MMIO literals.  Anchors Y_BLEND and YC_CONVERSION are
included as controls.  Purpose: determine whether OFFSET/TONE touch the same
YC output neighborhoods or distinct B2Y hardware stages.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
ROOTS={0x000d3284:'OFFSET_record_0x02',0x000d3c20:'TONE_records_0x08_0x19_0x1a',0x000d4480:'Y_BLEND_anchor',0x000d4570:'YC_CONVERSION_anchor'}
DEPTH=3

def md_new():m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m

def ins1(md,data,pc):return next(md.disasm(data[pc:pc+4],pc,count=1),None) if 0<=pc<len(data) else None

def bt(ins):
 try:ops=list(ins.operands)
 except:return None
 if ((ins.mnemonic.startswith('b') and ins.mnemonic not in ('bl','blx','bx','bxj')) or ins.mnemonic in ('cbz','cbnz')):
  for op in reversed(ops):
   if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
 return None

def ret(ins):return (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic in ('bx','bxj') and ins.op_str.strip()=='lr')
def cfg(md,data,start,span=0x1200):
 lo=max(0,start-0x10);hi=min(len(data),start+span);todo=[start];seen=set();out={}
 while todo and len(out)<2500:
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

def direct_calls(g):
 out=[]
 for pc,ins in g.items():
  try:ops=list(ins.operands)
  except:continue
  if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:out.append((pc,int(ops[0].imm)&0xffffffff))
 return sorted(out)

def mmios(g,data):
 out=[]
 for pc,ins in g.items():
  try:ops=list(ins.operands)
  except:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    lit=((pc+4)&~3)+int(op.mem.disp);v=u32(data,lit)
    if v is not None and 0x20000000<=v<=0x200fffff:out.append((pc,lit,v,ins.mnemonic,ins.op_str))
 return sorted(set(out))

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_b2y_offset_tone_calltree_v098.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes();md=md_new()
 for rv,label in ROOTS.items():
  print(f'\n=== V098 ROOT {label} 0x{rv:08x} ===')
  q=[(rv,0)];seen=set();tree=[];allmm=[]
  while q:
   va,dep=q.pop(0)
   if va in seen or not (0<=va<len(data)) or dep>DEPTH:continue
   seen.add(va);g=cfg(md,data,va);cs=direct_calls(g);mm=mmios(g,data);tree.append((va,dep,cs,mm));allmm+=mm
   print(f'V098_FUNC=0x{va:08x}|depth={dep}|nodes={len(g)}|calls={len(cs)}|mmio={",".join(sorted({f"0x{x[2]:08x}" for x in mm})) or "NONE"}')
   for pc,t in cs:print(f'  V098_CALL=0x{pc:08x}->0x{t:08x}')
   for pc,lit,v,mn,op in mm:print(f'  V098_MMIO=code=0x{pc:08x}|pool=0x{lit:08x}|value=0x{v:08x}|{mn} {op}')
   if dep<DEPTH:
    for _,t in cs:
     if 0<=t<len(data) and t not in seen:q.append((t,dep+1))
  pages=sorted(set(x[2] for x in allmm))
  print(f'V098_ROOT_SUMMARY={label}|root=0x{rv:08x}|functions={len(tree)}|pages={",".join(f"0x{x:08x}" for x in pages) or "NONE"}')
 print('\nV098_KNOWN_YC_PAGES=Yc_Convert:0x20020900|YC_Output_neighborhood:0x20022580,0x20022600,0x20022500')
 print('OVERALL_VERDICT=OFFSET_AND_TONE_DOWNSTREAM_MMIO_TOPOLOGY_TRACED_AGAINST_YC_ANCHORS')
if __name__=='__main__':main()
