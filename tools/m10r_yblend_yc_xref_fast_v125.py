#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

SETTERS={0x000d4480:'Y_BLEND_SETTER',0x000d4570:'YC_CONVERT_SETTER'}
NEEDLES={b'img_b2y_select_y_blend_paraset':'Y_BLEND_SELECT',b'YC CONVERSION':'YC_CONVERSION'}

def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def signext(v,bits):
 s=1<<(bits-1);return (v^s)-s

def thumb_bl_target(img,base,o):
 if o<0 or o+4>len(img):return None
 h1=u16(img,o);h2=u16(img,o+2)
 if (h1&0xf800)!=0xf000 or (h2&0xd000)!=0xd000:return None
 S=(h1>>10)&1;imm10=h1&0x3ff;J1=(h2>>13)&1;J2=(h2>>11)&1;imm11=h2&0x7ff
 I1=(~(J1^S))&1;I2=(~(J2^S))&1
 imm25=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
 return ((base+o+4)+signext(imm25,25))&0xffffffff

def dump_near(img,base,addr,label,before=64,after=20):
 a=max(base,addr-before)&~1;z=min(base+len(img),addr+after)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 print(f'V125_CONTEXT={label}|0x{a:08x}..0x{z:08x}')
 for ins in md.disasm(img[a-base:z-base],a):
  mark='|CALLSITE=1' if ins.address==addr else ''
  ann=[]
  try:
   for op in ins.operands:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
     p=((int(ins.address)+4)&~3)+int(op.mem.disp);po=p-base
     if 0<=po<=len(img)-4:ann.append(f'LIT=0x{p:08x}->0x{u32(img,po):08x}')
  except:pass
  print(f'V125_CTX_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}{mark}'+(('|'+'|'.join(ann)) if ann else ''))

def raw_find_all(img,pat):
 out=[];s=0
 while True:
  q=img.find(pat,s)
  if q<0:return out
  out.append(q);s=q+1

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v125 <sections>')
 img,base,fn=load(Path(sys.argv[1]));print(f'V125_IMG={fn}|base=0x{base:x}|size=0x{len(img):x}')

 print('\n######## FAST THUMB BL XREFS ########')
 hits=[]
 for o in range(0,len(img)-3,2):
  t=thumb_bl_target(img,base,o)
  if t in SETTERS:
   a=base+o;name=SETTERS[t];hits.append((a,t,name));print(f'V125_BL={name}|at=0x{a:08x}|target=0x{t:08x}')
 print(f'V125_BL_TOTAL={len(hits)}')
 for a,t,name in hits:dump_near(img,base,a,name)

 print('\n######## RAW SETTER POINTERS ########')
 for t,name in SETTERS.items():
  for v,kind in ((t,'EVEN'),(t|1,'THUMB')):
   hs=raw_find_all(img,struct.pack('<I',v))
   print(f'V125_SETTER_PTR={name}|kind={kind}|value=0x{v:08x}|count={len(hs)}|locs='+','.join(f'0x{base+x:08x}' for x in hs[:64]))

 print('\n######## STRING LOCATIONS / POINTERS / LOCAL XREFS ########')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for needle,label in NEEDLES.items():
  locs=raw_find_all(img,needle)
  print(f'V125_STRING={label}|count={len(locs)}|locs='+','.join(f'0x{base+x:08x}' for x in locs))
  for so in locs:
   sa=base+so
   ptrs=raw_find_all(img,struct.pack('<I',sa))
   print(f'V125_STRING_PTRS={label}|string=0x{sa:08x}|count={len(ptrs)}|locs='+','.join(f'0x{base+p:08x}' for p in ptrs[:128]))
   # Only disassemble around each pointer pool; find PC-relative loads that land on exact pool.
   for po in ptrs:
    pa=base+po;a=max(base,pa-0x1000)&~1;z=min(base+len(img),pa+0x100)
    for ins in md.disasm(img[a-base:z-base],a):
     try:
      for op in ins.operands:
       if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
        p=((int(ins.address)+4)&~3)+int(op.mem.disp)
        if p==pa:
         print(f'V125_STRING_XREF={label}|ins=0x{ins.address:08x}|pool=0x{pa:08x}')
         dump_near(img,base,ins.address,label+'_STRING_XREF',96,36)
     except:pass

 print('\nV125_GOAL=prove_direct_or_table_dispatch_callers_and_r1_setup_for_Y_BLEND_and_Yc_Convert_without_full_section_disassembly')
 print('OVERALL_VERDICT=V125_FAST_YBLEND_YC_XREF_COMPLETE')
if __name__=='__main__':main()
