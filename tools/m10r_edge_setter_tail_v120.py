#!/usr/bin/env python3
from __future__ import annotations
import csv,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_R0

RANGES=[
 (0x000d1de8,0x000d2300,'HF'),
 (0x000d2a2c,0x000d3540,'LF'),
]

def load(d):
 rows=list(csv.DictReader((d/'sections.csv').open()));r=next(x for x in rows if x['name']=='IMG-System')
 return (d/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def rname(md,r):
 try:return md.reg_name(r)
 except:return str(r)

def main():
 if len(sys.argv)!=2:raise SystemExit('usage: v120 <sections_dir>')
 d=Path(sys.argv[1]);b,base,fn=load(d)
 print(f'V120_IMG={fn}|base=0x{base:x}|size=0x{len(b):x}')
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;md.skipdata=True
 for a,z,label in RANGES:
  print(f'\n=== V120_RANGE {label}|0x{a:08x}..0x{z:08x} ===')
  off=a-base
  # Lightweight constant propagation is enough for the common sequence
  # movs rx,#ofs ; ldr/ldrh ry,[rx,r0], including offsets >0xff built by shifts/adds.
  const={}
  for ins in md.disasm(b[off:off+(z-a)],a):
   try:ops=list(ins.operands)
   except Exception:ops=[]
   ann=[]

   # Apply simple constant propagation after using current constants for mem annotation.
   for op in ops:
    if op.type==ARM_OP_MEM:
     bs=op.mem.base; ix=op.mem.index; disp=int(op.mem.disp)
     src_off=None
     # Direct [r0,#disp]
     if bs==ARM_REG_R0 and ix==0:
      src_off=disp
     # Indexed [constReg,r0] or [r0,constReg]
     elif ix==ARM_REG_R0 and bs in const:
      src_off=const[bs]+disp
     elif bs==ARM_REG_R0 and ix in const:
      src_off=const[ix]+disp
     if src_off is not None and 0<=src_off<=0x1c0:
      ann.append(f'SRC_FIELD=0x{src_off:03x}/dword{src_off//4}')
     # expose all memory addressing in the critical tail regardless
     if src_off is not None or (0xb0<=disp<=0x1c0):
      ann.append('MEM='+rname(md,bs)+(('+'+rname(md,ix)) if ix else '')+f'{disp:+#x}')

   # Print every instruction around source-field accesses, calls/branches, and all
   # arithmetic that can construct indexed source offsets.
   interesting=bool(ann) or ins.mnemonic in ('movs','mov','lsls','lsr','lsrs','adds','add','subs','sub','ldr','ldrh','ldrb','str','strh','b','beq','bne','cbz','cbnz','bl','blx','pop','bx')
   if interesting:
    cstate=','.join(f'{rname(md,k)}=0x{v:x}' for k,v in sorted(const.items()))
    print(f'V120_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ann)) if ann else '')+(f'|CONST_BEFORE={cstate}' if cstate and ann else ''))

   # Constant propagation update. Conservative: discard destination when unknown.
   if ops and ops[0].type==ARM_OP_REG:
    dst=ops[0].reg
    m=ins.mnemonic
    if m in ('movs','mov') and len(ops)>=2:
     if ops[1].type==ARM_OP_IMM: const[dst]=int(ops[1].imm)&0xffffffff
     elif ops[1].type==ARM_OP_REG and ops[1].reg in const: const[dst]=const[ops[1].reg]
     else: const.pop(dst,None)
    elif m in ('lsls','lsl') and len(ops)>=3 and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM and ops[1].reg in const:
     const[dst]=(const[ops[1].reg] << int(ops[2].imm))&0xffffffff
    elif m in ('lsrs','lsr') and len(ops)>=3 and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM and ops[1].reg in const:
     const[dst]=(const[ops[1].reg] >> int(ops[2].imm))&0xffffffff
    elif m in ('adds','add'):
     if len(ops)==2 and ops[1].type==ARM_OP_IMM and dst in const: const[dst]=(const[dst]+int(ops[1].imm))&0xffffffff
     elif len(ops)>=3 and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM and ops[1].reg in const: const[dst]=(const[ops[1].reg]+int(ops[2].imm))&0xffffffff
     else: const.pop(dst,None)
    elif m in ('subs','sub'):
     if len(ops)==2 and ops[1].type==ARM_OP_IMM and dst in const: const[dst]=(const[dst]-int(ops[1].imm))&0xffffffff
     elif len(ops)>=3 and ops[1].type==ARM_OP_REG and ops[2].type==ARM_OP_IMM and ops[1].reg in const: const[dst]=(const[ops[1].reg]-int(ops[2].imm))&0xffffffff
     else: const.pop(dst,None)
    elif m.startswith('ldr') or m.startswith('ldm') or m in ('orrs','ands','bics','eors','muls'):
     const.pop(dst,None)

 print('\nV120_TARGET_FIELDS=HF dword70/0x118 ISO-dependent scalar; dword71/0x11c=1023; dword72..77/0x120..0x134 sharpness 500/1000/1500; dword89..94/0x164..0x178 second sharpness group')
 print('V120_GOAL=map_indexed_tail_control_fields_to_exact_HighEdge_LowEdge_MMIO_registers_and_bit_widths')
 print('OVERALL_VERDICT=V120_EDGE_SETTER_INDEXED_TAIL_TRACED')
if __name__=='__main__':main()
