#!/usr/bin/env python3
"""Trace B2Y tone/WBCLIP/Y_BLEND driver entry points to MMIO fields.

Addresses come from v068 selector-to-driver calls. The report records literal
MMIO pages, masks/shifts, stores, calls and nearby diagnostic strings. It does
not infer undocumented field meaning from bit width alone.
"""
from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
BASE=0x42000000
FUNCS=[('TONE_DRIVER',0x0d42e0),('WBCLIP_DRIVER',0x0d4480),('Y_BLEND_DRIVER',0x0d4570)]

def u32(b,o):return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def litrefs(ins,data):
    out=[]
    try:ops=list(ins.operands)
    except Exception:return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            po=(((ins.address+4)&~3)+int(op.mem.disp))-BASE
            if 0<=po<=len(data)-4:out.append((po,u32(data,po)))
    return out

def ascii_near(data,off,r=0x500):
    lo=max(0,off-r);hi=min(len(data),off+r);out=[];i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=10:out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else:i+=1
    return out

def function_ins(md,data,start,maxspan=0x500):
    out=[]
    for ins in md.disasm(data[start:min(len(data),start+maxspan)],BASE+start):
        out.append(ins);off=ins.address-BASE
        if off>start+2 and ((ins.mnemonic.lower()=='pop' and 'pc' in ins.op_str.lower()) or (ins.mnemonic.lower()=='bx' and 'lr' in ins.op_str.lower())):break
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: script sections_dir')
    root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    print(f'V069_IMG_SIZE={len(data)}|base=0x{BASE:08x}')
    for label,start in FUNCS:
        print(f'\n=== V069_FUNC {label} start=0x{start:x} va=0x{BASE+start:08x} ===')
        for so,s in ascii_near(data,start):
            if any(k in s.lower() for k in ('b2y','tone','blend','clip','gamma','conversion','limit')):
                print(f'V069_NEAR_NAME=0x{so:x}|{s}')
        mmio=set();constants=[];stores=0;calls=[]
        for ins in function_ins(md,data,start):
            off=ins.address-BASE;extra=[]
            for po,v in litrefs(ins,data):
                extra.append(f'LIT=0x{po:x}->0x{v:08x}');constants.append(v)
                if 0x20000000<=v<0x21000000:mmio.add(v)
            if ins.mnemonic.lower().startswith('str'):stores+=1
            if ins.mnemonic.lower().startswith('bl'):
                try:op=ins.operands[0]
                except Exception:op=None
                if op is not None and op.type==ARM_OP_IMM:
                    calls.append((off,op.imm-BASE,op.imm));extra.append(f'CALL=0x{op.imm:08x}')
            print(f'V069_INS=0x{off:x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(extra)) if extra else ''))
        print('V069_MMIO='+(','.join(f'0x{x:08x}' for x in sorted(mmio)) or '-'))
        print(f'V069_STORE_COUNT={stores}')
        print('V069_LITERALS='+(','.join(f'0x{x:08x}' for x in dict.fromkeys(constants)) or '-'))
        seen=set()
        for frm,to,va in calls:
            if to in seen:continue
            seen.add(to);print(f'V069_CALL=from=0x{frm:x}|to=0x{to:x}|va=0x{va:08x}')
            for so,s in ascii_near(data,to,0x200):
                if any(k in s.lower() for k in ('b2y','tone','blend','clip','gamma','conversion','limit','gain')):
                    print(f'  V069_CALL_NAME=0x{so:x}|{s}')
    print('\nOVERALL_VERDICT=DRIVER_REGISTER_FIELDS_RECORDED')
if __name__=='__main__':main()
