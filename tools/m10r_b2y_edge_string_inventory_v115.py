#!/usr/bin/env python3
from __future__ import annotations
import csv,sys,re
from pathlib import Path

KEYS=('edge','hedge','ledge','coring','gain','scale','step','threshold','sharp','high freq','low freq','highedge','lowedge')
SECTIONS=('IMG-System','IMG-SAM7')

def ascii_runs(b,minlen=4):
 out=[];i=0
 while i<len(b):
  if 32<=b[i]<127:
   j=i
   while j<len(b) and 32<=b[j]<127:j+=1
   if j-i>=minlen: out.append((i,b[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v115 <sections_dir>')
 d=Path(sys.argv[1]);rows=list(csv.DictReader((d/'sections.csv').open()))
 for sec in SECTIONS:
  r=next(x for x in rows if x['name']==sec); b=(d/r['file']).read_bytes(); base=int(r['image_base'],16)
  print(f'\n=== V115_SECTION {sec}|file={r["file"]}|base=0x{base:x}|size=0x{len(b):x} ===')
  runs=ascii_runs(b); hits=[]
  for o,s in runs:
   sl=s.lower()
   if any(k in sl for k in KEYS): hits.append((o,s))
  print(f'V115_HIT_COUNT={sec}|{len(hits)}')
  for o,s in hits:
   print(f'V115_HIT={sec}|va=0x{base+o:08x}|{s}')
   # Nearby real strings often carry field labels belonging to the same debug block.
   near=[(oo,ss) for oo,ss in runs if abs(oo-o)<=0x180 and oo!=o]
   for oo,ss in near[:24]: print(f'V115_NEAR={sec}|anchor=0x{base+o:08x}|va=0x{base+oo:08x}|{ss}')
 print('\nV115_GOAL=find_B2Y_edge_specific_parameter_names_without_relying_on_lens_or_suppression_debug_false_leads')
 print('OVERALL_VERDICT=V115_B2Y_EDGE_STRING_INVENTORY_EXTRACTED')
if __name__=='__main__':main()
