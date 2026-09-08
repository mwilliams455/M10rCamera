#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

S={
'HIGH_SCALE':'Im_B2Y_Set_HighEdge_Scale_Table error. write_ofs_num + array_num > MAX',
'LOW_SCALE':'Im_B2Y_Set_LowEdge_Scale_Table error. write_ofs_num + array_num > MAX',
'HIGH_STEP':'Im_B2Y_Set_HighEdge_Step_Table error. write_ofs_num + array_num > MAX',
'LOW_STEP':'Im_B2Y_Set_LowEdge_Step_Table error. write_ofs_num + array_num > MAX',
'HIGH_CTRL':'Im_B2Y_Ctrl_HighEdge error. b2y_ctrl_hedge = NULL',
'LOW_CTRL':'Im_B2Y_Ctrl_LowEdge error. b2y_ctrl_ledge = NULL',
'EDGE_BLEND':'Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL'}

def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: ... <sections>')
 d=Path(sys.argv[1]);b,base,fn=load(d)
 tg={k:base+b.find(v.encode()) for k,v in S.items()}; inv={v:k for k,v in tg.items()}
 print(f'V111_SAM7={fn}|base=0x{base:x}|size=0x{len(b):x}')
 for k,v in tg.items():print(f'V111_TARGET={k}|0x{v:08x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 hits=[]
 ring=[]
 for ins in md.disasm(b,base):
  ring.append((ins.address,ins.mnemonic,ins.op_str));ring=ring[-80:]
  pc=(ins.address+4)&~3
  found=None
  if ins.mnemonic.startswith('adr'):
   for o in ins.operands:
    if o.type==ARM_OP_IMM:
     imm=int(o.imm)
     for cand in (pc+imm,pc-imm):
      if cand in inv:found=(inv[cand],cand,f'ADR pc+/-imm imm=0x{imm:x}');break
  elif ins.mnemonic.startswith('ldr'):
   for o in ins.operands:
    if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
     la=pc+o.mem.disp;off=la-base
     if 0<=off<=len(b)-4:
      val=struct.unpack_from('<I',b,off)[0]
      if val in inv:found=(inv[val],val,f'LDR literal@0x{la:x}')
  if found:
   label,target,kind=found
   print(f'V111_XREF={label}|site=0x{ins.address:08x}|target=0x{target:08x}|{kind}')
   print('V111_PRE='+ ';'.join(f'0x{a:x}:{m} {o}' for a,m,o in ring[-50:]))
   # disassemble next 0x120 bytes directly from current instruction to capture validation/writer path
   off=ins.address-base
   for x in md.disasm(b[off:off+0x120],ins.address):
    print(f'V111_POST={label}|0x{x.address:08x}|{x.mnemonic} {x.op_str}')
   hits.append((label,ins.address))
 print(f'V111_HIT_COUNT={len(hits)}')
 print('OVERALL_VERDICT=V111_SAM7_EDGE_API_XREFS_DONE')
if __name__=='__main__':main()
