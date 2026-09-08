#!/usr/bin/env python3
from __future__ import annotations
import hashlib,struct,sys
from pathlib import Path

PFX=4;HDR=PFX+0x10;STRIDE=0xA90
MAP={
 0x1e:'HF_SCLP',0x1f:'HF_SCLM',0x20:'HF_TONP',0x21:'HF_TONM',
 0x22:'LF_SCLP',0x23:'LF_SCLM',0x24:'LF_TONP',0x25:'LF_TONM',
}
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v119 <B2Y>')
 b=Path(sys.argv[1]).read_bytes();count=u32(b,PFX+8);payload=HDR+count*STRIDE
 blobs={}
 for idx in range(count):
  o=HDR+idx*STRIDE;rid,rel,size=u32(b,o),u32(b,o+4),u32(b,o+8)
  if rid in MAP:
   blob=b[payload+rel:payload+rel+size];blobs[rid]=blob
   n=len(blob)//2;vals=struct.unpack_from('<'+'H'*n,blob,0) if n else ()
   print(f'V119_TABLE=id=0x{rid:02x}|name={MAP[rid]}|index={idx}|size=0x{size:x}|sha256={hashlib.sha256(blob).hexdigest()}|u16len={n}|min={min(vals) if vals else -1}|max={max(vals) if vals else -1}')
   if vals:
    picks=[0,n//8,n//4,n//2,(3*n)//4,n-1]
    print('V119_SAMPLES='+MAP[rid]+'|'+','.join(f'{i}:{vals[i]}' for i in picks))
 for a,c,label in [(0x1e,0x1f,'HF_SCLP_vs_SCLM'),(0x20,0x21,'HF_TONP_vs_TONM'),(0x22,0x23,'LF_SCLP_vs_SCLM'),(0x24,0x25,'LF_TONP_vs_TONM'),(0x1e,0x22,'HF_vs_LF_SCLP'),(0x1f,0x23,'HF_vs_LF_SCLM')]:
  A=blobs.get(a,b'');C=blobs.get(c,b'');eq=A==C
  diffs=[]
  if len(A)==len(C) and len(A)%2==0:
   av=struct.unpack_from('<'+'H'*(len(A)//2),A,0);cv=struct.unpack_from('<'+'H'*(len(C)//2),C,0)
   diffs=[(i,x,y) for i,(x,y) in enumerate(zip(av,cv)) if x!=y]
  print(f'V119_COMPARE={label}|equal={eq}|bytesA={len(A)}|bytesB={len(C)}|u16diffs={len(diffs)}')
  for i,x,y in diffs[:32]:print(f'V119_DIFF={label}|i={i}|A={x}|B={y}|delta={y-x}')
 print('V119_EVIDENCE=caller_failure_strings_map_IDs_as_SCLP_SCLM_TONP_TONM;this_probe_tests_payload_polarity_symmetry')
 print('OVERALL_VERDICT=V119_EDGE_POLARITY_TABLE_MAP_COMPLETE')
if __name__=='__main__':main()
