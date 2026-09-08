#!/usr/bin/env python3
from __future__ import annotations
import csv,re,struct,sys
from pathlib import Path

def amap(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def refs(data,base,val):
 pat=struct.pack('<I',val);out=[];p=0
 while 1:
  q=data.find(pat,p)
  if q<0:return out
  out.append(base+q);p=q+1

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v129 <sections>')
 data,base,fn=amap(Path(sys.argv[1]));print(f'V129_SAM7={fn}|base=0x{base:08x}|size=0x{len(data):x}')
 strings=[]
 for m in re.finditer(rb'[ -~]{5,}',data):
  try:s=m.group().decode('ascii')
  except:continue
  strings.append((base+m.start(),s))
 print('\n######## ALL Im_B2Y STRINGS ########')
 for a,s in strings:
  if 'Im_B2Y' in s:print(f'V129_IMB2Y=0x{a:08x}|{s}')
 print('\n######## YC / YBLEND / MATRIX / CLIP / GAIN CANDIDATES ########')
 keys=('yblend','y_blend','yc','matrix','clip','offset','gain','blend','convert')
 cands=[]
 for a,s in strings:
  sl=s.lower()
  if ('b2y' in sl or 'yc' in sl or 'yblend' in sl) and any(k in sl for k in keys):
   cands.append((a,s));print(f'V129_CAND=0x{a:08x}|{s}')
 print('\n######## EXACT TARGET STRING POINTER REFS ########')
 for a,s in cands:
  if any(k in s.lower() for k in ('yblend','yc','convert')):
   rr=refs(data,base,a)
   if rr:print(f'V129_REF|string=0x{a:08x}|count={len(rr)}|sites='+','.join(f'0x{x:08x}' for x in rr[:80])+'|text='+s[:160])
 print('\n######## NEAR TARGET STRINGS ########')
 targets=[(a,s) for a,s in strings if any(k in s.lower() for k in ('imb2y_ctrl_y','im_b2y_ctrl_y','yblend','yc_conversion','yctorgb','rgbtoyc'))]
 for ta,ts in targets:
  print(f'V129_TARGET=0x{ta:08x}|{ts}')
  for a,s in strings:
   if abs(a-ta)<=0x700:print(f'V129_NEAR=0x{a:08x}|{s[:240]}')
 print('\nV129_GOAL=recover_SAM7_SDK_symbolic_names_or_argument_validation_strings_for_Y_BLEND_and_Yc_Convert_local_fields')
 print('OVERALL_VERDICT=V129_YC_SDK_STRING_CENSUS_COMPLETE')
if __name__=='__main__':main()
