#!/usr/bin/env python3
"""v0.81: recover SAM7 B2Y string references without assuming absolute pointers.

For every ARM/Thumb PC-relative literal load in IMG-SAM7, derive the runtime
base that would make the loaded word point at each target diagnostic string.
A genuine relocated string base should recur across multiple independent
controls.  Also enumerate direct ADR references and quantify the repeated
0x13400-spaced data occurrences seen by v0.80.
"""
from __future__ import annotations
import collections,csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_OP_IMM,ARM_REG_PC

TARGETS={
 'GAMMA':'Im_B2Y_Ctrl_Gamma error. b2y_ctrl_gamma = NULL',
 'CC1':'Im_B2Y_Ctrl_CC_Matrix error. b2y_ctrl_cc1 = NULL',
 'YCC':'Im_B2Y_Ctrl_Yc_Convert error. b2y_ctrl_ycc = NULL',
 'CHROMA_SUPPRESS':'Im_B2Y_Ctrl_Chroma_Suppress error. b2y_ctrl_cs = NULL',
 'COLOR_NR':'Im_B2Y_Ctrl_Color_NR error. b2y_ctrl_clpf = NULL',
 'POSTFILTER':'Im_B2Y_Ctrl_PostFilter error. b2y_ctrl_post_filter = NULL',
 'EDGEBLEND':'Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL',
}

def printable(x):return 32<=x<127

def run_start(data,o):
 while o>0 and printable(data[o-1]):o-=1
 return o

def u32(data,o):return struct.unpack_from('<I',data,o)[0]

def scan_mode(data,mode_name,mode,step,targets):
 md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
 bases=collections.defaultdict(lambda:collections.defaultdict(list));adrs=[];lit_count=0
 for off in range(0,len(data)-4,step):
  ins=next(md.disasm(data[off:off+4],off,count=1),None)
  if ins is None:continue
  try:ops=list(ins.operands)
  except Exception:continue
  # Direct ADR alias. With address==file offset, PC-relative target is a file offset.
  if ins.mnemonic=='adr' and len(ops)>=2 and ops[1].type==ARM_OP_IMM:
   dest=int(ops[1].imm)&0xffffffff
   for label,poss in targets.items():
    if dest in poss:
     adrs.append((label,off,dest,ins.mnemonic,ins.op_str))
  for op in ops:
   if op.type!=ARM_OP_MEM or op.mem.base!=ARM_REG_PC:continue
   pc=(off+8) if mode_name=='ARM' else ((off+4)&~3)
   lit=pc+int(op.mem.disp)
   if lit<0 or lit>len(data)-4:continue
   w=u32(data,lit);lit_count+=1
   for label,poss in targets.items():
    for pos_kind,s in poss.items():
     base=(w-s)&0xffffffff
     # Strong bases should be naturally aligned; keep 4 KiB and 64 KiB-style links.
     if (base&0xfff)==0:
      bases[base][label].append((off,lit,w,pos_kind,ins.mnemonic,ins.op_str))
  # only one PC-relative memory operand is relevant for literal resolution
 return bases,adrs,lit_count

def merge(dst,src,mode):
 for base,bylabel in src.items():
  for label,refs in bylabel.items():
   dst[base][label].extend([(mode,)+r for r in refs])

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_pc_relative_xrefs_v081.py <sections_dir>')
 root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7');data=(root/row['file']).read_bytes()
 targets={}
 print(f'V081_SAM7=file={row["file"]}|size=0x{len(data):x}|kind={row["kind"]}')
 for label,needle in TARGETS.items():
  sub=data.find(needle.encode());rs=run_start(data,sub) if sub>=0 else -1
  targets[label]={'run':rs,'substring':sub}
  print(f'V081_TARGET={label}|run=0x{rs:x}|substring=0x{sub:x}|delta={sub-rs}')
 allbases=collections.defaultdict(lambda:collections.defaultdict(list));alladrs=[];counts={}
 for mode_name,mode,step in [('ARM',CS_MODE_ARM,4),('THUMB',CS_MODE_THUMB,2)]:
  b,a,n=scan_mode(data,mode_name,mode,step,targets);merge(allbases,b,mode_name);alladrs.extend((mode_name,)+x for x in a);counts[mode_name]=n
 print(f'V081_LITERAL_LOADS=ARM:{counts["ARM"]},THUMB:{counts["THUMB"]}')
 ranked=[]
 for base,bylabel in allbases.items():
  if len(bylabel)>=2:ranked.append((len(bylabel),sum(len(v) for v in bylabel.values()),base,bylabel))
 ranked.sort(reverse=True)
 print('\n=== V081 RELOCATION BASES SUPPORTED BY PC-RELATIVE LOADS ===')
 for nlab,nref,base,bylabel in ranked[:30]:
  print(f'V081_BASE=0x{base:08x}|targets={nlab}|refs={nref}|labels={",".join(sorted(bylabel))}')
 strong=[x for x in ranked if x[0]>=3]
 for nlab,nref,base,bylabel in strong[:8]:
  for label,refs in sorted(bylabel.items()):
   for mode,code,lit,w,kind,mn,ops in refs[:8]:
    print(f'V081_XREF={label}|base=0x{base:08x}|mode={mode}|code=0x{code:x}|lit=0x{lit:x}|word=0x{w:08x}|target_kind={kind}|{mn} {ops}')
 print('\n=== V081 DIRECT ADR REFERENCES ===')
 for mode,label,code,dest,mn,ops in alladrs:
  print(f'V081_ADR={label}|mode={mode}|code=0x{code:x}|target=0x{dest:x}|{mn} {ops}')
 print(f'V081_ADR_COUNT={len(alladrs)}')

 # v0.80 found three raw-word occurrences separated by exactly 0x13400 for
 # CC1/YCC/EDGEBLEND under a spurious base. Quantify local byte repetition.
 anchors=[0xc9c84,0xdd084,0xf0484];span=0x1000
 if anchors[-1]+span<=len(data):
  chunks=[data[a:a+span] for a in anchors]
  def eq(a,b):return sum(x==y for x,y in zip(a,b))/len(a)
  print(f'V081_BANK_LOCAL_EQUALITY=span=0x{span:x}|d01=0x{anchors[1]-anchors[0]:x}|d12=0x{anchors[2]-anchors[1]:x}|eq01={eq(chunks[0],chunks[1]):.6f}|eq12={eq(chunks[1],chunks[2]):.6f}|eq02={eq(chunks[0],chunks[2]):.6f}')
 print('OVERALL_VERDICT=SAM7_PC_RELATIVE_STRING_ADDRESSING_ENUMERATED_WITHOUT_POINTER_ASSUMPTION')
if __name__=='__main__':main()
