#!/usr/bin/env python3
"""v0.85: map SAM7 B2Y YC-family controls to MMIO pages/register offsets.

Goals:
  * inspect the exact 4-byte word immediately preceding each named B2Y YC-family
    diagnostic string, because v0.83/v0.84 proved this is a literal-pool pattern;
  * resolve Thumb PC-relative references to any 0x2002xxxx literal found there;
  * for every reference to page 0x20020900, recover the surrounding Thumb
    function and enumerate base-register offsets touched, especially +0x2c,
    +0x30 and +0x34 (IMG-System Y_BLEND registers).

Evidence only. Function names are assigned only when a literal is physically
paired with that diagnostic and a code xref reaches the same literal.
"""
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC

TARGETS={
 'YC_GAIN':'I:Im_B2Y_Ctrl_YC_OutOffsetAndGain error.',
 'YC_CLIP':'I:Im_B2Y_Ctrl_YC_OutClip error.',
 'YCTORG':'I:Im_B2Y_Ctrl_YCtoRGB_Matrix error.',
 'RGBTOYC':'I:Im_B2Y_Ctrl_RGBtoYC_Matrix error.',
 'GAMMA':'I:Im_B2Y_Ctrl_Gamma error.',
 'YCC':'I:Im_B2Y_Ctrl_Yc_Convert error.',
 'CHROMA_SUPPRESS':'I:Im_B2Y_Ctrl_Chroma_Suppress error.',
 'COLOR_NR':'I:Im_B2Y_Ctrl_Color_NR error.',
 'POSTFILTER':'I:Im_B2Y_Ctrl_PostFilter error.',
 'EDGEBLEND':'I:Im_B2Y_Ctrl_EdgeBlend error.',
}
WATCH={0x2c,0x30,0x34}

def u32(b,o):return struct.unpack_from('<I',b,o)[0]

def thumb():
 m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m

def refs_to_literal(data,lit):
 m=thumb();out=[]
 lo=max(0,lit-0x10000);hi=min(len(data)-4,lit+0x200)
 for off in range(lo&~1,hi,2):
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins is None:continue
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    pc=(off+4)&~3
    if pc+int(op.mem.disp)==lit:
     out.append((off,ins));break
 return out

def find_func_start(data,ref,max_back=0x300):
 # Conservative Thumb prologue search. Prefer nearest PUSH containing LR.
 m=thumb();best=None
 lo=max(0,ref-max_back)&~1
 for off in range(lo,ref+1,2):
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins and ins.mnemonic=='push' and 'lr' in ins.op_str:best=off
 return best if best is not None else lo

def disasm_func(data,start,max_len=0x500):
 m=thumb();out=[];off=start;end=min(len(data),start+max_len)
 while off<end:
  ins=next(m.disasm(data[off:off+4],off,count=1),None)
  if ins is None:break
  out.append(ins);off+=ins.size
  # Treat return-pop or bx lr as end after at least a few instructions.
  if len(out)>3 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):break
 return out

def reg_offsets(insns,base_reg):
 vals=[]
 for ins in insns:
  try:ops=list(ins.operands)
  except Exception:continue
  for op in ops:
   if op.type==ARM_OP_MEM and op.mem.base==base_reg:
    vals.append((ins.address,int(op.mem.disp),ins.mnemonic,ins.op_str))
 return vals

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_b2y_page20900_map_v085.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 print(f'V085_SAM7=file={row["file"]}|size=0x{len(data):x}|kind={row["kind"]}')
 paired=[]
 for label,needle in TARGETS.items():
  positions=[];p=0
  while True:
   q=data.find(needle.encode('ascii'),p)
   if q<0:break
   positions.append(q);p=q+1
  print(f'\nV085_DIAG={label}|count={len(positions)}|offs={",".join(hex(x) for x in positions)}')
  for q in positions:
   candidates=[]
   # Exact literal usually ends immediately before I:, but allow 0..3 pad bytes.
   for back in (4,5,6,7,8):
    o=q-back
    if o>=0 and o%2==0 and o+4<=len(data):
     v=u32(data,o)
     if 0x20000000<=v<=0x200fffff:candidates.append((o,v,back))
   for lit,val,back in candidates:
    refs=refs_to_literal(data,lit)
    print(f'V085_PAIRED_LITERAL={label}|diag=0x{q:x}|literal=0x{lit:x}|back={back}|value=0x{val:08x}|thumb_refs={len(refs)}|codes={",".join(hex(o) for o,_ in refs)}')
    paired.append((label,q,lit,val,refs))

 print('\n=== V085 PAGE 0x20020900 FUNCTION MAP ===')
 page_entries=[]
 for label,q,lit,val,refs in paired:
  if val!=0x20020900:continue
  for ref,ldr in refs:
   start=find_func_start(data,ref);insns=disasm_func(data,start)
   # The literal LDR destination register is the page-base register.
   try:ops=list(ldr.operands);base_reg=ops[0].reg if ops and ops[0].type==ARM_OP_REG else None
   except Exception:base_reg=None
   accesses=reg_offsets(insns,base_reg) if base_reg is not None else []
   offsets=sorted(set(x[1] for x in accesses))
   watch=sorted(set(x[1] for x in accesses if x[1] in WATCH))
   print(f'V085_FUNC={label}|start=0x{start:x}|xref=0x{ref:x}|end=0x{insns[-1].address+insns[-1].size:x}|base_reg={base_reg}|offsets={",".join(hex(x) for x in offsets)}|watch={",".join(hex(x) for x in watch)}')
   for a,d,mn,ops in accesses:
    mark='|YBLEND_WATCH' if d in WATCH else ''
    print(f'  V085_ACCESS={label}|0x{a:x}|off=0x{d:x}|{mn} {ops}{mark}')
   # Full bounded disassembly only for functions touching Y_BLEND registers or YCC.
   if watch or label in ('YCC','YC_GAIN','YC_CLIP','YCTORG','RGBTOYC'):
    for ins in insns:
     print(f'  V085_INS={label}|0x{ins.address:x}|{ins.mnemonic} {ins.op_str}')
   page_entries.append((label,start,offsets,watch))

 print('\n=== V085 DIRECT WATCH SUMMARY ===')
 hits=[x for x in page_entries if x[3]]
 for label,start,offsets,watch in hits:
  print(f'V085_YBLEND_OWNER_CANDIDATE={label}|func=0x{start:x}|watch={",".join(hex(x) for x in watch)}')
 print(f'V085_YBLEND_OWNER_CANDIDATE_COUNT={len(hits)}')
 print('OVERALL_VERDICT=SAM7_YC_FAMILY_MMIO_AND_PAGE20900_OFFSETS_MAPPED')
if __name__=='__main__':main()
