#!/usr/bin/env python3
"""v0.82: characterize IMG-SAM7 internal layout and repeated data banks.

v0.81 showed no code xrefs to the B2Y diagnostic strings and proved three
0x13400-spaced neighborhoods are byte-identical.  This probe recovers the
maximal identical span, inventories common executable/container signatures,
and reports coarse code/data statistics without assigning semantics.
"""
from __future__ import annotations
import collections,csv,hashlib,math,struct,sys
from pathlib import Path

ANCHORS=(0xc9c84,0xdd084,0xf0484)
SHIFT=0x13400
SIGS={
 'ELF':b'\x7fELF','MZ':b'MZ','PKZIP':b'PK\x03\x04','GZIP':b'\x1f\x8b\x08',
 'XZ':b'\xfd7zXZ\x00','LZMA_ALONE':b'\x5d\x00\x00','UBOOT':b'\x27\x05\x19\x56',
 'ANDROID_BOOT':b'ANDROID!','SQUASHFS_LE':b'hsqs','SQUASHFS_BE':b'sqsh'
}

def entropy(b:bytes)->float:
 if not b:return 0.0
 c=collections.Counter(b);n=len(b)
 return -sum((v/n)*math.log2(v/n) for v in c.values())

def ascii_frac(b):return sum(32<=x<127 or x in (9,10,13) for x in b)/len(b) if b else 0

def maximal_equal(data:bytes,a0:int,a1:int,a2:int):
 left=0
 while min(a0,a1,a2)-left-1>=0 and data[a0-left-1]==data[a1-left-1]==data[a2-left-1]:left+=1
 right=0
 while max(a0,a1,a2)+right<len(data) and data[a0+right]==data[a1+right]==data[a2+right]:right+=1
 return left,right

def strings(data:bytes,minlen=12):
 out=[];i=0
 while i<len(data):
  if 32<=data[i]<127:
   j=i
   while j<len(data) and 32<=data[j]<127:j+=1
   if j-i>=minlen:out.append((i,data[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_layout_v082.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');p=root/row['file'];data=p.read_bytes()
 print(f'V082_SAM7=file={p.name}|size=0x{len(data):x}|sha256={hashlib.sha256(data).hexdigest()}|declared_base={row["image_base"]}|kind={row["kind"]}|aux={row["aux"]}')
 print('V082_HEAD256='+data[:0x100].hex())
 print('V082_HEAD_U32='+','.join(f'0x{struct.unpack_from("<I",data,o)[0]:08x}' for o in range(0,min(0x80,len(data)-3),4)))
 for name,sig in SIGS.items():
  offs=[];pos=0
  while True:
   q=data.find(sig,pos)
   if q<0:break
   offs.append(q);pos=q+1
  if offs:print(f'V082_SIGNATURE={name}|count={len(offs)}|offs={",".join(hex(x) for x in offs[:32])}')
 # Common ARM vector-table fingerprint: branch opcodes in first words.
 for off in range(0,min(len(data),0x4000),4):
  w=struct.unpack_from('<I',data,off)[0]
  if (w&0xff000000)==0xea000000:
   print(f'V082_EARLY_ARM_BRANCH=off=0x{off:x}|word=0x{w:08x}')

 left,right=maximal_equal(data,*ANCHORS)
 starts=[a-left for a in ANCHORS];ends=[a+right for a in ANCHORS]
 print(f'V082_EQUAL3=anchor0=0x{ANCHORS[0]:x}|shift=0x{SHIFT:x}|left=0x{left:x}|right=0x{right:x}|length=0x{left+right:x}|starts={",".join(hex(x) for x in starts)}|ends={",".join(hex(x) for x in ends)}')
 for i,(s,e) in enumerate(zip(starts,ends)):
  blob=data[s:e]
  print(f'V082_EQUAL_REGION={i}|start=0x{s:x}|end=0x{e:x}|size=0x{len(blob):x}|sha256={hashlib.sha256(blob).hexdigest()}')
  lo=max(0,s-0x40);hi=min(len(data),s+0x80)
  print(f'V082_REGION_HEADCTX={i}|lo=0x{lo:x}|hex={data[lo:hi].hex()}')

 # Coarse 64 KiB statistics reveal compressed/data/code/string zones.
 print('\n=== V082 COARSE MAP 0x10000 ===')
 step=0x10000
 for s in range(0,len(data),step):
  b=data[s:min(len(data),s+step)]
  print(f'V082_ZONE=start=0x{s:x}|size=0x{len(b):x}|entropy={entropy(b):.4f}|ascii_frac={ascii_frac(b):.4f}|zero_frac={b.count(0)/len(b):.4f}|sha16={hashlib.sha256(b).hexdigest()[:16]}')

 # Inventory target control strings and nearby B2Y symbol cluster globally.
 ss=strings(data)
 b2y=[(o,s) for o,s in ss if 'B2Y' in s or 'b2y' in s]
 print(f'V082_B2Y_STRING_COUNT={len(b2y)}')
 for o,s in b2y[:240]:print(f'V082_B2Y_STRING=0x{o:x}|{s}')
 print('OVERALL_VERDICT=SAM7_INTERNAL_LAYOUT_AND_REPEATED_BANKS_CHARACTERIZED')
if __name__=='__main__':main()
