#!/usr/bin/env python3
from __future__ import annotations
import csv,re,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC,ARM_REG_R0

PFX=4; HDR=PFX+0x10; STRIDE=0xA90
TARGETS={0x0C:'YC_CONVERSION',0x0D:'Y_BLEND'}
SETTERS={0x000D4480:'Y_BLEND_SETTER',0x000D4570:'YC_CONVERT_SETTER'}
TERMS=[b'Y_BLEND',b'YBlend',b'Y Blend',b'Yc_Convert',b'YCtoRGB',b'YC Conversion',b'YCC',b'Ycc',b'Blend']

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def s32(x):return x-0x100000000 if x&0x80000000 else x

def astrings(blob,minlen=5):
 out=[]
 for m in re.finditer(rb'[ -~]{%d,}'%minlen,blob):
  try:out.append((m.start(),m.group().decode('ascii')))
  except:pass
 return out

def records(data):
 count=u32(data,PFX+8); pay=HDR+count*STRIDE; out=[]
 for i in range(count):
  o=HDR+i*STRIDE; rid,rel,size=u32(data,o),u32(data,o+4),u32(data,o+8)
  out.append((i,rid,rel,size,pay+rel,data[o:o+STRIDE]))
 return out

def dump_records(b2y):
 rs=records(b2y)
 print(f'V123_B2Y_SIZE=0x{len(b2y):x}|record_count={len(rs)}')
 for rid,name in TARGETS.items():
  hits=[r for r in rs if r[1]==rid]
  print(f'\n=== V123_RECORDS {name} id=0x{rid:02x} count={len(hits)} ===')
  for occ,(idx,_,rel,size,p,hdr) in enumerate(hits):
   blob=b2y[p:p+size]; vals=[u32(blob,o) for o in range(0,len(blob)-3,4)]
   sels=[s for _,s in astrings(hdr,8) if 'B2Y' in s or 'MODE' in s or 'ISO' in s or 'SHARPNESS' in s]
   print(f'V123_REC={name}|occ={occ}|index={idx}|rel=0x{rel:x}|size=0x{size:x}|payload=0x{p:x}')
   print('V123_U32='+','.join(str(v) for v in vals))
   print('V123_S32='+','.join(str(s32(v)) for v in vals))
   print('V123_SELECTORS='+(' || '.join(sels) if sels else '<none>'))
   print('V123_HEX='+blob.hex())

def pc_lit_addr(ins,disp):return ((int(ins.address)+4)&~3)+int(disp)

def dump_setter(img,base,va,label):
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 off=va-base
 print(f'\n=== V123_SETTER {label} va=0x{va:08x} ===')
 if off<0 or off>=len(img):print('V123_OOB=1');return
 for k,ins in enumerate(md.disasm(img[off:off+0x600],va)):
  ann=[]
  try:ops=list(ins.operands)
  except:ops=[]
  for op in ops:
   if op.type==ARM_OP_MEM:
    if op.mem.base==ARM_REG_R0:
     ann.append(f'SRC_R0_OFF=0x{int(op.mem.disp)&0xffffffff:x}')
    if op.mem.base==ARM_REG_PC:
     la=pc_lit_addr(ins,op.mem.disp);lo=la-base
     if 0<=lo<=len(img)-4:
      v=u32(img,lo);ann.append(f'LITERAL=0x{la:08x}->0x{v:08x}')
      if 0x20000000<=v<=0x20ffffff:ann.append('MMIO=1')
  if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
   ann.append(f'CALL=0x{int(ops[0].imm)&0xffffffff:08x}')
  print(f'V123_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
  if k>4 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):
   break

def call_and_ptr_scan(img,base):
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 print('\n=== V123_SETTER_CALL_POINTER_SCAN ===')
 for va,name in SETTERS.items():
  calls=[]
  for ins in md.disasm(img,base):
   if ins.mnemonic not in ('bl','blx'):continue
   try:ops=list(ins.operands)
   except:continue
   if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&~1)==(va&~1):calls.append(ins.address)
  ptr=[]
  for o in range(0,len(img)-3,4):
   v=u32(img,o)
   if v in (va,va|1):ptr.append(base+o)
  print(f'V123_TARGET={name}|va=0x{va:08x}|direct_calls={len(calls)}|ptr_words={len(ptr)}')
  print('V123_CALLS='+','.join(f'0x{x:08x}' for x in calls))
  print('V123_PTRS='+','.join(f'0x{x:08x}' for x in ptr))
  for p in ptr[:16]:
   o=p-base; a=max(0,o-48);z=min(len(img),o+64)
   print(f'V123_PTR_NEIGHBOR={name}|at=0x{p:08x}|hex={img[a:z].hex()}')

def term_scan(root,rows):
 print('\n=== V123_FIRMWARE_TERM_SCAN ===')
 for r in rows:
  p=root/r['file']
  try:b=p.read_bytes()
  except:continue
  base=int(r['image_base'],16)
  lower=b.lower()
  for term in TERMS:
   tl=term.lower();start=0;seen=0
   while True:
    q=lower.find(tl,start)
    if q<0:break
    seen+=1
    a=max(0,q-96);z=min(len(b),q+len(term)+160)
    ctx=b[a:z]
    txt=''.join(chr(x) if 32<=x<127 else '.' for x in ctx)
    print(f'V123_TERM=section={r["name"]}|file={r["file"]}|term={term.decode("ascii","ignore")}|off=0x{q:x}|va=0x{base+q:x}|ctx={txt}')
    start=q+1
    if seen>=24:break

def main():
 if len(sys.argv)!=3:raise SystemExit('usage: v123 <sections_dir> <b2y>')
 root=Path(sys.argv[1]);b2y=Path(sys.argv[2]).read_bytes();rows=list(csv.DictReader((root/'sections.csv').open()))
 dump_records(b2y)
 row=next(r for r in rows if r['name']=='IMG-System');img=(root/row['file']).read_bytes();base=int(row['image_base'],16)
 print(f'\nV123_IMG_SYSTEM={row["file"]}|base=0x{base:x}|size=0x{len(img):x}')
 for va,label in SETTERS.items():dump_setter(img,base,va,label)
 call_and_ptr_scan(img,base)
 term_scan(root,rows)
 print('\nOVERALL_VERDICT=V123_YBLEND_YCCONVERT_RECORDS_SETTERS_CALLREFS_TERMS_EXTRACTED')
if __name__=='__main__':main()
