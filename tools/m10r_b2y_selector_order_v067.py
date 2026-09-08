#!/usr/bin/env python3
"""Trace IMG-System B2Y selector strings, refs and orchestration call order.

Targets the recovered neighborhood containing tone-control TBL0/TBL1,
WBCLIPLEVEL, Y_BLEND and YC_CONVERSION. No semantic labels are assigned from
proximity alone: the report distinguishes direct string-pointer evidence,
branch targets and the 0x20020780 MMIO owner inventory.
"""
from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

IMG_BASE=0x42000000
TARGETS=[
 b'img_b2y_select_tone_control_paraset   TBL0',
 b'img_b2y_select_tone_control_paraset   TBL1',
 b'img_b2y_select_wbcliplevel_paraset',
 b'img_b2y_select_y_blend_paraset',
 b'img_b2y_select_yc_conversion_paraset',
 b'img_b2y_start()1',
]

def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def rows(root): return list(csv.DictReader((root/'sections.csv').open()))

def thumb(rootdata):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True; return md

def nearest_push(md,data,off,back=0x1000):
    hits=[]
    for p in range(max(0,off-back),off,2):
        i=next(md.disasm(data[p:p+4],IMG_BASE+p,count=1),None)
        if i and i.mnemonic.lower()=='push' and 'lr' in i.op_str.lower(): hits.append(p)
    return hits[-1] if hits else None

def litrefs(ins,data):
    ans=[]
    try: ops=list(ins.operands)
    except Exception: return ans
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            po=(((ins.address+4)&~3)+int(op.mem.disp))-IMG_BASE
            if 0<=po<=len(data)-4: ans.append((po,u32(data,po)))
    return ans

def scan_ptr_xrefs(md,data,ptr_off,ptr_val):
    out=[]
    lo=max(0,ptr_off-0x1200); hi=min(len(data)-2,ptr_off+0x200)
    for off in range(lo,hi,2):
        i=next(md.disasm(data[off:off+4],IMG_BASE+off,count=1),None)
        if i and any(po==ptr_off and v==ptr_val for po,v in litrefs(i,data)):
            out.append((off,i))
    return out

def ascii_near(data,off,r=0x180):
    lo=max(0,off-r); hi=min(len(data),off+r); out=[]; i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127: j+=1
            if j-i>=12: out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else: i+=1
    return out

def dump_function(md,data,start,span=0x500):
    end=min(len(data),start+span)
    print(f'V067_FUNC_DUMP=start=0x{start:x}|va=0x{IMG_BASE+start:08x}|span=0x{end-start:x}')
    for i in md.disasm(data[start:end],IMG_BASE+start):
        off=i.address-IMG_BASE
        extra=''
        if i.mnemonic.lower().startswith('bl'):
            try:
                op=i.operands[0]
                if op.type==ARM_OP_IMM: extra=f'|CALL_TARGET=0x{op.imm:08x}|target_off=0x{op.imm-IMG_BASE:x}'
            except Exception: pass
        lr=litrefs(i,data)
        if lr: extra += '|LITERALS='+','.join(f'0x{po:x}->0x{v:08x}' for po,v in lr)
        print(f'  V067_INS=0x{off:x}|{i.mnemonic} {i.op_str}{extra}')
        if off>start+4 and i.mnemonic.lower()=='pop' and 'pc' in i.op_str.lower(): break

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: script sections_dir')
    root=Path(sys.argv[1]); rr=rows(root)
    row=next((r for r in rr if r['name']=='IMG-System'),None)
    if not row: raise SystemExit('IMG-System missing')
    data=(root/row['file']).read_bytes(); md=thumb(data)
    print(f'V067_IMG_SIZE={len(data)}|base=0x{IMG_BASE:08x}')
    owners=[]
    for s in TARGETS:
        off=data.find(s)
        label=s.decode()
        print(f'\nV067_STRING={label}|off={"-" if off<0 else hex(off)}|va={"-" if off<0 else hex(IMG_BASE+off)}')
        if off<0: continue
        vals={IMG_BASE+off, IMG_BASE+off+1}
        ptrs=[]
        for val in vals:
            pat=struct.pack('<I',val); p=0
            while True:
                q=data.find(pat,p)
                if q<0: break
                ptrs.append((q,val)); p=q+1
        print(f'V067_POINTER_LITERALS={len(ptrs)}|'+(','.join(f'0x{q:x}->0x{v:08x}' for q,v in ptrs) or '-'))
        for q,v in ptrs:
            for xo,ins in scan_ptr_xrefs(md,data,q,v):
                owner=nearest_push(md,data,xo)
                print(f'V067_STRING_XREF={label}|ptr=0x{q:x}|code=0x{xo:x}|owner={"-" if owner is None else hex(owner)}|{ins.mnemonic} {ins.op_str}')
                if owner is not None: owners.append(owner)
    orch=0x154f88
    dump_function(md,data,orch,0x500)
    print('\n=== V067 CALL TARGET CONTEXT ===')
    seen=set()
    for i in md.disasm(data[orch:min(len(data),orch+0x500)],IMG_BASE+orch):
        if not i.mnemonic.lower().startswith('bl'): continue
        try: op=i.operands[0]
        except Exception: continue
        if op.type!=ARM_OP_IMM: continue
        to=op.imm-IMG_BASE
        if not (0<=to<len(data)) or to in seen: continue
        seen.add(to)
        print(f'V067_CALL=from=0x{i.address-IMG_BASE:x}|to=0x{to:x}|va=0x{op.imm:08x}')
        for so,ss in ascii_near(data,to):
            low=ss.lower()
            if any(k in low for k in ('b2y','tone','blend','conversion','clip','gamma','jpeg','rgb','ycc')):
                print(f'  V067_TARGET_ASCII=0x{so:x}|{ss}')
    print('\nOVERALL_VERDICT=SELECTOR_XREF_AND_CALL_ORDER_RECORDED_NO_PROXIMITY_SEMANTICS_ASSUMED')
if __name__=='__main__': main()
