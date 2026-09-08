#!/usr/bin/env python3
from __future__ import annotations
import re,struct,sys
from pathlib import Path

PFX=4;HDR=PFX+0x10;STRIDE=0xA90
TARGETS={0x0f:'HF',0x10:'LF'}
ISOS=(100,200,800,1600,4000,12500,40000)
SHARPS=('LOW','MEDIUM','HIGH')

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def s32(v):return v-0x100000000 if v&0x80000000 else v

def strings(blob):
 out=[]
 for m in re.finditer(rb'[ -~]{8,}',blob):
  try:out.append(m.group().decode('ascii'))
  except:pass
 return out

def parse(data):
 count=u32(data,PFX+8);payload=HDR+count*STRIDE; recs=[]
 for idx in range(count):
  o=HDR+idx*STRIDE;rid,rel,size=u32(data,o),u32(data,o+4),u32(data,o+8)
  if rid not in TARGETS:continue
  hdr=data[o:o+STRIDE];blob=data[payload+rel:payload+rel+size]
  sels=[s for s in strings(hdr) if '_B2YMODE:STILL_SHARPNESS:' in s]
  recs.append({'idx':idx,'rid':rid,'size':size,'blob':blob,'sels':sels})
 return recs

def choose(recs,rid,sharp,iso):
 needle=f'_B2YMODE:STILL_SHARPNESS:{sharp}_ISO:{iso}'
 hits=[r for r in recs if r['rid']==rid and any(needle in s for s in r['sels'])]
 return hits[0] if hits else None

def dwords(r):
 n=len(r['blob'])//4
 return list(struct.unpack_from('<'+'I'*n,r['blob'],0))

def emit_diff(label,a,b):
 A=dwords(a);B=dwords(b);n=min(len(A),len(B))
 print(f'\n=== V117_DIFF {label}|Aidx={a["idx"]}|Bidx={b["idx"]} ===')
 same=0;diff=0
 for i in range(n):
  if A[i]==B[i]:same+=1;continue
  diff+=1
  print(f'V117_D={label}|i={i}|off=0x{i*4:03x}|A_u={A[i]}|A_s={s32(A[i])}|B_u={B[i]}|B_s={s32(B[i])}|delta_s={s32(B[i])-s32(A[i])}')
 print(f'V117_DIFF_SUMMARY={label}|same={same}|diff={diff}|lenA={len(A)}|lenB={len(B)}')

def emit_groups(side,r):
 V=dwords(r)
 print(f'\n=== V117_GROUPS side={side}|idx={r["idx"]}|size=0x{r["size"]:x} ===')
 # Known setter-mapped windows around kernel and paired shaping groups.
 for a,z,name in [(0,16,'HEADER_KERNEL_PRE'),(16,40,'SHAPE_A'),(40,70,'SHAPE_B'),(70,min(len(V),106),'TAIL')]:
  vals=V[a:z]
  print(f'V117_GROUP={side}|{name}|i={a}..{z-1}|'+','.join(f'{i}:{s32(V[i])}' for i in range(a,z)))

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v117 <B2Y>')
 data=Path(sys.argv[1]).read_bytes();recs=parse(data)
 print(f'V117_RECS={len(recs)}')
 for rid,side in TARGETS.items():
  print(f'\n######## V117_SIDE {side} ########')
  # Sharpness-mode differences at matched ISO.
  for iso in ISOS:
   picks={s:choose(recs,rid,s,iso) for s in SHARPS}
   print('V117_PICK='+side+f'|iso={iso}|'+','.join(f'{s}={picks[s]["idx"] if picks[s] else "NA"}' for s in SHARPS))
   if picks['LOW'] and picks['MEDIUM']:emit_diff(f'{side}_ISO{iso}_LOW_TO_MED',picks['LOW'],picks['MEDIUM'])
   if picks['MEDIUM'] and picks['HIGH']:emit_diff(f'{side}_ISO{iso}_MED_TO_HIGH',picks['MEDIUM'],picks['HIGH'])
  # ISO evolution within MEDIUM.
  prev=None;previso=None
  for iso in ISOS:
   r=choose(recs,rid,'MEDIUM',iso)
   if r and (prev is None or r['idx']!=prev['idx']):
    emit_groups(side,r)
    if prev:emit_diff(f'{side}_MEDIUM_ISO{previso}_TO_{iso}',prev,r)
    prev=r;previso=iso
 print('\nV117_GOAL=separate_enable_kernel_scale_tone_threshold_fields_by_sharpness_and_ISO_variation')
 print('OVERALL_VERDICT=V117_EDGE_RECORD_DIFFERENTIAL_COMPLETE')
if __name__=='__main__':main()
