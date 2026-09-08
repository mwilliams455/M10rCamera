#!/usr/bin/env python3
"""v0.79: map IMG-SAM7 B2Y control diagnostic strings to code references.

Targets: Gamma, CC1, Yc_Convert, Chroma_Suppress, Color_NR, PostFilter and
EdgeBlend. The probe uses the firmware section's declared image_base and tries
both ARM and Thumb PC-relative literal references. It reports evidence only;
architecture/mode is not frozen unless refs are coherent.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

TARGETS={
 'GAMMA':'Im_B2Y_Ctrl_Gamma error. b2y_ctrl_gamma = NULL',
 'CC1':'Im_B2Y_Ctrl_CC_Matrix error. b2y_ctrl_cc1 = NULL',
 'YCC':'Im_B2Y_Ctrl_Yc_Convert error. b2y_ctrl_ycc = NULL',
 'CHROMA_SUPPRESS':'Im_B2Y_Ctrl_Chroma_Suppress error. b2y_ctrl_cs = NULL',
 'COLOR_NR':'Im_B2Y_Ctrl_Color_NR error. b2y_ctrl_clpf = NULL',
 'POSTFILTER':'Im_B2Y_Ctrl_PostFilter error. b2y_ctrl_post_filter = NULL',
 'EDGEBLEND':'Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL',
}

def u32(b,o):return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def ascii_near(data,off,r=0x300):
 lo=max(0,off-r);hi=min(len(data),off+r);out=[];i=lo
 while i<hi:
  if 32<=data[i]<127:
   j=i
   while j<hi and 32<=data[j]<127:j+=1
   if j-i>=10:out.append((i,data[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def refs_for_literal(data,base,lit_off,mode_name,mode,step):
 md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True;refs=[]
 start=max(0,lit_off-0x3000);end=min(len(data)-4,lit_off+0x100)
 for off in range(start,end,step):
  ins=next(md.disasm(data[off:off+4],base+off,count=1),None)
  if ins is None:continue
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    # ARM uses PC+8; Thumb uses aligned PC+4. Capstone address gives current VA.
    pc=((ins.address+8) if mode_name=='ARM' else ((ins.address+4)&~3))
    po=(pc+int(op.mem.disp))-base
    if po==lit_off:
     refs.append((off,ins.mnemonic,ins.op_str));break
 return refs

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_b2y_control_xrefs_v079.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7')
 data=(root/row['file']).read_bytes();base=int(row['image_base'],16)
 print(f'V079_SAM7=file={row["file"]}|size=0x{len(data):x}|image_base=0x{base:08x}|kind={row["kind"]}')
 for label,needle in TARGETS.items():
  # strings may have leading noise chars, so search stable suffix.
  stable=needle.encode('ascii')
  off=data.find(stable)
  if off<0:
   # fallback to core function phrase
   core=needle.split(' error.')[0].encode('ascii');off=data.find(core);stable=core
  print(f'\nV079_TARGET={label}|string_off={hex(off) if off>=0 else "NONE"}|string_va={hex(base+off) if off>=0 else "NONE"}')
  if off<0:continue
  va=base+off
  ptr=struct.pack('<I',va&0xffffffff);pos=0;lits=[]
  while True:
   q=data.find(ptr,pos)
   if q<0:break
   lits.append(q);pos=q+1
  print(f'V079_PTRS={label}|count={len(lits)}|offs={",".join(hex(x) for x in lits)}')
  for lit in lits:
   for mode_name,mode,step in [('ARM',CS_MODE_ARM,4),('THUMB',CS_MODE_THUMB,2)]:
    refs=refs_for_literal(data,base,lit,mode_name,mode,step)
    for ro,m,ops in refs:
     print(f'V079_XREF={label}|mode={mode_name}|code_off=0x{ro:x}|va=0x{base+ro:08x}|literal_off=0x{lit:x}|{m} {ops}')
     for so,s in ascii_near(data,ro,0x180):
      if 'Im_B2Y' in s or 'b2y_ctrl' in s:
       print(f'  V079_NEAR_ASCII=0x{so:x}|{s}')
 print('\nOVERALL_VERDICT=SAM7_B2Y_CONTROL_STRING_XREFS_ENUMERATED')
if __name__=='__main__':main()
