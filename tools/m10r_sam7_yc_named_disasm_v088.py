#!/usr/bin/env python3
"""v0.88: bounded Thumb disassembly of named SAM7 YC hardware controls.

Targets come directly from v0.87 xref-backed function starts. This probe emits
full instruction bodies and nearby literal-pool words/ASCII so register-base
adjustments can be decoded without relying on the simplistic base-register
tracker used in v0.87.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN

FUNCS={
 'YC_GAIN_A':0x4f30e,
 'YC_GAIN_B':0x4f414,
 'YC_GAIN_C':0x4f51a,
 'YCTORG_A':0x4f7c0,
 'YCTORG_B':0x4f8a4,
 'YCTORG_C':0x4fa08,
 'YCC':0x51da6,
}
DIAGS={
 'YC_GAIN':0x4f786,
 'YC_CLIP_A':0x4fb8e,
 'YC_CLIP_B':0x4fbbe,
 'YCTORG':0x4fc02,
}

def disfunc(data,start,maxlen=0x500):
 m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=False;out=[];off=start
 while off<min(len(data),start+maxlen):
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins is None:break
  out.append(ins);off+=ins.size
  if len(out)>4 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):break
 return out

def printable(b):return 32<=b<127

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_yc_named_disasm_v088.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 print(f'V088_SAM7=file={row["file"]}|size=0x{len(data):x}|kind={row["kind"]}')
 for name,start in FUNCS.items():
  insns=disfunc(data,start)
  end=insns[-1].address+insns[-1].size if insns else start
  print(f'\n=== V088_FUNC {name} start=0x{start:x} end=0x{end:x} count={len(insns)} ===')
  for ins in insns:print(f'V088_INS={name}|0x{ins.address:x}|{ins.mnemonic} {ins.op_str}')
  # Print aligned words immediately following function, common literal-pool zone.
  lo=(end+3)&~3;hi=min(len(data),lo+0x100)
  for o in range(lo,hi,4):
   v=struct.unpack_from('<I',data,o)[0]
   if 0x20000000<=v<=0x200fffff or v in (0x00003fff,0x00007fff,0x00008000,0xffff8000):
    print(f'V088_LITERAL_AFTER={name}|off=0x{o:x}|value=0x{v:08x}')

 print('\n=== V088 DIAGNOSTIC NEIGHBORHOODS ===')
 for name,q in DIAGS.items():
  lo=max(0,q-0x100);hi=min(len(data),q+0x80)
  print(f'V088_DIAGCTX={name}|lo=0x{lo:x}|hi=0x{hi:x}|hex={data[lo:hi].hex()}')
  for o in range((lo+3)&~3,hi-3,4):
   v=struct.unpack_from('<I',data,o)[0]
   if 0x20000000<=v<=0x200fffff:print(f'V088_DIAG_MMIO={name}|off=0x{o:x}|value=0x{v:08x}')
 print('OVERALL_VERDICT=NAMED_SAM7_YC_CONTROL_BODIES_AND_LITERAL_POOLS_CAPTURED')
if __name__=='__main__':main()
