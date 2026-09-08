#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,re,struct,sys
from collections import Counter,defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC,ARM_REG_R0

PFX=4; HDR=PFX+0x10; STRIDE=0xA90
TARGETS={0x0C:'YC_CONVERT',0x0D:'Y_BLEND'}
SETTERS=[(0x000d4380,0x000d4570,'Y_BLEND_CONTEXT'),(0x000d4570,0x000d47c0,'YC_CONVERT_SETTER')]

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def s32(v): return v-0x100000000 if v&0x80000000 else v
def strings(blob):
 out=[]
 for m in re.finditer(rb'[ -~]{8,}',blob):
  try: out.append(m.group().decode('ascii'))
  except: pass
 return out

def parse(data):
 count=u32(data,PFX+8); payload=HDR+count*STRIDE; out=[]
 for idx in range(count):
  o=HDR+idx*STRIDE; rid,rel,size=u32(data,o),u32(data,o+4),u32(data,o+8)
  if rid not in TARGETS: continue
  h=data[o:o+STRIDE]; b=data[payload+rel:payload+rel+size]
  out.append({'idx':idx,'rid':rid,'name':TARGETS[rid],'size':size,'blob':b,'strings':strings(h)})
 return out

def vals32(b): return list(struct.unpack_from('<'+'I'*(len(b)//4),b,0)) if len(b)>=4 else []
def vals16(b): return list(struct.unpack_from('<'+'H'*(len(b)//2),b,0)) if len(b)>=2 else []
def sel_short(ss):
 q=[s for s in ss if ('B2YMODE' in s or 'SHARPNESS' in s or 'ISO:' in s or 'MODE:' in s)]
 return q[:10]

def survey_records(recs):
 for rid,name in TARGETS.items():
  rr=[r for r in recs if r['rid']==rid]
  print(f'\n######## V123_RECORD_FAMILY {name} id=0x{rid:02x} count={len(rr)} ########')
  groups=defaultdict(list)
  for r in rr: groups[(len(r['blob']),hashlib.sha256(r['blob']).hexdigest())].append(r)
  print(f'V123_UNIQUE_PAYLOADS={name}|count={len(groups)}')
  for gi,((size,sha),gg) in enumerate(sorted(groups.items(),key=lambda x:min(r['idx'] for r in x[1]))):
   b=gg[0]['blob']; v32=vals32(b); v16=vals16(b)
   print(f'V123_PAYLOAD={name}|group={gi}|size=0x{size:x}|sha256={sha}|records='+','.join(str(r['idx']) for r in gg))
   print('V123_U32='+','.join(f'{i}:{v}' for i,v in enumerate(v32[:64])))
   print('V123_S32='+','.join(f'{i}:{s32(v)}' for i,v in enumerate(v32[:64])))
   print('V123_U16='+','.join(f'{i}:{v}' for i,v in enumerate(v16[:96])))
   for r in gg[:12]: print(f'V123_SELECTOR={name}|idx={r["idx"]}|'+ ' || '.join(sel_short(r['strings'])))
   if len(gg)>12: print(f'V123_SELECTOR_MORE={name}|count={len(gg)-12}')
  # Field variation across payload groups by dword and halfword positions.
  if groups:
   reps=[g[0]['blob'] for g in groups.values()]
   min4=min(len(b)//4 for b in reps); min2=min(len(b)//2 for b in reps)
   for i in range(min4):
    vs=sorted({u32(b,i*4) for b in reps})
    if len(vs)>1: print(f'V123_DWORD_VARIATION={name}|off=0x{i*4:02x}|values='+','.join(str(v) for v in vs))
   for i in range(min2):
    vs=sorted({struct.unpack_from('<H',b,i*2)[0] for b in reps})
    if len(vs)>1: print(f'V123_HALF_VARIATION={name}|off=0x{i*2:02x}|values='+','.join(str(v) for v in vs))

def load_img(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def rname(md,r):
 try:return md.reg_name(r)
 except:return str(r)
def lit32(img,base,a):
 o=a-base
 return u32(img,o) if 0<=o<=len(img)-4 else None

def dump_setters(sections):
 img,base,fn=load_img(sections); print(f'\nV123_IMG={fn}|base=0x{base:x}|size=0x{len(img):x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for a,z,label in SETTERS:
  print(f'\n######## V123_SETTER {label}|0x{a:08x}..0x{z:08x} ########')
  const={}; off=a-base
  for ins in md.disasm(img[off:off+(z-a)],a):
   try:ops=list(ins.operands)
   except Exception:ops=[]
   ann=[]
   for op in ops:
    if op.type==ARM_OP_MEM:
     bs=op.mem.base;ix=op.mem.index;disp=int(op.mem.disp);src=None
     if bs==ARM_REG_R0 and ix==0: src=disp
     elif ix==ARM_REG_R0 and bs in const: src=const[bs]+disp
     elif bs==ARM_REG_R0 and ix in const: src=const[ix]+disp
     if src is not None and -0x20<=src<=0x100: ann.append(f'SRC_FIELD=0x{src:x}')
     if bs==ARM_REG_PC:
      p=((int(ins.address)+4)&~3)+disp;v=lit32(img,base,p)
      if v is not None: ann.append(f'LITERAL=0x{p:08x}->0x{v:08x}')
   if ins.mnemonic in ('ands','and','bics','lsls','lsrs','lsl','lsr','ubfx','bfi','orrs','orr','str','strh','strb','ldr','ldrh','ldrb','mov','movs','adds','add','subs','sub','bl','blx','bx','pop') or ann:
    print(f'V123_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else ''))
   # conservative constant propagation for indexed source offsets
   if ops and ops[0].type==ARM_OP_REG:
    dst=ops[0].reg;m=ins.mnemonic
    if m in ('mov','movs') and len(ops)>=2:
     if ops[1].type==ARM_OP_IMM: const[dst]=int(ops[1].imm)&0xffffffff
     elif ops[1].type==ARM_OP_REG and ops[1].reg in const: const[dst]=const[ops[1].reg]
     else: const.pop(dst,None)
    elif m in ('lsls','lsl') and len(ops)>=3 and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM and ops[1].reg in const:
     const[dst]=(const[ops[1].reg]<<int(ops[2].imm))&0xffffffff
    elif m in ('adds','add') and len(ops)>=3 and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM and ops[1].reg in const:
     const[dst]=(const[ops[1].reg]+int(ops[2].imm))&0xffffffff
    elif m.startswith('ldr') or m.startswith('ldm') or m in ('ands','and','orrs','orr','bics','eors','muls','ubfx'):
     const.pop(dst,None)

 # SDK/debug string census around Y blend / YC conversion terminology.
 print('\n######## V123_STRING_CENSUS ########')
 for m in re.finditer(rb'[ -~]{5,}',img):
  s=m.group().decode('ascii','ignore'); sl=s.lower()
  if ('yblend' in sl or 'y_blend' in sl or 'yc_convert' in sl or 'yc conversion' in sl or 'ycconvert' in sl or 'blend y' in sl):
   print(f'V123_STRING=0x{base+m.start():08x}|{s}')

def main():
 if len(sys.argv)!=3: raise SystemExit('usage: v123 <sections_dir> <B2Y>')
 sections=Path(sys.argv[1]); data=Path(sys.argv[2]).read_bytes(); recs=parse(data)
 print(f'V123_B2Y_SIZE=0x{len(data):x}|target_records={len(recs)}')
 survey_records(recs); dump_setters(sections)
 print('\nV123_GOAL=separate_Y_BLEND_and_YcConvert_fixed_defaults_from_mode_ISO_dependent_local_controls_and_map_exact_setter_field_widths')
 print('OVERALL_VERDICT=V123_YBLEND_YC_FIELD_SURVEY_COMPLETE')
if __name__=='__main__': main()
