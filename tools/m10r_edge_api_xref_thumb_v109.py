#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

TARGETS=[
 ('HIGH_SCALE','Im_B2Y_Set_HighEdge_Scale_Table error. write_ofs_num + array_num > MAX'),
 ('LOW_SCALE','Im_B2Y_Set_LowEdge_Scale_Table error. write_ofs_num + array_num > MAX'),
 ('HIGH_STEP','Im_B2Y_Set_HighEdge_Step_Table error. write_ofs_num + array_num > MAX'),
 ('LOW_STEP','Im_B2Y_Set_LowEdge_Step_Table error. write_ofs_num + array_num > MAX'),
 ('HIGH_CTRL','Im_B2Y_Ctrl_HighEdge error. b2y_ctrl_hedge = NULL'),
 ('LOW_CTRL','Im_B2Y_Ctrl_LowEdge error. b2y_ctrl_ledge = NULL'),
 ('EDGE_BLEND','Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL'),
]

def sec(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def find_string(data,base,s):
 p=data.find(s.encode());return None if p<0 else base+p

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_edge_api_xref_thumb_v109.py <sections>')
 d=Path(sys.argv[1]);data,base,fn=sec(d)
 t={label:find_string(data,base,s) for label,s in TARGETS}
 print(f'V109_SAM7={fn}|base=0x{base:08x}|size=0x{len(data):x}')
 for k,v in t.items():print(f'V109_TARGET={k}|{"NONE" if v is None else f"0x{v:08x}"}')
 wanted={v:k for k,v in t.items() if v is not None}
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 hits=[];insns=[]
 for ins in md.disasm(data,base):
  insns.append(ins)
  # ADR is decoded with an immediate destination by Capstone.
  if ins.mnemonic.startswith('adr'):
   try:
    for op in ins.operands:
     if op.type==ARM_OP_IMM and int(op.imm) in wanted:hits.append((ins.address,wanted[int(op.imm)],'ADR',int(op.imm)))
   except:pass
  # LDR Rt,[PC,#disp] -> literal pool word -> possible string address.
  if ins.mnemonic.startswith('ldr'):
   try:
    for op in ins.operands:
     if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
      la=((ins.address+4)&~3)+op.mem.disp
      off=la-base
      if 0<=off<=len(data)-4:
       val=struct.unpack_from('<I',data,off)[0]
       if val in wanted:hits.append((ins.address,wanted[val],f'LDR_LITERAL@0x{la:08x}',val))
   except:pass
 print('\n=== V109_STRING_CODE_XREFS ===')
 for h in hits:print(f'V109_XREF=site=0x{h[0]:08x}|target={h[1]}|kind={h[2]}|string=0x{h[3]:08x}')

 # Build address->index to recover a conservative function window: nearest push
 # containing lr within 160 instructions before the reference, then through first
 # return (pop pc or bx lr) after it.
 idx={x.address:i for i,x in enumerate(insns)}
 print('\n=== V109_API_FUNCTION_WINDOWS ===')
 for site,label,kind,val in hits:
  i=idx.get(site)
  if i is None:continue
  s=max(0,i-160)
  for j in range(i,max(-1,i-160),-1):
   x=insns[j]
   if x.mnemonic.startswith('push') and ('lr' in x.op_str):s=j;break
  e=min(len(insns),i+220)
  for j in range(i,min(len(insns),i+220)):
   x=insns[j]
   if (x.mnemonic.startswith('pop') and 'pc' in x.op_str) or (x.mnemonic=='bx' and x.op_str.strip()=='lr'):
    e=j+1;break
  print(f'V109_FUNC={label}|xref=0x{site:08x}|start=0x{insns[s].address:08x}|end=0x{insns[e-1].address:08x}')
  for x in insns[s:e]:print(f'V109_INS=0x{x.address:08x}|{x.mnemonic} {x.op_str}')

 print('\n=== V109_EDGE_API_ADJACENT_CALL_TARGETS ===')
 # Calls in recovered windows expose generic SRAM/table-write helpers shared by
 # scale/step functions. Print all BL/BLX instructions within +/-0x180 of xrefs.
 seen=set()
 for site,label,_,_ in hits:
  for x in insns[max(0,idx[site]-120):min(len(insns),idx[site]+160)]:
   if x.mnemonic in ('bl','blx'):
    key=(label,x.address,x.op_str)
    if key not in seen:
     seen.add(key);print(f'V109_CALL={label}|site=0x{x.address:08x}|{x.mnemonic} {x.op_str}')
 print('OVERALL_VERDICT=V109_THUMB_PC_RELATIVE_EDGE_API_XREFS_EXTRACTED')
if __name__=='__main__':main()
