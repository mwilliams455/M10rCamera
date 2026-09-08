#!/usr/bin/env python3
"""v1.00 — decode OFFSET/TONE/DG downstream targets in ARM state.

v0.99 showed ARM prologue bytes at targets previously decoded as Thumb.  This
probe disassembles the proven BLX destinations as ARM, walks intra-function
branches, resolves ARM PC-relative literal loads (PC=address+8), and reports
MMIO pages/call targets.  Goal: constrain tone/DG hardware placement without
blocking the first Android render build.
"""
from __future__ import annotations
import csv, struct, sys
from collections import deque
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

ROOTS = {
    0x000D3284: 'OFFSET_record_0x02',
    0x000D3C20: 'TONE_records_0x08_0x19_0x1A',
    0x000D15EC: 'DG_record_0x0B',
    0x000D164C: 'DG_record_0x1C',
    0x000D1694: 'DG_record_0x1D',
}
MAX_NODES = 500
FUNC_WINDOW = 0x1200

def u32(data, off):
    return struct.unpack_from('<I', data, off)[0] if 0 <= off <= len(data)-4 else None

def is_conditional_branch(mn):
    if mn in ('b','bl','blx','bx','bxj'): return False
    return mn.startswith('b') and mn not in ('bic','bics')

def literal_target(ins):
    try: ops=list(ins.operands)
    except Exception: return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            return ((int(ins.address)+8)&~3)+int(op.mem.disp)
    return None

def imm_target(ins):
    try: ops=list(ins.operands)
    except Exception: return None
    for op in ops:
        if op.type==ARM_OP_IMM: return int(op.imm)&0xffffffff
    return None

def cfg(data, start):
    md=Cs(CS_ARCH_ARM, CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN); md.detail=True
    q=deque([start]); seen=set(); insns={}
    lo=start; hi=min(len(data), start+FUNC_WINDOW)
    while q and len(insns)<MAX_NODES:
        pc=q.popleft()&~3
        while lo <= pc < hi and pc not in seen and len(insns)<MAX_NODES:
            seen.add(pc)
            ins=next(md.disasm(data[pc:pc+4], pc, count=1), None)
            if not ins or ins.size!=4: break
            insns[pc]=ins
            mn=ins.mnemonic
            tgt=imm_target(ins)
            if mn in ('b',) and tgt is not None:
                if lo <= tgt < hi: q.append(tgt)
                break
            if is_conditional_branch(mn) and tgt is not None:
                if lo <= tgt < hi: q.append(tgt)
                pc += 4; continue
            if mn in ('bx','bxj') and ins.op_str.strip()=='lr': break
            if mn.startswith('pop') and 'pc' in ins.op_str: break
            if mn in ('mov','movs') and ins.op_str.replace(' ','') in ('pc,lr','pc,r14'): break
            pc += 4
    return [insns[k] for k in sorted(insns)]

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: ... <sections_dir>')
    root=Path(sys.argv[1])
    rows=list(csv.DictReader((root/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System')
    data=(root/row['file']).read_bytes()
    print(f'V100_IMG_SYSTEM=file={row["file"]}|size=0x{len(data):x}|mode=ARM')
    global_pages=set()
    for start,name in ROOTS.items():
        insns=cfg(data,start)
        pages=set(); calls=[]; literals=[]
        print(f'\n=== V100 {name} start=0x{start:08x} nodes={len(insns)} ===')
        print(f'V100_ROOT_BYTES={data[start:start+32].hex()}')
        for ins in insns:
            print(f'V100_INS=0x{ins.address:08x}|{ins.bytes.hex()}|{ins.mnemonic} {ins.op_str}')
            lit=literal_target(ins)
            if lit is not None:
                val=u32(data,lit)
                literals.append((ins.address,lit,val))
                print(f'  V100_LITERAL=code=0x{ins.address:08x}|pool=0x{lit:08x}|value={"NONE" if val is None else f"0x{val:08x}"}')
                if val is not None and 0x20000000 <= val <= 0x200fffff:
                    page=val & 0xfffff000; pages.add(page); global_pages.add(page)
                    print(f'  V100_MMIO=code=0x{ins.address:08x}|value=0x{val:08x}|page=0x{page:08x}')
            if ins.mnemonic in ('bl','blx'):
                tgt=imm_target(ins)
                if tgt is not None:
                    calls.append((ins.address,tgt,ins.mnemonic))
                    print(f'  V100_CALL=0x{ins.address:08x}->{tgt:#010x}|{ins.mnemonic}')
        print(f'V100_ROOT_SUMMARY={name}|start=0x{start:08x}|nodes={len(insns)}|calls={len(calls)}|mmio={",".join(f"0x{x:08x}" for x in sorted(pages)) if pages else "NONE"}')
    print(f'\nV100_GLOBAL_MMIO={",".join(f"0x{x:08x}" for x in sorted(global_pages)) if global_pages else "NONE"}')
    print('OVERALL_VERDICT=OFFSET_TONE_DG_TARGETS_REDECODED_IN_PROVEN_ARM_STATE')

if __name__=='__main__': main()
