#!/usr/bin/env python3
from __future__ import annotations
import csv,math,struct,sys
from pathlib import Path

# Exact mathematical inverse (Q12 target) of current firmware RGB->YC matrix
# [1224,2404,467;-691,-1357,2048;2048,-1715,-333] / 4096.
REF=[4097,0,5743,4097,-1410,-2924,4097,7258,0]

def s14(v):
 v&=0x3fff
 return v-0x4000 if v&0x2000 else v

def s16(v): return v-0x10000 if v&0x8000 else v

def dist(vals):
 # Compare both direct signed integer blocks and low-14-bit hardware encodings.
 d1=sum((a-b)**2 for a,b in zip(vals,REF))
 h=[s14(x) for x in vals]
 # For coefficients > 8191/2 the hardware can still represent positive magnitudes
 # depending on block semantics; also compare raw 14-bit unsigned against positive ref.
 raw=[x&0x3fff for x in vals]
 d2=sum((a-b)**2 for a,b in zip(h,REF))
 d3=sum((a-(b&0x3fff))**2 for a,b in zip(raw,REF))
 return min(d1,d2,d3),h,raw

def scan_u16(data,label,top=40):
 hits=[]
 for o in range(0,len(data)-18,2):
  vals=list(struct.unpack_from('<9H',data,o))
  score,h,raw=dist(vals)
  hits.append((score,o,vals,h,raw))
 hits.sort(key=lambda x:x[0])
 print(f'\n=== V103_U16_TOP {label} ===')
 for rank,(sc,o,v,h,r) in enumerate(hits[:top]):
  print(f'V103_HIT=rank={rank}|off=0x{o:x}|score={sc}|u16={v}|s14={h}|raw14={r}')

def scan_u32(data,label,top=40):
 hits=[]
 for o in range(0,len(data)-36,4):
  u=list(struct.unpack_from('<9I',data,o));v=[x-0x100000000 if x&0x80000000 else x for x in u]
  sc=sum((a-b)**2 for a,b in zip(v,REF))
  hits.append((sc,o,v,u))
 hits.sort(key=lambda x:x[0])
 print(f'\n=== V103_U32_TOP {label} ===')
 for rank,(sc,o,v,u) in enumerate(hits[:top]):
  print(f'V103_HIT32=rank={rank}|off=0x{o:x}|score={sc}|s32={v}|u32={u}')

def exact_sequences(data,label):
 candidates=[]
 # Common BT.601-ish inverse constants; search each coefficient as u16/raw14.
 for n in (4096,4097,5743,5744,7258,7259,1410,1411,2924,2925):
  pat=struct.pack('<H',n&0xffff)
  offs=[];i=0
  while True:
   i=data.find(pat,i)
   if i<0:break
   offs.append(i);i+=1
  print(f'V103_CONST={label}|value={n}|count={len(offs)}|first={",".join(hex(x) for x in offs[:20])}')

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_yctorgb_matrixhunt_v103.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()))
 print('V103_REF_Q12='+','.join(str(x) for x in REF))
 for name in ('IMG-SAM7','IMG-System'):
  row=next(r for r in rows if r['name']==name);data=(root/row['file']).read_bytes()
  print(f'\nV103_SECTION={name}|file={row["file"]}|size=0x{len(data):x}')
  scan_u16(data,name,30);exact_sequences(data,name)
 # Calibration B2Y section if present.
 b=next((r for r in rows if 'data_calib_B2Y' in r['name']),None)
 if b:
  data=(root/b['file']).read_bytes();print(f'\nV103_SECTION=B2Y|file={b["file"]}|size=0x{len(data):x}')
  scan_u16(data,'B2Y',30);scan_u32(data,'B2Y',30);exact_sequences(data,'B2Y')
 print('OVERALL_VERDICT=V103_YCTORGB_MATRIX_CANDIDATES_RANKED_AGAINST_EXACT_INPUT_MATRIX_INVERSE')
if __name__=='__main__':main()
