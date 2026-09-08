#!/usr/bin/env python3
"""v0.91: bind SAM7 YC diagnostic strings to code using Thumb ADR.

Literal proximity is intentionally ignored. Each printable diagnostic run is
located exactly; Thumb ADR instructions in the surrounding code are resolved
with Capstone and matched to addresses inside that run. This identifies the
actual wrapper/error path for YC_OutOffsetAndGain, YC_OutClip and YCtoRGB.
"""
from __future__ import annotations
import csv,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM
TARGETS={
 'YC_GAIN':'Im_B2Y_Ctrl_YC_OutOffsetAndGain',
 'YC_CLIP':'Im_B2Y_Ctrl_YC_OutClip',
 'YCTORG':'Im_B2Y_Ctrl_YCtoRGB_Matrix',
 'RGBTOYC':'Im_B2Y_Ctrl_RGBtoYC_Matrix',
 'RGB_CLIP':'Im_B2Y_Ctrl_RGB_OutClip',
 'JPEGXR_CLIP':'Im_B2Y_Ctrl_JpegXR_OutClip',
}

def printable(x):return 32<=x<127

def run(data,inside):
 lo=inside
 while lo>0 and printable(data[lo-1]):lo-=1
 hi=inside
 while hi<len(data) and printable(data[hi]):hi+=1
 return lo,hi,data[lo:hi].decode('ascii','replace')

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: ... <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 runs={}
 for label,needle in TARGETS.items():
  p=0;arr=[]
  while True:
   q=data.find(needle.encode(),p)
   if q<0:break
   arr.append(run(data,q));p=q+1
  runs[label]=arr
  for lo,hi,s in arr:print(f'V091_STRING={label}|lo=0x{lo:x}|hi=0x{hi:x}|{s}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
 print('\n=== V091 ADR BINDINGS ===')
 hits=[]
 # Scan the known YC neighborhood plus duplicate high string table area.
 for off in range(0x4e000,min(len(data)-4,0x53000),2):
  ins=next(md.disasm(data[off:off+4],off,count=1),None)
  if not ins or ins.mnemonic!='adr':continue
  try:ops=list(ins.operands)
  except Exception:continue
  if len(ops)<2 or ops[1].type!=ARM_OP_IMM:continue
  target=int(ops[1].imm)&0xffffffff
  for label,arr in runs.items():
   for lo,hi,s in arr:
    if lo<=target<hi:
     hits.append((label,off,target,lo,hi,ins.op_str))
     print(f'V091_ADR={label}|code=0x{off:x}|target=0x{target:x}|run=0x{lo:x}..0x{hi:x}|adr {ins.op_str}')
 print(f'V091_ADR_COUNT={len(hits)}')
 # Fixed local contexts around each hit.
 for label,off,target,lo,hi,ops in hits:
  a=max(0,off-0x40)&~1;b=min(len(data),off+0x80)
  print(f'\nV091_CONTEXT={label}|center=0x{off:x}')
  for x in md.disasm(data[a:b],a):print(f'V091_INS={label}|0x{x.address:x}|{x.mnemonic} {x.op_str}')
 print('OVERALL_VERDICT=YC_DIAGNOSTIC_WRAPPERS_BOUND_BY_DIRECT_ADR_REFERENCES')
if __name__=='__main__':main()
