#!/usr/bin/env python3
"""v0.83: recover SAM7 B2Y control xrefs via MOVW/MOVT and MMIO literals.

The IMG-SAM7 image begins with valid ARM code but v0.79-v0.81 found no direct
string-pointer literals/ADR references. ARM compilers commonly materialize
addresses with MOVW/MOVT pairs, so this probe detects such pairs for the named
B2Y controls. It also searches the exact IMG-System B2Y MMIO page 0x20020900
and nearby page bases for literal/code references.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_REG,ARM_OP_MEM,ARM_REG_PC

TARGETS={
 'GAMMA':'Im_B2Y_Ctrl_Gamma error. b2y_ctrl_gamma = NULL',
 'CC1':'Im_B2Y_Ctrl_CC_Matrix error. b2y_ctrl_cc1 = NULL',
 'YCC':'Im_B2Y_Ctrl_Yc_Convert error. b2y_ctrl_ycc = NULL',
 'YCTORG':'Im_B2Y_Ctrl_YCtoRGB_Matrix error.',
 'RGBTOYC':'Im_B2Y_Ctrl_RGBtoYC_Matrix error.',
 'YC_GAIN':'Im_B2Y_Ctrl_YC_OutOffsetAndGain error.',
 'YC_CLIP':'Im_B2Y_Ctrl_YC_OutClip error.',
 'CHROMA_SUPPRESS':'Im_B2Y_Ctrl_Chroma_Suppress error.',
}
MMIOS=(0x20020900,0x20020800,0x20020a00)

def printable(x):return 32<=x<127

def run_start(data,o):
 while o>0 and printable(data[o-1]):o-=1
 return o

def raw_occ(data,val):
 pat=struct.pack('<I',val&0xffffffff);out=[];p=0
 while True:
  q=data.find(pat,p)
  if q<0:break
  out.append(q);p=q+1
 return out

def disasm_arm(data):
 md=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);md.detail=True
 out=[]
 for off in range(0,len(data)-4,4):
  ins=next(md.disasm(data[off:off+4],off,count=1),None)
  if ins is not None:out.append((off,ins))
 return out

def reg_imm(ins):
 try:ops=list(ins.operands)
 except Exception:return None
 if len(ops)>=2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_IMM:
  return ops[0].reg,int(ops[1].imm)&0xffff
 return None

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_movw_mmio_xrefs_v083.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 print(f'V083_SAM7=file={row["file"]}|size=0x{len(data):x}|declared_base={row["image_base"]}|kind={row["kind"]}')
 addrmap={}
 for label,needle in TARGETS.items():
  sub=data.find(needle.encode('ascii'));rs=run_start(data,sub) if sub>=0 else -1
  vals=[]
  if rs>=0:vals.append(('run',rs))
  if sub>=0 and sub!=rs:vals.append(('substring',sub))
  addrmap[label]=vals
  print(f'V083_TARGET={label}|'+('|'.join(f'{k}=0x{v:x}' for k,v in vals) if vals else 'NOT_FOUND'))

 insns=disasm_arm(data)
 print(f'V083_ARM_INSN_COUNT={len(insns)}')
 # MOVW then MOVT to same register within the next six ARM instructions.
 pairhits=[]
 for i,(off,ins) in enumerate(insns):
  if ins.mnemonic!='movw':continue
  ri=reg_imm(ins)
  if ri is None:continue
  reg,lo=ri
  for j in range(i+1,min(i+7,len(insns))):
   off2,ins2=insns[j]
   if off2-off>24:break
   if ins2.mnemonic!='movt':continue
   r2=reg_imm(ins2)
   if r2 is None or r2[0]!=reg:continue
   val=(r2[1]<<16)|lo
   for label,poss in addrmap.items():
    for kind,target in poss:
     if val==target:
      pairhits.append((label,kind,off,off2,val,ins.op_str,ins2.op_str))
   for mm in MMIOS:
    if val==mm:pairhits.append((f'MMIO_{mm:08X}','exact',off,off2,val,ins.op_str,ins2.op_str))
   break
 print('\n=== V083 MOVW/MOVT HITS ===')
 for h in pairhits:
  label,kind,o1,o2,val,a,b=h
  print(f'V083_MOVPAIR={label}|target_kind={kind}|movw=0x{o1:x}|movt=0x{o2:x}|value=0x{val:08x}|movw {a}|movt {b}')
  # Context centered on the pair, useful for function/error-path reconstruction.
  idx=next((k for k,(o,_) in enumerate(insns) if o==o1),None)
  if idx is not None:
   for o,x in insns[max(0,idx-12):min(len(insns),idx+20)]:
    print(f'  V083_CTX=0x{o:x}|{x.mnemonic} {x.op_str}')
 print(f'V083_MOVPAIR_COUNT={len(pairhits)}')

 print('\n=== V083 RAW MMIO LITERALS AND PC-RELATIVE REFS ===')
 md=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);md.detail=True
 for mm in MMIOS:
  occ=raw_occ(data,mm);print(f'V083_MMIO_LITERAL=value=0x{mm:08x}|count={len(occ)}|offs={",".join(hex(x) for x in occ)}')
  for lit in occ:
   lo=max(0,lit-0x5000);hi=min(len(data)-4,lit+0x100)
   for off in range(lo&~3,hi,4):
    ins=next(md.disasm(data[off:off+4],off,count=1),None)
    if ins is None:continue
    try:ops=list(ins.operands)
    except Exception:continue
    for op in ops:
     if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
      tgt=off+8+int(op.mem.disp)
      if tgt==lit:
       print(f'V083_MMIO_XREF=value=0x{mm:08x}|code=0x{off:x}|literal=0x{lit:x}|{ins.mnemonic} {ins.op_str}')

 print('OVERALL_VERDICT=SAM7_MOVW_MOVT_AND_B2Y_MMIO_XREFS_ENUMERATED')
if __name__=='__main__':main()
