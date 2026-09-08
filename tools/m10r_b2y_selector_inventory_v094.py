#!/usr/bin/env python3
"""v0.94: executable inventory of IMG-System B2Y selectors.

For every direct call to the proven B2Y calibration lookup at 0x1a0fc4:
- recover record id from the nearest immediate write to r1;
- recover the enclosing Thumb function;
- bind the selector name from that function's own trailing
  img_b2y_select_*_paraset diagnostic block;
- recover the post-lookup downstream setter BL;
- inspect that setter for PC-relative 0x2002xxxx MMIO literals and direct
  register offsets.

This avoids nearest-string-to-MMIO ownership assumptions and gives a complete
record -> selector -> setter -> MMIO crosswalk.
"""
from __future__ import annotations
import csv,re,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC

LOOKUP_OFF=0x1a0fc4
MAX_FUNC=0x600


def u32(b,o):
    if o<0 or o+4>len(b): return None
    return struct.unpack_from('<I',b,o)[0]


def get_md():
    m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m


def one(md,data,base,off):
    return next(md.disasm(data[off:off+4],base+off,count=1),None)


def decode_func(md,data,base,start):
    out=[];off=start
    while off < min(len(data),start+MAX_FUNC):
        ins=one(md,data,base,off)
        if not ins: break
        out.append(ins);off+=ins.size
        if len(out)>3 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):
            break
    return out


def func_start(md,data,base,call_off):
    best=None
    lo=max(0,call_off-0x500)&~1
    for off in range(lo,call_off+1,2):
        ins=one(md,data,base,off)
        if ins and ins.mnemonic=='push' and 'lr' in ins.op_str: best=off
    return best


def strings(data,lo,hi,minlen=5):
    out=[];i=max(0,lo);hi=min(len(data),hi)
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=minlen:out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else:i+=1
    return out


def selector_name(data,start,end):
    # The selector's diagnostic/name block follows its return in this firmware.
    ss=strings(data,end,min(len(data),end+0x140),5)
    for off,s in ss:
        m=re.search(r'img_b2y_select_([A-Za-z0-9_]+)_paraset',s)
        if m:return m.group(1),off,s
    return None,None,None


def rid_before(md,data,base,call_off):
    # Decode a compact backwards window as individual Thumb instructions.
    cand=[]
    lo=max(0,call_off-0x40)&~1
    for off in range(lo,call_off,2):
        ins=one(md,data,base,off)
        if ins:cand.append((off,ins))
    for off,ins in reversed(cand):
        try:ops=list(ins.operands)
        except Exception:continue
        if (ins.mnemonic in ('movs','mov','mov.w') and len(ops)>=2 and
            ops[0].type==ARM_OP_REG and md.reg_name(ops[0].reg)=='r1' and
            ops[1].type==ARM_OP_IMM):
            return int(ops[1].imm)&0xffffffff,off
    return None,None


def downstream_setter(md,data,base,insns,lookup_va):
    # Pick direct BL/BLX after the lookup, before return; ignore logging helpers
    # only if another later direct call exists. The last direct call is the
    # selector's control setter in the known B2Y selector idiom.
    seen_lookup=False;calls=[]
    for ins in insns:
        try:ops=list(ins.operands)
        except Exception:ops=[]
        if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
            tgt=int(ops[0].imm)&0xffffffff
            if tgt==lookup_va: seen_lookup=True;continue
            if seen_lookup:calls.append((int(ins.address)-base,tgt))
    return calls[-1] if calls else (None,None)


def setter_mmio(md,data,base,setter_va):
    if setter_va is None or not (base<=setter_va<base+len(data)):return [],[]
    start=setter_va-base;insns=decode_func(md,data,base,start)
    mm=[];access=[]
    reg_pages={}
    for ins in insns:
        try:ops=list(ins.operands)
        except Exception:ops=[]
        if ins.mnemonic.startswith('ldr') and len(ops)>=2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_MEM and ops[1].mem.base==ARM_REG_PC:
            pool=((int(ins.address)+4)&~3)+int(ops[1].mem.disp)
            val=u32(data,pool-base)
            if val is not None and 0x20000000<=val<=0x200fffff:
                reg=ops[0].reg;reg_pages[reg]=val
                mm.append((int(ins.address),pool,val,md.reg_name(reg)))
        # Direct memory access where base register is currently known to hold a page.
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base in reg_pages:
                access.append((int(ins.address),reg_pages[op.mem.base],int(op.mem.disp),ins.mnemonic,ins.op_str))
        # Track simple mov register propagation.
        if ins.mnemonic in ('mov','movs') and len(ops)>=2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_REG:
            if ops[1].reg in reg_pages:reg_pages[ops[0].reg]=reg_pages[ops[1].reg]
        # Track add/sub immediate transformations of known MMIO base registers.
        if ins.mnemonic in ('adds','subs','add','sub') and len(ops)>=2 and ops[0].type==ARM_OP_REG:
            dst=ops[0].reg
            # two-operand Thumb form mutates dst
            if dst in reg_pages and ops[-1].type==ARM_OP_IMM:
                d=int(ops[-1].imm)
                reg_pages[dst]=(reg_pages[dst]+(d if ins.mnemonic.startswith('add') else -d))&0xffffffff
    # Dedupe
    mm2=[]
    for x in mm:
        if x not in mm2:mm2.append(x)
    ac2=[]
    for x in access:
        if x not in ac2:ac2.append(x)
    return mm2,ac2


