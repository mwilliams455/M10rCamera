#!/usr/bin/env python3
from __future__ import annotations
import re,struct,sys,collections
from pathlib import Path

PFX=4; HDR=PFX+0x10; STRIDE=0xA90; RID=0x0f

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def strings(blob):
 out=[]
 for m in re.finditer(rb'[ -~]{8,}',blob):
  try: out.append(m.group().decode('ascii'))
  except: pass
 return out

def main():
 if len(sys.argv)!=2: raise SystemExit('usage: v122 <B2Y calibration>')
 b=Path(sys.argv[1]).read_bytes(); count=u32(b,PFX+8); payload=HDR+count*STRIDE
 rows=[]
 for idx in range(count):
  o=HDR+idx*STRIDE; rid,rel,size=u32(b,o),u32(b,o+4),u32(b,o+8)
  if rid!=RID: continue
  blob=b[payload+rel:payload+rel+size]
  if len(blob)<0x120: continue
  sels=[s for s in strings(b[o:o+STRIDE]) if 'B2YMODE' in s]
  # These are stored as dwords in calibration, but setter consumes low 16 bits.
  f114=u32(blob,0x114)&0xffff
  f118=u32(blob,0x118)&0x3ff
  f11c=u32(blob,0x11c)&0x3ff
  en=u32(blob,0) if len(blob)>=4 else None
  rows.append((idx,size,en,f114,f118,f11c,sels))
  print(f'V122_REC=idx{idx}|size=0x{size:x}|enable={en}|f114={f114}|f118={f118}|f118_q8={f118/256:.6f}|f11c={f11c}|sels={" || ".join(sels[:8])}')
 print(f'V122_COUNT={len(rows)}')
 for pos,name in [(3,'f114'),(4,'f118'),(5,'f11c')]:
  c=collections.Counter(r[pos] for r in rows)
  print('V122_UNIQUE_'+name+'='+','.join(f'{k}:{v}' for k,v in sorted(c.items())))
 # Focused STILL sharpness/ISO matrix.
 print('V122_STILL_MATRIX_BEGIN')
 for sharp in ('LOW','MEDIUM','HIGH'):
  for iso in (100,160,200,400,640,800,1600,4000,12500,40000):
   needle=f'_B2YMODE:STILL_SHARPNESS:{sharp}_ISO:{iso}'
   hit=next((r for r in rows if any(needle in s for s in r[6])),None)
   if hit:
    print(f'V122_STILL={sharp}|ISO={iso}|idx={hit[0]}|enable={hit[2]}|f114={hit[3]}|f118={hit[4]}|q8={hit[4]/256:.6f}|f11c={hit[5]}')
 print('V122_STILL_MATRIX_END')
 # Ratios HIGH/MED at matched ISO when both enabled.
 for iso in (100,160,200,400,640,800,1600,4000,12500,40000):
  def pick(sh):
   n=f'_B2YMODE:STILL_SHARPNESS:{sh}_ISO:{iso}'
   return next((r for r in rows if any(n in s for s in r[6])),None)
  m,h=pick('MEDIUM'),pick('HIGH')
  if m and h and m[4]: print(f'V122_RATIO=ISO{iso}|HIGH_over_MED_f118={h[4]/m[4]:.6f}|MED={m[4]}|HIGH={h[4]}')
 print('V122_INTERPRETATION_GUARD=f118_is_10bit_and_Q8_like_numerically_but_semantic_gain_not_claimed_without_consumer/register_evidence')
 print('OVERALL_VERDICT=V122_HF_SCALAR_SURVEY_COMPLETE')
if __name__=='__main__': main()
