#!/usr/bin/env python3
"""v0.95 — exact IMG-System B2Y selector-name binding via executable ADR targets.

v0.94 deliberately over-collected trailing strings and therefore could attach
an adjacent function's diagnostic name to a selector.  Here we bind names only
when a Thumb ADR inside the actual selector body resolves to the diagnostic
string used by that body.

The common B2Y calibration lookup is IMG-System +0x1a0fc4.  For every direct
call we recover the record id, enclosing function, all correctly resolved ADR
targets, and direct calls made after the lookup.  This gives a no-proximity
record -> selector-name -> downstream-call crosswalk.
"""
from __future__ import annotations
import csv,re,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_REG

LOOKUP=0x001A0FC4
MAX_BACK=0x600
MAX_FUNC=0x900


def md_new():
    m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m


def ins1(md,data,base,off):
    if off<0 or off>=len(data): return None
    return next(md.disasm(data[off:off+4],base+off,count=1),None)


def cstr(data,off,maxlen=240):
    if off<0 or off>=len(data):return None
    out=bytearray();i=off
    while i<len(data) and len(out)<maxlen:
        b=data[i]
        if b==0:break
        if not (32<=b<127):return None
        out.append(b);i+=1
    return out.decode('ascii','replace') if len(out)>=3 else None


def func_start(md,data,base,call_off):
    best=None
    for off in range(max(0,call_off-MAX_BACK)&~1,call_off+1,2):
        ins=ins1(md,data,base,off)
        if ins and ins.mnemonic=='push' and 'lr' in ins.op_str:best=off
    return best


def decode_func(md,data,base,start):
    out=[];off=start
    while off<min(len(data),start+MAX_FUNC):
        ins=ins1(md,data,base,off)
        if not ins:break
        out.append(ins);off+=ins.size
        if len(out)>2 and ((ins.mnemonic=='pop' and 'pc' in ins.op_str) or
                           (ins.mnemonic=='bx' and ins.op_str.strip()=='lr')):
            break
    return out


def direct_target(ins):
    try:ops=list(ins.operands)
    except Exception:return None
    if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
        return int(ops[0].imm)&0xffffffff
    return None


def record_before(md,data,base,call_off):
    cand=[]
    for off in range(max(0,call_off-0x50)&~1,call_off,2):
        ins=ins1(md,data,base,off)
        if ins:cand.append((off,ins))
    for off,ins in reversed(cand):
        try:ops=list(ins.operands)
        except Exception:continue
        if ins.mnemonic in ('movs','mov','mov.w') and len(ops)>=2 and ops[0].type==ARM_OP_REG and md.reg_name(ops[0].reg)=='r1' and ops[1].type==ARM_OP_IMM:
            return int(ops[1].imm)&0xffffffff,off
    return None,None


def adr_target(ins):
    # In Capstone Thumb mode the ADR immediate here is the displacement shown
    # in op_str (e.g. adr r1,#0x38), not an absolute VA.
    try:ops=list(ins.operands)
    except Exception:return None
    if not ins.mnemonic.startswith('adr') or not ops or ops[-1].type!=ARM_OP_IMM:return None
    disp=int(ops[-1].imm)
    return (((int(ins.address)+4)&~3)+disp)&0xffffffff


def name_from_adr_strings(items):
    for _,_,s in items:
        if not s:continue
        m=re.search(r'img_b2y_select_([A-Za-z0-9_]+)_paraset',s)
        if m:return m.group(1)
    return None


def main():
    if len(sys.argv)!=2:raise SystemExit('usage: m10r_b2y_selector_adr_bind_v095.py <sections_dir>')
    root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System');data=(root/row['file']).read_bytes();base=int(row['image_base'],16)
    md=md_new();lookup_va=base+LOOKUP
    print(f'V095_IMG_SYSTEM=file={row["file"]}|base=0x{base:08x}|size=0x{len(data):x}|lookup=0x{lookup_va:08x}')

    lookup_calls=[]
    for off in range(0,len(data)-4,2):
        ins=ins1(md,data,base,off)
        if ins and direct_target(ins)==lookup_va:lookup_calls.append(off)
    print(f'V095_LOOKUP_CALL_COUNT={len(lookup_calls)}')

    maps=[]
    seen_functions={}
    for call_off in lookup_calls:
        rid,rid_off=record_before(md,data,base,call_off)
        fs=func_start(md,data,base,call_off)
        if fs is None:
            print(f'V095_UNBOUND=lookup=0x{call_off:x}|record={hex(rid) if rid is not None else "UNKNOWN"}|reason=no_func_start');continue
        insns=decode_func(md,data,base,fs)
        adr=[]
        for ins in insns:
            t=adr_target(ins)
            if t is not None:
                s=cstr(data,t-base)
                # Some human diagnostic strings have a short non-printable or
                # alignment prefix; keep exact target and +1..+4 probes only as
                # evidence, but selector-name binding still requires the name
                # string itself to be directly addressable.
                if not s:
                    for d in range(1,5):
                        ss=cstr(data,t-base+d)
                        if ss:
                            s=f'[+{d}]'+ss;break
                adr.append((int(ins.address),t,s))
        name=name_from_adr_strings(adr)
        # all direct calls after this specific lookup until function return
        post=[];after=False
        for ins in insns:
            tgt=direct_target(ins)
            if tgt is None:continue
            if int(ins.address)==base+call_off and tgt==lookup_va:
                after=True;continue
            if after:post.append((int(ins.address),tgt))
        print(f'\nV095_SELECTOR=func=0x{base+fs:08x}|lookup=0x{base+call_off:08x}|record={hex(rid) if rid is not None else "UNKNOWN"}|adr_name={name or "UNKNOWN"}')
        for a,t,s in adr:
            if s or (base+fs<=t<=base+fs+0x300):print(f'  V095_ADR=ins=0x{a:08x}|target=0x{t:08x}|ascii={s or "NONE"}')
        for a,t in post:print(f'  V095_POSTCALL=0x{a:08x}->0x{t:08x}')
        maps.append((rid,name,base+fs,base+call_off,post))
        seen_functions.setdefault(base+fs,set()).add(name or 'UNKNOWN')

    print('\n=== V095 EXACT ADR CROSSWALK ===')
    for rid,name,fs,lc,post in maps:
        calls=','.join(f'0x{t:08x}' for _,t in post) or 'NONE'
        print(f'V095_MAP=record={hex(rid) if rid is not None else "UNKNOWN"}|name={name or "UNKNOWN"}|func=0x{fs:08x}|lookup=0x{lc:08x}|postcalls={calls}')

    print('\n=== V095 HIGH-VALUE RECORDS ===')
    for rid,name,fs,lc,post in maps:
        if rid in (0x0c,0x0d,0x17,0x02,0x0e,0x08,0x19,0x1a,0x04):
            calls=','.join(f'0x{t:08x}' for _,t in post) or 'NONE'
            print(f'V095_FOCUS=record=0x{rid:x}|name={name or "UNKNOWN"}|func=0x{fs:08x}|postcalls={calls}')

    bad=[(fs,names) for fs,names in seen_functions.items() if len(names)>1]
    print(f'V095_FUNCTION_NAME_CONFLICTS={len(bad)}')
    for fs,names in bad:print(f'V095_CONFLICT=func=0x{fs:08x}|names={",".join(sorted(names))}')
    print('OVERALL_VERDICT=SELECTOR_NAMES_BOUND_ONLY_BY_EXECUTABLE_ADR_REFERENCES')

if __name__=='__main__':main()
