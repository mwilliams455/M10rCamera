#!/usr/bin/env python3
"""v0.74 map the B2Y parameter orchestrator to selector record IDs and names.

Evidence rules:
- Orchestrator is the v067-proven function at IMG-System +0x154f88.
- Only direct BL/BLX targets inside the local B2Y selector cluster are mapped.
- A target is assigned a calibration record ID only if its own body directly
  calls the proven common lookup 0x421a0fc4 and an explicit r1 immediate is
  present in the immediately preceding instructions.
- Diagnostic names are taken only from ASCII strings whose address is produced
  by an ADR/PC-relative literal inside that same target body. Nearby strings by
  address alone are reported separately and never used as the primary label.

Configuration call order is NOT asserted to equal hardware pixel-flow order.
"""
from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

BASE=0x42000000
ORCH=0x154f88
LOOKUP=0x421a0fc4
CLUSTER_LO=0x153000
CLUSTER_HI=0x155400


def md_thumb():
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True;return md

def u32(data,o): return struct.unpack_from('<I',data,o)[0] if 0<=o<=len(data)-4 else None

def body(md,data,start,span=0x500):
    out=[]
    for ins in md.disasm(data[start:min(len(data),start+span)],BASE+start):
        out.append(ins);off=ins.address-BASE;m=ins.mnemonic.lower()
        if off>start+2 and ((m=='pop' and 'pc' in ins.op_str.lower()) or (m=='bx' and 'lr' in ins.op_str.lower())):break
    return out

def direct_target(ins):
    if not ins.mnemonic.lower().startswith('bl'): return None
    try:op=ins.operands[0]
    except Exception:return None
    return int(op.imm) if op.type==ARM_OP_IMM else None

def mov_r1_imm(ins):
    if not ins.mnemonic.lower().startswith('mov'):return None
    try:ops=list(ins.operands)
    except Exception:return None
    if len(ops)!=2 or ops[1].type!=ARM_OP_IMM:return None
    if not ins.op_str.lower().replace(' ','').startswith('r1,'):return None
    return int(ops[1].imm)

def pc_literal(ins,data):
    try:ops=list(ins.operands)
    except Exception:return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            po=(((ins.address+4)&~3)+int(op.mem.disp))-BASE
            if 0<=po<=len(data)-4:return po,u32(data,po)
    return None

def ascii_at(data,off,maxlen=160):
    if not (0<=off<len(data)) or not (32<=data[off]<127):return None
    j=off
    while j<min(len(data),off+maxlen) and 32<=data[j]<127:j+=1
    if j-off<4:return None
    return data[off:j].decode('ascii','replace')

def referenced_ascii(ins,data):
    out=[]
    m=ins.mnemonic.lower()
    # Capstone resolves ADR destination as absolute immediate on Thumb.
    if m.startswith('adr'):
        try:ops=list(ins.operands)
        except Exception:ops=[]
        for op in ops:
            if op.type==ARM_OP_IMM:
                va=int(op.imm);off=va-BASE
                s=ascii_at(data,off)
                if s:out.append((off,s,'ADR'))
    lit=pc_literal(ins,data)
    if lit:
        po,val=lit
        if BASE<=val<BASE+len(data):
            s=ascii_at(data,val-BASE)
            if s:out.append((val-BASE,s,'LDR_LITERAL'))
    return out

def selector_info(md,data,start):
    insns=body(md,data,start,0x240)
    lookup_hits=[];refs=[]
    for idx,ins in enumerate(insns):
        refs.extend(referenced_ascii(ins,data))
        if direct_target(ins)==LOOKUP:
            rid=None;src=None
            for q in reversed(insns[max(0,idx-12):idx]):
                x=mov_r1_imm(q)
                if x is not None:
                    rid=x;src=q.address-BASE;break
            lookup_hits.append((ins.address-BASE,rid,src))
    # Keep only likely diagnostic/configuration strings actually referenced.
    good=[];seen=set()
    for off,s,kind in refs:
        if (off,s) in seen:continue
        seen.add((off,s))
        low=s.lower()
        if any(k in low for k in ('b2y','tone','blend','clip','conversion','string:%s','paras','gamma','offset','shift','edge','color','interpol','texture','filter','light')):
            good.append((off,s,kind))
    return insns,lookup_hits,good

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: script <sections_dir>')
    sec=Path(sys.argv[1]);rows=list(csv.DictReader((sec/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System');data=(sec/row['file']).read_bytes();md=md_thumb()
    orch=body(md,data,ORCH,0x600)
    print(f'V074_ORCHESTRATOR=off=0x{ORCH:x}|va=0x{BASE+ORCH:08x}|ins={len(orch)}')
    seq=[]
    for ins in orch:
        va=direct_target(ins)
        if va is None:continue
        off=va-BASE
        if CLUSTER_LO<=off<CLUSTER_HI:
            seq.append((ins.address-BASE,off,va))
    print(f'V074_CLUSTER_CALL_COUNT={len(seq)}')
    for order,(frm,to,va) in enumerate(seq):
        insns,hits,refs=selector_info(md,data,to)
        print(f'\nV074_CALL=order={order}|from=0x{frm:x}|target=0x{to:x}|va=0x{va:08x}|selector_ins={len(insns)}')
        if hits:
            for calloff,rid,src in hits:
                print(f'V074_LOOKUP=target=0x{to:x}|call=0x{calloff:x}|record_id={"-" if rid is None else hex(rid)}|r1_source={"-" if src is None else hex(src)}')
        else:
            print(f'V074_LOOKUP=target=0x{to:x}|NONE')
        for ro,s,kind in refs:
            print(f'V074_REF_STRING=target=0x{to:x}|off=0x{ro:x}|kind={kind}|text={s}')
    # Compact ordered record-ID chain for direct comparison with renderer hypotheses.
    print('\n=== V074 ORDERED RECORD-ID CHAIN ===')
    for order,(frm,to,va) in enumerate(seq):
        _,hits,refs=selector_info(md,data,to)
        ids=','.join(hex(h[1]) for h in hits if h[1] is not None) or '-'
        names=' || '.join(s for _,s,_ in refs) or '-'
        print(f'V074_CHAIN=order={order}|from=0x{frm:x}|target=0x{to:x}|ids={ids}|refs={names}')
    print('\nINTERPRETATION_BOUNDARY=CONFIGURATION_CALL_ORDER_IS_NOT_HARDWARE_PIXEL_FLOW_ORDER')
    print('OVERALL_VERDICT=ORCHESTRATOR_SELECTOR_RECORD_IDS_AND_REFERENCED_NAMES_MAPPED')
if __name__=='__main__':main()
