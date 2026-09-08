#!/usr/bin/env python3
from __future__ import annotations
import string,struct,sys
from pathlib import Path

SECTION_PREFIX=4; HDR=SECTION_PREFIX+0x10; STRIDE=0xA90
IDS={0x11:'EDGE_SYNTHESIS',0x0F:'HIGH_FREQ_EDGE',0x10:'LOW_FREQ_EDGE',0x12:'TEXTURE_ENHANCEMENT'}

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def ascii_runs(b,minlen=3):
 out=[];i=0
 while i<len(b):
  if 32<=b[i]<127:
   j=i
   while j<len(b) and 32<=b[j]<127:j+=1
   if j-i>=minlen:out.append((i,b[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_edge_record_metadata_v104.py <b2y_section>')
 data=Path(sys.argv[1]).read_bytes();count=u32(data,SECTION_PREFIX+8);payload_base=HDR+count*STRIDE
 print(f'V104_SIZE=0x{len(data):x}|count={count}|payload_base=0x{payload_base:x}')
 for idx in range(count):
  o=HDR+idx*STRIDE;rid=u32(data,o);rel=u32(data,o+4);size=u32(data,o+8)
  if rid not in IDS:continue
  header=data[o:o+STRIDE]
  print(f'\n=== V104_REC index={idx}|id=0x{rid:02x}|name={IDS[rid]}|rel=0x{rel:x}|size=0x{size:x} ===')
  # First 64 dwords often expose selector/control fields even when strings are sparse.
  vals=list(struct.unpack_from('<64I',header,0))
  print('V104_HEAD_U32='+','.join(str(x) for x in vals))
  runs=ascii_runs(header)
  print(f'V104_ASCII_COUNT={len(runs)}')
  for ro,s in runs:
   print(f'V104_ASCII=off=0x{ro:x}|{s}')
 print('\nOVERALL_VERDICT=V104_EDGE_PARAMETER_SET_RECORD_HEADERS_EXTRACTED')
if __name__=='__main__':main()
