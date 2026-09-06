#!/usr/bin/env python3
"""M10-R v0.56 surgical canonical-WB consumer probe.

Evidence anchor (already proven in archived research): central selector 0x42154F84
loads the B2Y runtime halfwords at local +0x04/+0x06/+0x08 into r0/r1/r2 and
calls 0x420D4380.  This probe does not rediscover speculative addresses.  It
inspects that exact callee, reports its bounded Thumb body and follows the three
incoming argument registers conservatively through simple register transfers,
arithmetic, stores and calls.

No renderer/application files are touched.
"""
from __future__ import annotations

from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC

TARGET = 0x420D4380
WINDOW = 0x280


def load_sections(root: Path):
    rows = list(csv.DictReader((root / 'sections.csv').open(encoding='utf-8')))
    out=[]
    for row in rows:
        base=int(row['image_base'],16)
        p=root/row['file']
        data=p.read_bytes()
        if base and base <= TARGET < base+len(data):
            out.append((row,base,data))
    return out


def rn(md, rid):
    return md.reg_name(rid) if rid else None


def op_regs(ins, md):
    try:
        rd,wr=ins.regs_access()
        return ({rn(md,x) for x in rd if rn(md,x)}, {rn(md,x) for x in wr if rn(md,x)})
    except Exception:
        return set(),set()


def literal_value(ins, op, data, base):
    if op.type != ARM_OP_MEM:
        return None
    mem=op.mem
    if mem.base != ARM_REG_PC:
        return None
    addr=((ins.address+4)&~3)+int(mem.disp)
    off=addr-base
    if 0 <= off <= len(data)-4:
        return addr, struct.unpack_from('<I',data,off)[0]
    return None


def main():
    if len(sys.argv)!=2:
        raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1])
    matches=load_sections(root)
    print('V056_ANCHOR=0x42154f84:local+04/+06/+08->r0/r1/r2->0x420d4380')
    print('V056_CALLEE=0x420d4380')
    print(f'V056_MATCHING_SECTIONS={len(matches)}')
    if len(matches)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_SECTION_MAPPING')
        return 0
    row,base,data=matches[0]
    off=TARGET-base
    print(f"V056_SECTION={row['index']}:{row['name']}")
    print(f'V056_SECTION_BASE=0x{base:08x}')
    print(f'V056_CALLEE_OFFSET=0x{off:x}')

    md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
    md.detail=True
    code=data[off:off+WINDOW]
    taint={'r0':{'R'},'r1':{'G'},'r2':{'B'}}
    stores=[]; calls=[]; literals=[]; taint_ops=[]
    insn_count=0
    return_seen=False

    print('=== V056_CALLEE_BODY ===')
    for ins in md.disasm(code,TARGET):
        insn_count += 1
        txt=f'{ins.address:08x}: {ins.mnemonic:<10} {ins.op_str}'.rstrip()
        print(txt)
        if ins.id==0:
            taint.clear(); continue
        try: ops=list(ins.operands)
        except Exception: ops=[]
        reads,writes=op_regs(ins,md)
        used=set()
        for r in reads:
            used |= taint.get(r,set())

        # literal pool reporting
        for op in ops:
            lv=literal_value(ins,op,data,base)
            if lv:
                addr,val=lv; literals.append((ins.address,addr,val))
                print(f'  V056_LITERAL@0x{ins.address:08x}=0x{val:08x} pool=0x{addr:08x}')

        mn=ins.mnemonic.lower()
        if used:
            taint_ops.append((ins.address,mn,ins.op_str,sorted(used)))
            print(f"  V056_TAINT_USE labels={','.join(sorted(used))}")

        # Stores: operand 0 is stored value; report taint and address form.
        if mn.startswith('str') and ops:
            src_labels=set()
            if ops[0].type==ARM_OP_REG:
                src_labels |= taint.get(rn(md,ops[0].reg),set())
            stores.append((ins.address,ins.op_str,sorted(src_labels)))
            print(f"  V056_STORE labels={','.join(sorted(src_labels)) or '-'} op='{ins.op_str}'")

        # Calls: ARM AAPCS argument registers are r0-r3. Report exact live taint.
        if mn in ('bl','blx'):
            argmap={r:sorted(taint.get(r,set())) for r in ('r0','r1','r2','r3') if taint.get(r)}
            calls.append((ins.address,ins.op_str,argmap))
            print(f'  V056_CALL_TAINT={argmap}')
            # conservative boundary: call may clobber r0-r3; preserve callee-saved only.
            for r in ('r0','r1','r2','r3','r12','lr'):
                taint.pop(r,None)
        else:
            # Simple transfer propagation using Capstone read/write sets.
            src_labels=set()
            for r in reads:
                src_labels |= taint.get(r,set())
            for w in writes:
                taint.pop(w,None)
            if src_labels and len(writes)==1 and not mn.startswith(('cmp','tst','str','push')):
                w=next(iter(writes)); taint[w]=set(src_labels)

        if mn=='bx' and 'lr' in ins.op_str:
            return_seen=True; break
        if mn=='pop' and 'pc' in ins.op_str:
            return_seen=True; break
        if insn_count>=220:
            break

    print('=== V056_SUMMARY ===')
    print(f'V056_INSNS={insn_count}')
    print(f'V056_RETURN_SEEN={int(return_seen)}')
    print(f'V056_TAINT_OPS={len(taint_ops)}')
    print(f'V056_STORES={len(stores)}')
    print(f'V056_CALLS={len(calls)}')
    print(f'V056_LITERALS={len(literals)}')
    labeled_stores=[x for x in stores if x[2]]
    tainted_calls=[x for x in calls if x[2]]
    print(f'V056_TAINTED_STORES={len(labeled_stores)}')
    print(f'V056_TAINTED_CALLS={len(tainted_calls)}')
    for a,op,labs in labeled_stores:
        print(f"V056_TAINTED_STORE=0x{a:08x}|{','.join(labs)}|{op}")
    for a,op,argmap in tainted_calls:
        print(f'V056_TAINTED_CALL=0x{a:08x}|{op}|{argmap}')
    # Do not infer pixel semantics from a write alone.  This first pass only
    # resolves whether the canonical WB triplet demonstrably leaves the helper.
    if labeled_stores:
        print('OVERALL_VERDICT=CANONICAL_WB_REACHES_STORE_NEEDS_TARGET_CLASSIFICATION')
    elif tainted_calls:
        print('OVERALL_VERDICT=CANONICAL_WB_ESCAPES_TO_CALLEE_UNRESOLVED')
    elif return_seen:
        print('OVERALL_VERDICT=NO_OUTWARD_CANONICAL_WB_CONSUMER_IN_HELPER')
    else:
        print('OVERALL_VERDICT=UNRESOLVED')

if __name__=='__main__':
    main()
