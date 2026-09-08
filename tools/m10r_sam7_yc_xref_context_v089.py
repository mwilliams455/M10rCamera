#!/usr/bin/env python3
"""v0.89: exact Thumb contexts around v0.87 YC page xrefs and clip cluster.

Avoids prologue inference: disassemble fixed windows around each proven
PC-relative MMIO literal xref plus the contiguous YC_CLIP/YCTORG diagnostic
cluster. This is intended for manual register/field reconstruction.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN

XREFS={
 'YC_GAIN_34C':0x4f34c,'YC_GAIN_3B4':0x4f3b4,'YC_GAIN_452':0x4f452,
 'YC_GAIN_4BA':0x4f4ba,'YC_GAIN_550':0x4f550,
 'YCTORG_800':0x4f800,'YCTORG_856':0x4f856,'YCTORG_8E4':0x4f8e4,'YCTORG_A12':0x4fa12,
}
RANGES={
 'YC_GAIN_CLUSTER':(0x4f2f0,0x4f780),
 'YCTORG_CLIP_CLUSTER':(0x4f7a0,0x4fc40),
}

def md():return Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
def disrange(data,lo,hi):
 m=md();return list(m.disasm(data[lo:hi],lo))
def ascii_runs(data,lo,hi,minlen=8):
 out=[];i=lo
 while i<hi:
  if 32<=data[i]<127:
   j=i
   while j<hi and 32<=data[j]<127:j+=1
   if j-i>=minlen:out.append((i,data[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_yc_xref_context_v089.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 print(f'V089_SAM7=file={row["file"]}|size=0x{len(data):x}')
 for name,c in XREFS.items():
  lo=max(0,c-0x50)&~1;hi=min(len(data),c+0xb0)
  print(f'\n=== V089_XREF {name} center=0x{c:x} lo=0x{lo:x} hi=0x{hi:x} ===')
  for ins in disrange(data,lo,hi):
   mark='|XREF' if ins.address==c else ''
   print(f'V089_INS={name}|0x{ins.address:x}|{ins.mnemonic} {ins.op_str}{mark}')
  for o in range((lo+3)&~3,hi-3,4):
   v=struct.unpack_from('<I',data,o)[0]
   if 0x20000000<=v<=0x200fffff:print(f'V089_MMIO_WORD={name}|off=0x{o:x}|value=0x{v:08x}')
 for name,(lo,hi) in RANGES.items():
  print(f'\n=== V089_RANGE {name} lo=0x{lo:x} hi=0x{hi:x} ===')
  for off,s in ascii_runs(data,lo,hi):print(f'V089_ASCII={name}|0x{off:x}|{s}')
  for o in range((lo+3)&~3,hi-3,4):
   v=struct.unpack_from('<I',data,o)[0]
   if 0x20000000<=v<=0x200fffff:print(f'V089_RANGE_MMIO={name}|off=0x{o:x}|value=0x{v:08x}')
 print('OVERALL_VERDICT=EXACT_YC_XREF_AND_CLIP_CLUSTER_CONTEXT_CAPTURED')
if __name__=='__main__':main()
