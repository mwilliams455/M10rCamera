#!/usr/bin/env python3
from __future__ import annotations
import csv,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN

SITES={
 'EDGE_GAIN':0x000afd7a,
 'EXTRACTED_CORING':0x0010fcf8,
 'EXTRACTED_CORING_ZERO':0x0011133c,
}
STRINGS={
 'EDGE_GAIN_STR':0x000afeb0,
 'CORING_STR':0x0010ffb8,
 'CORING_ZERO_STR':0x00111608,
}

def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def ascii_runs(b,a,z,minlen=3):
 out=[];i=max(0,a)
 while i<min(len(b),z):
  if 32<=b[i]<127:
   j=i
   while j<min(len(b),z) and 32<=b[j]<127:j+=1
   if j-i>=minlen:out.append((i,b[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v114 <sections>')
 d=Path(sys.argv[1]);b,base,fn=load(d)
 print(f'V114_IMG={fn}|base=0x{base:x}|size=0x{len(b):x}')
 print('\n=== V114_STRING_NEIGHBORHOODS ===')
 for label,va in STRINGS.items():
  off=va-base
  print(f'V114_STRING_CENTER={label}|0x{va:08x}')
  for o,s in ascii_runs(b,off-0x300,off+0x380):
   print(f'V114_ASCII={label}|0x{base+o:08x}|{s}')

 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=False;md.skipdata=True
 print('\n=== V114_NEAREST_PROLOGUES ===')
 for label,site in SITES.items():
  a=max(base,site-0x1800); off=a-base
  candidates=[]
  for ins in md.disasm(b[off:site-a],a):
   if ins.mnemonic=='push' and 'lr' in ins.op_str:
    candidates.append(ins.address)
  print(f'V114_SITE={label}|0x{site:08x}|push_candidates='+','.join(f'0x{x:08x}' for x in candidates[-12:]))
  if not candidates:continue
  start=candidates[-1]
  # The closest push can be an inner/non-returning block if decoding crossed data.
  # Emit the last three candidates separately so caller can identify the real function.
  for rank,st in enumerate(candidates[-3:],1):
   print(f'\n--- V114_FUNC_CANDIDATE {label} rank={rank} start=0x{st:08x} ---')
   oo=st-base; end=min(base+len(b),site+0x80)
   for ins in md.disasm(b[oo:oo+(end-st)],st):
    mark='|SITE=1' if ins.address==site else ''
    print(f'V114_INS={label}|cand={rank}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}{mark}')

 print('\nV114_FOCUS=trace_r5_working_struct_origin_and_names_around_offset_0x62_coring')
 print('OVERALL_VERDICT=V114_EDGE_DEBUG_STRUCT_CONTEXT_EXTRACTED')
if __name__=='__main__':main()
