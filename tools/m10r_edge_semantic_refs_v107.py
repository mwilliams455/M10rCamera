#!/usr/bin/env python3
from __future__ import annotations
import csv,re,struct,sys
from pathlib import Path

PFX=4; HDR=PFX+0x10; STRIDE=0xA90

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def s32s(b): return list(struct.unpack_from('<'+'i'*(len(b)//4),b,0))

def ascii_runs(b,minlen=5):
 out=[];i=0
 while i<len(b):
  if 32<=b[i]<127:
   j=i
   while j<len(b) and 32<=b[j]<127:j+=1
   if j-i>=minlen:out.append((i,b[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def recs(data):
 n=u32(data,PFX+8); pbase=HDR+n*STRIDE; out=[]
 for i in range(n):
  h=HDR+i*STRIDE; rid,rel,size=u32(data,h),u32(data,h+4),u32(data,h+8)
  out.append((i,rid,data[h:h+STRIDE],data[pbase+rel:pbase+rel+size]))
 return out

def selectors(h):return [s for _,s in ascii_runs(h) if '_B2YMODE:' in s]

def section_map(d):
 rows=list(csv.DictReader((d/'sections.csv').open()))
 return {r['name']:(d/r['file'],int(r['image_base'],16),r['file']) for r in rows}

def main():
 if len(sys.argv)!=3:raise SystemExit('usage: m10r_edge_semantic_refs_v107.py <sections_dir> <b2y>')
 d=Path(sys.argv[1]); b=Path(sys.argv[2]).read_bytes(); rr=recs(b)
 print(f'V107_B2Y=0x{len(b):x}|records={len(rr)}')

 print('\n=== V107_EXACT_STILL_MEDIUM_CONTROL_RECORDS ===')
 for rid,name in ((0x0f,'HF'),(0x10,'LF')):
  hit=None
  for idx,r,h,p in rr:
   if r!=rid: continue
   ss=selectors(h)
   if any(s=='_B2YMODE:STILL_SHARPNESS:MEDIUM_ISO:100' for s in ss):
    hit=(idx,ss,p);break
  if not hit:
   print(f'V107_{name}_NOT_FOUND=1');continue
  idx,ss,p=hit
  vals=s32s(p)
  print(f'V107_{name}=idx={idx}|bytes=0x{len(p):x}|selectors={ss}')
  print(f'V107_{name}_S32='+','.join(f'{i}:{v}' for i,v in enumerate(vals)))

 print('\n=== V107_HF_LF_RECORD_DIFF ===')
 def get(rid):
  for idx,r,h,p in rr:
   if r==rid and any(s=='_B2YMODE:STILL_SHARPNESS:MEDIUM_ISO:100' for s in selectors(h)):return s32s(p)
  return []
 hf,lf=get(0x0f),get(0x10)
 m=min(len(hf),len(lf))
 for i in range(m):
  if hf[i]!=lf[i]:print(f'V107_DIFF=dword{i}|hf={hf[i]}|lf={lf[i]}')
 print(f'V107_LENGTHS=hf={len(hf)}|lf={len(lf)}')

 # Search code-bearing/system sections first, avoiding calibration selector noise.
 print('\n=== V107_SYSTEM_EDGE_TERMINOLOGY ===')
 sm=section_map(d)
 terms=('B2Y','EDGE','Edge','edge','HighFreq','LowFreq','Coring','coring','Synthesis','SYNTH','Sharp','SHARP','Detail','DETAIL','Limit','LIMIT')
 emitted=0
 priority=['IMG-System','IMG-SAM7','IMG-MAIN','IMG-CA9']
 seen=set()
 for name in priority+list(sm):
  if name in seen or name not in sm:continue
  seen.add(name);path,base,fn=sm[name]
  try:data=path.read_bytes()
  except:continue
  for off,s in ascii_runs(data,5):
   if any(t in s for t in terms):
    # discard calibration-style mode-selector floods
    if '_B2YMODE:' in s:continue
    print(f'V107_TERM=section={name}|file={fn}|va=0x{base+off:08x}|{s[:300]}')
    emitted+=1
    if emitted>=800:break
  if emitted>=800:break
 print(f'V107_TERM_COUNT={emitted}')

 # Numeric xrefs to the four LUT SRAM bases in IMG-System can reveal consumers,
 # not merely their configuration writer. A true image-Y consumer may expose
 # adjacent registers or lookup ordering that differs from the loader.
 print('\n=== V107_LUT_BASE_XREFS ===')
 if 'IMG-System' in sm:
  path,base,fn=sm['IMG-System']; data=path.read_bytes()
  addrs=[0x20A80000,0x20A88000,0x20A90000,0x20A94000,0x20AA0000,0x20AA8000,0x20AB0000,0x20AB4000]
  for a in addrs:
   nd=struct.pack('<I',a);pos=[];st=0
   while True:
    q=data.find(nd,st)
    if q<0:break
    pos.append(base+q);st=q+1
   print(f'V107_XREF=addr=0x{a:08x}|count={len(pos)}|sites='+','.join(f'0x{x:08x}' for x in pos[:80]))

 # Search for exact 14-bit and 10-bit masks near system code. This is only a
 # correlation map, not semantic proof, but helps identify consumers surrounding
 # the edge MMIO blocks and LUT SRAM banks.
 print('\n=== V107_MASK_LITERAL_XREFS ===')
 if 'IMG-System' in sm:
  path,base,fn=sm['IMG-System']; data=path.read_bytes()
  for val,label in ((0x3fff,'14BIT'),(0x03ff,'10BIT'),(0x1fff,'13BIT'),(0x20020a00,'HF_MMIO'),(0x20020c00,'LF_MMIO'),(0x20020e00,'SYNTH_MMIO')):
   nd=struct.pack('<I',val); pos=[]; st=0
   while True:
    q=data.find(nd,st)
    if q<0:break
    pos.append(base+q);st=q+1
   print(f'V107_LITERAL={label}|0x{val:08x}|count={len(pos)}|sites='+','.join(f'0x{x:08x}' for x in pos[:100]))

 print('\n=== V107_VERDICT ===')
 print('V107_CAUTION=14bit_LUT_address_space_plus_10bit_values_is_strong_structure_but_not_yet_proof_of_luma_coordinate_or_Q10_gain')
 print('V107_RENDER_RULE=Do_not_replace_EDGE1A_arithmetic_or_add_LF_until_coordinate_and_combination_semantics_are_constrained_or_explicitly_bounded_as_a_separate_AB_candidate')
 print('OVERALL_VERDICT=V107_EDGE_SEMANTIC_REFERENCE_EVIDENCE_EXTRACTED')
if __name__=='__main__':main()
