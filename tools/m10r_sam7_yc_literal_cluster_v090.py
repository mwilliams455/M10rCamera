#!/usr/bin/env python3
"""v0.90: exact literal-pool map for SAM7 YC output/YCtoRGB cluster.

Scans only 0x4f700..0x4fc80. Every 0x200xxxxx word is reported with Thumb
PC-relative refs and the nearest printable runs. This avoids v0.87's broad
name association and keeps literal ownership local/auditable.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
LO=0x4f700;HI=0x4fc80

def strings(data,lo,hi,minlen=6):
 out=[];i=lo
 while i<hi:
  if 32<=data[i]<127:
   j=i
   while j<hi and 32<=data[j]<127:j+=1
   if j-i>=minlen:out.append((i,j,data[i:j].decode('ascii','replace')))
   i=j
  else:i+=1
 return out

def refs(data,lit):
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;out=[]
 lo=max(0,lit-0x1000)&~1;hi=min(len(data)-4,lit+0x100)
 for off in range(lo,hi,2):
  ins=next(md.disasm(data[off:off+4],off,count=1),None)
  if not ins:continue
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC and ((off+4)&~3)+int(op.mem.disp)==lit:
    out.append((off,ins.mnemonic,ins.op_str));break
 return out

def ctx(data,center):
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);lo=max(0,center-0x30)&~1;hi=min(len(data),center+0x70)
 return list(md.disasm(data[lo:hi],lo))

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: ... <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes();ss=strings(data,LO,HI)
 print(f'V090_RANGE=0x{LO:x}..0x{HI:x}')
 for a,b,s in ss:print(f'V090_ASCII=start=0x{a:x}|end=0x{b:x}|{s}')
 print('\n=== V090 MMIO LITERALS ===')
 for o in range(LO&~1,HI-3,2):
  v=struct.unpack_from('<I',data,o)[0]
  if not (0x20000000<=v<=0x200fffff):continue
  rr=refs(data,o)
  prev=max((x for x in ss if x[1]<=o),default=None,key=lambda x:x[1])
  nxt=min((x for x in ss if x[0]>=o+4),default=None,key=lambda x:x[0])
  print(f'V090_LITERAL=off=0x{o:x}|value=0x{v:08x}|refs={len(rr)}|prev={prev[2] if prev else ""}|prev_dist={o-prev[1] if prev else -1}|next={nxt[2] if nxt else ""}|next_dist={nxt[0]-(o+4) if nxt else -1}')
  for code,mn,ops in rr:
   print(f'  V090_XREF=lit=0x{o:x}|page=0x{v:08x}|code=0x{code:x}|{mn} {ops}')
   for ins in ctx(data,code):print(f'    V090_CTX=0x{ins.address:x}|{ins.mnemonic} {ins.op_str}')
 print('OVERALL_VERDICT=LOCAL_YC_LITERAL_OWNERSHIP_REBUILT_WITHOUT_BROAD_ASSOCIATION')
if __name__=='__main__':main()
