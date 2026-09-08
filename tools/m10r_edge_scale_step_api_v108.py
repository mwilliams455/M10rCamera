#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN

TARGET_STRINGS=[
 ('HIGH_SCALE','Im_B2Y_Set_HighEdge_Scale_Table error. write_ofs_num + array_num > MAX'),
 ('LOW_SCALE','Im_B2Y_Set_LowEdge_Scale_Table error. write_ofs_num + array_num > MAX'),
 ('HIGH_STEP','Im_B2Y_Set_HighEdge_Step_Table error. write_ofs_num + array_num > MAX'),
 ('LOW_STEP','Im_B2Y_Set_LowEdge_Step_Table error. write_ofs_num + array_num > MAX'),
 ('HIGH_CTRL','Im_B2Y_Ctrl_HighEdge error. b2y_ctrl_hedge = NULL'),
 ('LOW_CTRL','Im_B2Y_Ctrl_LowEdge error. b2y_ctrl_ledge = NULL'),
 ('BLEND_CTRL','Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL'),
]
BANKS=[0x20A80000,0x20A88000,0x20A90000,0x20A94000,0x20AA0000,0x20AA8000,0x20AB0000,0x20AB4000]

def amap(d):
 rows=list(csv.DictReader((d/'sections.csv').open()))
 r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def refs(data,base,val):
 n=struct.pack('<I',val);out=[];p=0
 while True:
  q=data.find(n,p)
  if q<0:break
  out.append(base+q);p=q+1
 return out

def findstr(data,base,s):
 p=data.find(s.encode())
 return None if p<0 else base+p

def dump_thumb(data,base,site,label,pre=0x140,post=0x80):
 # Literal refs sit in pools; look backwards for plausible Thumb function bodies.
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
 start=max(base,(site-pre)&~1); off=start-base
 ins=list(md.disasm(data[off:off+pre+post],start))
 print(f'V108_CONTEXT={label}|ref=0x{site:08x}|start=0x{start:08x}')
 for x in ins:
  if site-pre <= x.address <= site+post:
   print(f'V108_INS=0x{x.address:08x}|{x.mnemonic} {x.op_str}')

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_edge_scale_step_api_v108.py <sections_dir>')
 d=Path(sys.argv[1]);data,base,fn=amap(d)
 print(f'V108_SAM7={fn}|base=0x{base:08x}|size=0x{len(data):x}')
 print('\n=== V108_API_STRING_XREFS ===')
 allrefs=[]
 for label,s in TARGET_STRINGS:
  va=findstr(data,base,s)
  print(f'V108_STRING={label}|va={"NONE" if va is None else f"0x{va:08x}"}|{s}')
  if va is None:continue
  rr=refs(data,base,va)
  print(f'V108_STRREF={label}|count={len(rr)}|sites='+','.join(f'0x{x:08x}' for x in rr))
  for x in rr[:8]:allrefs.append((x,label))
 print('\n=== V108_API_REF_CONTEXTS ===')
 for x,label in allrefs:dump_thumb(data,base,x,label)

 print('\n=== V108_BANK_XREFS ===')
 for a in BANKS:
  rr=refs(data,base,a)
  print(f'V108_BANK=0x{a:08x}|count={len(rr)}|sites='+','.join(f'0x{x:08x}' for x in rr[:100]))
  for x in rr[:4]:dump_thumb(data,base,x,f'BANK_{a:08x}',0x100,0x60)

 print('\n=== V108_SIZE_CONSTANT_XREFS ===')
 for v,label in ((0x4000,'16384'),(0x2000,'8192'),(0x3fff,'14BIT_MAX'),(0x1fff,'13BIT_MAX'),(0x3ff,'10BIT_MAX'),(0x400,'1024')):
  rr=refs(data,base,v)
  print(f'V108_CONST={label}|0x{v:x}|count={len(rr)}|sites='+','.join(f'0x{x:08x}' for x in rr[:100]))

 # Dump ASCII strings physically near API error messages. SDK builds often keep
 # related argument-validation strings together; names can expose dimensions or
 # field semantics not recoverable from packed MMIO writes alone.
 print('\n=== V108_NEARBY_API_STRINGS ===')
 for label,s in TARGET_STRINGS[:4]:
  va=findstr(data,base,s)
  if va is None:continue
  o=va-base; lo=max(0,o-0x500); hi=min(len(data),o+0x500)
  region=data[lo:hi];i=0
  while i<len(region):
   if 32<=region[i]<127:
    j=i
    while j<len(region) and 32<=region[j]<127:j+=1
    if j-i>=5:
     txt=region[i:j].decode('ascii','replace')
     print(f'V108_NEAR={label}|va=0x{base+lo+i:08x}|{txt[:260]}')
    i=j
   else:i+=1
 print('\n=== V108_VERDICT ===')
 print('V108_GOAL=map_HighLowEdge_ScaleStep_APIs_to_exact_banks_sizes_and_control_flow')
 print('OVERALL_VERDICT=V108_EDGE_SCALE_STEP_API_XREF_EVIDENCE_EXTRACTED')
if __name__=='__main__':main()
