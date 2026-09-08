#!/usr/bin/env python3
"""Dump proven B2Y selector bodies around tone/WBCLIP/Y_BLEND/YC conversion.

The v067 address ordering strongly associates these starts with the immediately
preceding diagnostic strings. This probe records instructions, literal values,
MMIO pages, calls and target-local names without assigning undocumented field
semantics.
"""
from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
BASE=0x42000000
FUNCS=[('TONE_CAND',0x154d5c),('WBCLIP_CAND',0x154e18),('Y_BLEND_CAND',0x154ecc),('YC_CONVERSION_CAND',0x154f88)]

def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def ascii_near(data,off,r=0x250):
    lo=max(0,off-r); hi=min(len(data),off+r); out=[]; i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=10: out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else:i+=1
    return out

def litrefs(ins,data):
    out=[]
    try: ops=list(ins.operands)
    except Exception:return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            po=(((ins.address+4)&~3)+int(op.mem.disp))-BASE
            if 0<=po<=len(data)-4: out.append((po,u32(data,po)))
    return out

def function_ins(md,data,start,maxspan=0x800):
    out=[]
    for ins in md.disasm(data[start:min(len(data),start+maxspan)],BASE+start):
        out.append(ins)
        off=ins.address-BASE
        if off>start+2 and ins.mnemonic.lower()=='pop' and 'pc' in ins.op_str.lower(): break
        if off>start+2 and ins.mnemonic.lower()=='bx' and 'lr' in ins.op_str.lower(): break
    return out

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: script sections_dir')
    root=Path(sys.argv[1]); rows=list(csv.DictReader((root/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System'); data=(root/row['file']).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    print(f'V068_IMG_SIZE={len(data)}|base=0x{BASE:08x}')
    for label,start in FUNCS:
        print(f'\n=== V068_FUNC {label} start=0x{start:x} va=0x{BASE+start:08x} ===')
        for so,s in ascii_near(data,start,0x180):
            if any(k in s.lower() for k in ('tone','blend','clip','conversion','gamma','b2y')):
                print(f'V068_NEAR_NAME=0x{so:x}|{s}')
        mmio=set(); calls=[]; lits=[]
        for ins in function_ins(md,data,start):
            off=ins.address-BASE; extra=[]
            lr=litrefs(ins,data)
            for po,v in lr:
                lits.append((po,v)); extra.append(f'LIT=0x{po:x}->0x{v:08x}')
                if 0x20000000<=v<0x21000000: mmio.add(v)
            if ins.mnemonic.lower().startswith('bl'):
                try: op=ins.operands[0]
                except Exception: op=None
                if op is not None and op.type==ARM_OP_IMM:
                    to=op.imm-BASE; calls.append((off,to,op.imm)); extra.append(f'CALL=0x{op.imm:08x}')
            print(f'V068_INS=0x{off:x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(extra)) if extra else ''))
        print('V068_MMIO='+(','.join(f'0x{x:08x}' for x in sorted(mmio)) or '-'))
        uniq=[]; seen=set()
        for x in calls:
            if x[1] not in seen: seen.add(x[1]); uniq.append(x)
        for frm,to,va in uniq:
            print(f'V068_CALL=from=0x{frm:x}|to=0x{to:x}|va=0x{va:08x}')
            for so,s in ascii_near(data,to,0x1c0):
                if any(k in s.lower() for k in ('b2y','tone','blend','clip','conversion','gamma','rgb','ycc','limit','gain')):
                    print(f'  V068_CALL_NAME=0x{so:x}|{s}')
        # report unique non-address constants likely relevant to masks/coefficients
        vals=[]
        for po,v in lits:
            if v not in vals: vals.append(v)
        print('V068_LITERAL_VALUES='+(','.join(f'0x{v:08x}' for v in vals) or '-'))
    print('\nOVERALL_VERDICT=SELECTOR_BODIES_AND_MMIO_RECORDED')
if __name__=='__main__':main()
