#!/usr/bin/env python3
"""v0.87: map named SAM7 YC control APIs to MMIO literal pools/functions.

v0.85 proved Yc_Convert owns page 0x20020900 including +0x20..+0x34. This
probe broadens the same method for YC_OutOffsetAndGain, YC_OutClip,
YCtoRGB_Matrix, RGBtoYC_Matrix and nearby YC controls. It searches a bounded
literal-pool neighborhood around each diagnostic, accepts only 0x200xxxxx
words with actual Thumb PC-relative code xrefs, then enumerates register
accesses relative to the loaded page base.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC

TARGETS={
 'YC_GAIN':'Im_B2Y_Ctrl_YC_OutOffsetAndGain error.',
 'YC_CLIP':'Im_B2Y_Ctrl_YC_OutClip error.',
 'YCTORG':'Im_B2Y_Ctrl_YCtoRGB_Matrix error.',
 'RGBTOYC':'Im_B2Y_Ctrl_RGBtoYC_Matrix error.',
 'YCC':'Im_B2Y_Ctrl_Yc_Convert error.',
 'CHROMA_SUPPRESS':'Im_B2Y_Ctrl_Chroma_Suppress error.',
 'COLOR_NR':'Im_B2Y_Ctrl_Color_NR error.',
 'POSTFILTER':'Im_B2Y_Ctrl_PostFilter error.',
}

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def md():m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m

def refs(data,lit):
 m=md();out=[];lo=max(0,lit-0x12000)&~1;hi=min(len(data)-4,lit+0x200)
 for off in range(lo,hi,2):
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins is None:continue
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    if ((off+4)&~3)+int(op.mem.disp)==lit:out.append((off,ins));break
 return out

def func_start(data,ref):
 m=md();best=None;lo=max(0,ref-0x500)&~1
 for off in range(lo,ref+1,2):
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins and ins.mnemonic=='push' and 'lr' in ins.op_str:best=off
 return best

def disfunc(data,start,maxlen=0x600):
 if start is None:return []
 m=md();out=[];off=start;end=min(len(data),start+maxlen)
 while off<end:
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins is None:break
  out.append(ins);off+=ins.size
  if len(out)>4 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):break
 return out

def accesses(insns,reg):
 out=[]
 for ins in insns:
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==reg:
    out.append((ins.address,int(op.mem.disp),ins.mnemonic,ins.op_str))
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_yc_named_controls_v087.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 print(f'V087_SAM7=file={row["file"]}|size=0x{len(data):x}|kind={row["kind"]}')
 seen=set();mapped=[]
 for label,needle in TARGETS.items():
  poss=[];p=0
  while True:
   q=data.find(needle.encode(),p)
   if q<0:break
   poss.append(q);p=q+1
  print(f'\nV087_DIAG={label}|count={len(poss)}|offs={",".join(hex(x) for x in poss)}')
  for q in poss:
   lo=max(0,q-0x100);hi=min(len(data)-4,q+0x10)
   lits=[]
   for o in range(lo&~1,hi+1,2):
    v=u32(data,o)
    if 0x20000000<=v<=0x200fffff:
     rr=refs(data,o)
     if rr:lits.append((o,v,rr))
   # Rank nearer diagnostics first, but preserve all xref-backed literals.
   lits.sort(key=lambda x:abs(q-x[0]))
   for lit,val,rr in lits[:12]:
    print(f'V087_LITERAL={label}|diag=0x{q:x}|lit=0x{lit:x}|delta={q-lit}|page=0x{val:08x}|refs={len(rr)}|codes={",".join(hex(x) for x,_ in rr)}')
    for ref,ldr in rr:
     key=(label,lit,ref)
     if key in seen:continue
     seen.add(key);start=func_start(data,ref);insns=disfunc(data,start)
     try:ops=list(ldr.operands);breg=ops[0].reg if ops and ops[0].type==ARM_OP_REG else None
     except Exception:breg=None
     aa=accesses(insns,breg) if breg is not None else []
     offs=sorted(set(d for _,d,_,_ in aa))
     print(f'V087_FUNC={label}|page=0x{val:08x}|start={hex(start) if start is not None else "NONE"}|xref=0x{ref:x}|base_reg={breg}|offsets={",".join(hex(x) for x in offs)}')
     for a,d,mn,opstr in aa:print(f'  V087_ACCESS={label}|page=0x{val:08x}|0x{a:x}|off=0x{d:x}|{mn} {opstr}')
     mapped.append((label,val,start,tuple(offs)))
 print('\n=== V087 UNIQUE MAP ===')
 uniq=[]
 for x in mapped:
  if x not in uniq:uniq.append(x)
 for label,page,start,offs in uniq:
  print(f'V087_MAP={label}|page=0x{page:08x}|func={hex(start) if start is not None else "NONE"}|offsets={",".join(hex(x) for x in offs)}')
 print(f'V087_MAP_COUNT={len(uniq)}')
 print('OVERALL_VERDICT=NAMED_SAM7_YC_CONTROL_MMIO_FAMILIES_ENUMERATED')
if __name__=='__main__':main()
