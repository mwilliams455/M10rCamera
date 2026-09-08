#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
LO=0x00051d00;HI=0x00052250;STR=0x00051ffb

def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-SAM7')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def ascii_at(b,base,a,n=180):
 o=a-base
 if not 0<=o<len(b):return None
 e=b.find(b'\0',o,min(len(b),o+n));q=b[o:e]
 if e>o and q and all(32<=x<127 for x in q):return q.decode('ascii','replace')
 return None

def refs_string(ins,b,base):
 out=[]
 try:
  # Thumb ADR pseudo often appears as adr rd, #imm; Capstone operand imm can be absolute or displacement depending version.
  if ins.mnemonic=='adr' and len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_IMM:
   imm=int(ins.operands[1].imm)
   cand=[imm,((ins.address+4)&~3)+imm]
   for x in cand:
    if x==STR:out.append('ADR_STR')
  for op in ins.operands:
   if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
    p=((int(ins.address)+4)&~3)+int(op.mem.disp);po=p-base
    if 0<=po<=len(b)-4:
     v=u32(b,po)
     out.append(f'LIT=0x{p:08x}->0x{v:08x}')
     if v==STR:out.append('LIT_STR')
 except:pass
 return out

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v131 <sections>')
 b,base,fn=load(Path(sys.argv[1]));print(f'V131_SAM7={fn}|base=0x{base:08x}|scan=0x{LO:08x}..0x{HI:08x}|str=0x{STR:08x}')
 print('V131_STR_TEXT='+str(ascii_at(b,base,STR)))
 # Raw string pointer occurrences.
 for val,kind in ((STR,'EVEN'),(STR|1,'THUMB')):
  pat=struct.pack('<I',val);p=0;hs=[]
  while 1:
   q=b.find(pat,p)
   if q<0:break
   hs.append(base+q);p=q+1
  print(f'V131_STR_PTR={kind}|count={len(hs)}|'+','.join(f'0x{x:08x}' for x in hs))

 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=False
 # Find raw 16-bit PUSH encodings with LR bit in likely code region, then independently decode each candidate.
 cands=[]
 for a in range(LO,HI,2):
  h=u16(b,a-base)
  # PUSH T1: 1011 0 10 0 M reglist => mask FE00 == B400; M(bit8)=1 means LR included.
  if (h & 0xfe00)==0xb400 and (h & 0x0100):cands.append(a)
 print('V131_PROLOGUES='+','.join(f'0x{x:08x}' for x in cands))
 for a in cands:
  print(f'\n######## V131_FUNC_CAND 0x{a:08x} ########')
  hit=False;count=0
  for ins in md.disasm(b[a-base:min(len(b),a-base+0x380)],a):
   count+=1;ann=refs_string(ins,b,base)
   try:
    if ins.mnemonic in ('bl','blx') and ins.operands and ins.operands[0].type==ARM_OP_IMM:ann.append(f'CALL=0x{int(ins.operands[0].imm)&~1:08x}')
   except:pass
   if 'ADR_STR' in ann or 'LIT_STR' in ann:hit=True
   if ins.address<=a+0x80 or ann or (ins.mnemonic in ('pop','bx') and ('pc' in ins.op_str or ins.op_str.strip()=='lr')):
    print(f'V131_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
   if (ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr'):
    print(f'V131_RETURN=0x{ins.address:08x}|string_ref={int(hit)}|insns={count}');break
   # stop if decoder enters known string bytes
   if STR<=ins.address<STR+0x60:break
  print(f'V131_CAND_SUMMARY=start=0x{a:08x}|string_ref={int(hit)}')
 print('\nV131_GOAL=identify_exact_Im_B2Y_Ctrl_Yc_Convert_function_start_end_from_real_Thumb_prologue_and_error_string_reference')
 print('OVERALL_VERDICT=V131_YC_SDK_BOUNDARY_PROBE_COMPLETE')
if __name__=='__main__':main()
