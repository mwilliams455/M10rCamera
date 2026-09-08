#!/usr/bin/env python3
from __future__ import annotations
import csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

TARGETS={
 'HIGH_SCALE':'Im_B2Y_Set_HighEdge_Scale_Table error. write_ofs_num + array_num > MAX',
 'LOW_SCALE':'Im_B2Y_Set_LowEdge_Scale_Table error. write_ofs_num + array_num > MAX',
 'HIGH_STEP':'Im_B2Y_Set_HighEdge_Step_Table error. write_ofs_num + array_num > MAX',
 'LOW_STEP':'Im_B2Y_Set_LowEdge_Step_Table error. write_ofs_num + array_num > MAX',
 'HIGH_CTRL':'Im_B2Y_Ctrl_HighEdge error. b2y_ctrl_hedge = NULL',
 'LOW_CTRL':'Im_B2Y_Ctrl_LowEdge error. b2y_ctrl_ledge = NULL',
 'EDGE_BLEND':'Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL',
}
SYSTEM_TARGETS={
 'EDGE_GAIN':'        Edge Gain = %f',
 'EXTRACT_CORING':'extracted coring: %d',
 'SHARPNESS':'Sharpness',
 'CLIP_LOWER':'Clipping Lower Limit',
 'CLIP_UPPER':'Clipping Upper Limit',
}

def rows(d):return list(csv.DictReader((d/'sections.csv').open()))
def load(d,name):
 r=next(x for x in rows(d) if x['name']==name);return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']
def find(data,base,s):
 p=data.find(s.encode());return None if p<0 else base+p

def xrefs(data,base,targets):
 wanted={v:k for k,v in targets.items() if v is not None}; out=[]
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 insns=list(md.disasm(data,base)); idx={x.address:i for i,x in enumerate(insns)}
 for ins in insns:
  pc=((ins.address+4)&~3)
  if ins.mnemonic.startswith('adr'):
   try:
    imms=[int(o.imm) for o in ins.operands if o.type==ARM_OP_IMM]
    for imm in imms:
     # Capstone Thumb ADR operand is displacement in these firmware images.
     for cand in (pc+imm,pc-imm,imm):
      if cand in wanted:out.append((ins.address,wanted[cand],f'ADR pc=0x{pc:x} imm=0x{imm:x}',cand))
   except:pass
  if ins.mnemonic.startswith('ldr'):
   try:
    for o in ins.operands:
     if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
      la=pc+o.mem.disp; off=la-base
      if 0<=off<=len(data)-4:
       val=struct.unpack_from('<I',data,off)[0]
       if val in wanted:out.append((ins.address,wanted[val],f'LDR@0x{la:x}',val))
   except:pass
 return insns,idx,out

def window(insns,idx,site,label):
 i=idx[site];s=max(0,i-180)
 for j in range(i,max(-1,i-180),-1):
  x=insns[j]
  if x.mnemonic.startswith('push') and 'lr' in x.op_str:s=j;break
 e=min(len(insns),i+260)
 for j in range(i,min(len(insns),i+260)):
  x=insns[j]
  if (x.mnemonic.startswith('pop') and 'pc' in x.op_str) or (x.mnemonic=='bx' and x.op_str.strip()=='lr'):
   e=j+1;break
 print(f'V110_FUNC={label}|xref=0x{site:08x}|start=0x{insns[s].address:08x}|end=0x{insns[e-1].address:08x}')
 for x in insns[s:e]:print(f'V110_INS=0x{x.address:08x}|{x.mnemonic} {x.op_str}')

def probe(d,section,strings,prefix):
 data,base,fn=load(d,section); tg={k:find(data,base,s) for k,s in strings.items()}
 print(f'\n=== V110_{prefix}_TARGETS section={section} file={fn} ===')
 for k,v in tg.items():print(f'V110_TARGET={prefix}|{k}|{"NONE" if v is None else f"0x{v:08x}"}')
 insns,idx,hits=xrefs(data,base,tg)
 print(f'V110_XREF_COUNT={prefix}|{len(hits)}')
 seen=set()
 for site,label,kind,target in hits:
  key=(site,label)
  if key in seen:continue
  seen.add(key);print(f'V110_XREF={prefix}|site=0x{site:08x}|target={label}|kind={kind}|string=0x{target:08x}')
 for site,label,kind,target in hits:
  if (site,label) in seen:
   window(insns,idx,site,f'{prefix}_{label}');seen.remove((site,label))
 return data,base,insns,idx,hits

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: m10r_edge_api_xref_thumb_v110.py <sections>')
 d=Path(sys.argv[1])
 sam=probe(d,'IMG-SAM7',TARGETS,'SAM7')
 sysr=probe(d,'IMG-System',SYSTEM_TARGETS,'SYSTEM')
 print('\n=== V110_EXPECTED_TABLE_LIMITS ===')
 # Literal xrefs in the recovered API windows can directly show 0x4000/0x2000,
 # but print raw occurrence census too as a cross-check.
 data,base,insns,idx,hits=sam
 for val,label in ((0x4000,'SCALE_ENTRIES_EXPECTED_16384'),(0x2000,'STEP_ENTRIES_EXPECTED_8192'),(0x3ff,'SCALE_10BIT_MAX'),(0x3fff,'14BIT_MAX'),(0x1fff,'13BIT_MAX')):
  nd=struct.pack('<I',val);pos=[];st=0
  while True:
   q=data.find(nd,st)
   if q<0:break
   pos.append(base+q);st=q+1
  print(f'V110_CONST={label}|0x{val:x}|count={len(pos)}|sites='+','.join(f'0x{x:08x}' for x in pos[:80]))
 print('OVERALL_VERDICT=V110_CORRECTED_THUMB_ADR_EDGE_API_XREFS_EXTRACTED')
if __name__=='__main__':main()