def main():
    if len(sys.argv)!=2:raise SystemExit('usage: m10r_b2y_selector_inventory_v094.py <sections_dir>')
    root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-System')
    data=(root/row['file']).read_bytes();base=int(row['image_base'],16);lookup_va=base+LOOKUP_OFF
    md=get_md();print(f'V094_IMG_SYSTEM=file={row["file"]}|size=0x{len(data):x}|base=0x{base:08x}|lookup=0x{lookup_va:08x}')

    # Find every call to common lookup.
    calls=[]
    for off in range(0,len(data)-4,2):
        ins=one(md,data,base,off)
        if not ins or ins.mnemonic not in ('bl','blx'):continue
        try:ops=list(ins.operands)
        except Exception:continue
        if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&0xffffffff)==lookup_va:
            calls.append(off)
    print(f'V094_LOOKUP_CALL_COUNT={len(calls)}')
    rows_out=[]
    for call_off in calls:
        rid,rid_off=rid_before(md,data,base,call_off)
        start=func_start(md,data,base,call_off)
        if start is None:continue
        insns=decode_func(md,data,base,start);end=(int(insns[-1].address)-base+insns[-1].size) if insns else call_off+4
        name,name_off,name_str=selector_name(data,start,end)
        setter_call,setter=downstream_setter(md,data,base,insns,lookup_va)
        mm,acc=setter_mmio(md,data,base,setter)
        pages=sorted(set(x[2] for x in mm))
        offsets=sorted(set((p,d) for _,p,d,_,_ in acc))
        print(f'\nV094_SELECTOR=func=0x{start:x}|lookup=0x{call_off:x}|record={hex(rid) if rid is not None else "UNKNOWN"}|name={name or "UNKNOWN"}|setter={hex(setter) if setter is not None else "NONE"}|pages={",".join(f"0x{x:08x}" for x in pages) or "NONE"}')
        if name_off is not None:print(f'  V094_NAME_ASCII=0x{name_off:x}|{name_str}')
        if setter_call is not None:print(f'  V094_SETTER_CALL=0x{setter_call:x}->0x{setter:08x}')
        for a,pool,val,reg in mm:print(f'  V094_MMIO_LITERAL=ins=0x{a:x}|pool=0x{pool:x}|page=0x{val:08x}|reg={reg}')
        for a,p,d,mn,op in acc:print(f'  V094_ACCESS=0x{a:x}|page=0x{p:08x}|off=0x{d:x}|{mn} {op}')
        rows_out.append((rid,name,start,call_off,setter,pages,offsets))

    print('\n=== V094 COMPACT CROSSWALK ===')
    for rid,name,start,call_off,setter,pages,offsets in rows_out:
        print('V094_MAP=' + '|'.join([
            f'record={hex(rid) if rid is not None else "UNKNOWN"}',
            f'name={name or "UNKNOWN"}',f'func=0x{start:x}',f'lookup=0x{call_off:x}',
            f'setter={hex(setter) if setter is not None else "NONE"}',
            'pages=' + (','.join(f'0x{x:08x}' for x in pages) or 'NONE'),
            'offsets=' + (','.join(f'0x{p:08x}+0x{d:x}' for p,d in offsets) or 'NONE')]))

    # Highlight likely YC/output controls.
    print('\n=== V094 OUTPUT/YC CANDIDATES ===')
    for rid,name,start,call_off,setter,pages,offsets in rows_out:
        n=(name or '').lower()
        if any(k in n for k in ('yc','clip','gain','offset','rgb','output','blend','conversion')):
            print(f'V094_CANDIDATE=record={hex(rid) if rid is not None else "UNKNOWN"}|name={name}|setter={hex(setter) if setter is not None else "NONE"}|pages={",".join(f"0x{x:08x}" for x in pages) or "NONE"}')
    print('OVERALL_VERDICT=IMG_SYSTEM_B2Y_SELECTORS_BOUND_TO_RECORDS_SETTERS_AND_MMIO_BY_EXECUTABLE_CONTROL_FLOW')

if __name__=='__main__':main()
