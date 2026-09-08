#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

TOKENS=('SCLM','TONM','SCLP','TONP')
PHRASES=(
 'img_b2y_select_high_freq_edge_enhancement_paraset',
 'img_b2y_select_low_freq_edge_enhancement_paraset',
)

def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def ascii_runs(b,minlen=4):
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
 if len(sys.argv)!=2:raise SystemExit('usage: v116 <sections_dir>')
 d=Path(sys.argv[1]);b,base,fn=load(d);runs=ascii_runs(b)
 print(f'V116_IMG={fn}|base=0x{base:x}|size=0x{len(b):x}')
 targets=[]
 for o,s in runs:
  if any(t in s for t in TOKENS) and any(p in s for p in PHRASES):
   targets.append((base+o,s))
 for va,s in targets:print(f'V116_TARGET=0x{va:08x}|{s}')
 print(f'V116_TARGET_COUNT={len(targets)}')

 # Build literal-pool pointer map to exact target strings.
 poolmap={}
 for va,s in targets:
  needle=struct.pack('<I',va);p=0
  while True:
   k=b.find(needle,p)
   if k<0:break
   poolmap.setdefault(base+k,[]).append((va,s));p=k+1

 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 xrefs=[]
 for ins in md.disasm(b,base):
  try:ops=list(ins.operands)
  except Exception:ops=[]
  pc=(int(ins.address)+4)&~3
  hits=[]
  if ins.mnemonic.startswith('ldr'):
   for op in ops:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     pool=pc+int(op.mem.disp)
     for va,s in poolmap.get(pool,[]):hits.append((va,s,'LDR',pool))
  if ins.mnemonic.startswith('adr'):
   for op in ops:
    if op.type==ARM_OP_IMM:
     imm=int(op.imm)&0xffffffff
     cands={imm,(pc+imm)&0xffffffff,(pc-imm)&0xffffffff}
     for va,s in targets:
      if va in cands:hits.append((va,s,'ADR',None))
  for h in hits:
   rec=(int(ins.address),)+h
   if rec not in xrefs:xrefs.append(rec)
 print(f'V116_XREF_COUNT={len(xrefs)}')

 # For each xref dump a window and annotate calls/literals. The selector code is
 # compact enough that +/-0x180 catches switch/branch logic and record IDs.
 for site,va,s,kind,pool in xrefs:
  token=next((t for t in TOKENS if t in s),'UNK')
  side='HF' if 'high_freq' in s else 'LF'
  print(f'\n=== V116_XREF side={side}|token={token}|site=0x{site:08x}|kind={kind}|string=0x{va:08x} ===')
  a=max(base,(site-0x1c0)&~1);z=min(base+len(b),site+0x220);off=a-base
  for ins in md.disasm(b[off:off+(z-a)],a):
   ann=[]
   try:ops=list(ins.operands)
   except Exception:ops=[]
   if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
    ann.append('CALL=0x%08x'%(int(ops[0].imm)&0xffffffff))
   for op in ops:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     pp=((int(ins.address)+4)&~3)+int(op.mem.disp);po=pp-base
     if 0<=po<=len(b)-4:
      vv=u32(b,po);ann.append('LIT@0x%08x=0x%08x'%(pp,vv))
   mark='|XREF=1' if int(ins.address)==site else ''
   print(f'V116_INS={side}_{token}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}{mark}'+(('|'+'|'.join(ann)) if ann else ''))

 print('\n=== V116_TARGET_NEIGHBOR_STRINGS ===')
 for va,s in targets:
  o=va-base
  print(f'V116_ANCHOR=0x{va:08x}|{s}')
  for oo,ss in runs:
   if abs(oo-o)<=0x180 and oo!=o:
    print(f'V116_NEAR=anchor=0x{va:08x}|va=0x{base+oo:08x}|{ss}')

 print('\nV116_GOAL=resolve_SCLM_TONM_SCLP_TONP_meaning_and_map_to_HF_LF_control_record_substructures')
 print('OVERALL_VERDICT=V116_EDGE_SELECTOR_SUFFIX_XREFS_EXTRACTED')
if __name__=='__main__':main()
