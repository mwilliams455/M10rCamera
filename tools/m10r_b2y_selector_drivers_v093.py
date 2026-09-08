#!/usr/bin/env python3
"""v0.93: trace the three high-value B2Y selector downstream wrappers.

Roots proven by v0.92:
  record 0x0d / Y BLEND      -> 0x000d4480
  record 0x0c / YC CONVERSION -> 0x000d4570
  record 0x17 / unknown      -> 0x000d34f0

For each root, dump a bounded Thumb function, recurse through direct BL/BLX
calls, resolve PC-relative literal loads/ADR targets, and flag printable
strings plus 0x2002xxxx MMIO-looking constants. Also dump the selector-local
post-return data/string region so record 0x17 can be named from executable
ADR targets rather than nearest-string proximity.
"""
from __future__ import annotations
import csv, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

ROOTS = {
    0x000D4480: "record_0x0d_Y_BLEND",
    0x000D4570: "record_0x0c_YC_CONVERSION",
    0x000D34F0: "record_0x17_UNKNOWN",
}
SELECTORS = {
    0x00154E18: "record_0x0d_selector",
    0x00154ECC: "record_0x0c_selector",
    0x0015486C: "record_0x17_selector",
}
MAX_FUNC_BYTES = 0x300
MAX_DEPTH = 3
MAX_FUNCS_PER_ROOT = 80


def printable_at(data: bytes, off: int, maxlen: int = 220) -> str | None:
    if off < 0 or off >= len(data):
        return None
    j = off
    out = bytearray()
    while j < len(data) and len(out) < maxlen:
        b = data[j]
        if b == 0:
            break
        if not (32 <= b < 127):
            return None
        out.append(b); j += 1
    return out.decode('ascii', 'replace') if len(out) >= 4 else None


def strings(data: bytes, lo: int, hi: int, minlen: int = 4):
    out=[]; i=max(0,lo); hi=min(len(data),hi)
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127: j+=1
            if j-i>=minlen: out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else: i+=1
    return out


def u32(data: bytes, off: int):
    if off < 0 or off+4 > len(data): return None
    return struct.unpack_from('<I', data, off)[0]


def decode_func(md, data: bytes, base: int, va: int):
    off = va-base
    if off < 0 or off >= len(data): return []
    insns=[]
    for ins in md.disasm(data[off:off+MAX_FUNC_BYTES], va):
        insns.append(ins)
        # Return terminators. Avoid treating conditional data after return as code.
        if len(insns) >= 3 and ((ins.mnemonic == 'pop' and 'pc' in ins.op_str) or
                                (ins.mnemonic in ('bx','bxj') and ins.op_str.strip() == 'lr')):
            break
    return insns


def pc_target(ins, disp: int) -> int:
    return ((int(ins.address)+4) & ~3) + int(disp)


def analyze_one(md, data, base, va, label, depth):
    insns=decode_func(md,data,base,va)
    print(f'V093_FUNC=0x{va:08x}|label={label}|depth={depth}|insns={len(insns)}')
    calls=[]
    for ins in insns:
        print(f'  V093_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')
        try: ops=list(ins.operands)
        except Exception: ops=[]
        if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
            tgt=int(ops[0].imm)&0xffffffff
            calls.append(tgt)
            print(f'  V093_CALL=0x{ins.address:08x}->0x{tgt:08x}')
        # Resolve LDR literal pool references.
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                lit=pc_target(ins,op.mem.disp); loff=lit-base; val=u32(data,loff)
                extra=''
                if val is not None:
                    s=printable_at(data,val-base)
                    if s: extra=f'|ptr_ascii={s}'
                    if 0x20000000 <= val <= 0x2003ffff: extra+=f'|MMIO_CANDIDATE=0x{val:08x}'
                print(f'  V093_LITERAL=ins=0x{ins.address:08x}|pool=0x{lit:08x}|value={"NONE" if val is None else f"0x{val:08x}"}{extra}')
        # Resolve ADR immediates as code/data targets.
        if ins.mnemonic.startswith('adr') and ops and ops[-1].type==ARM_OP_IMM:
            tgt=int(ops[-1].imm)&0xffffffff
            s=printable_at(data,tgt-base)
            print(f'  V093_ADR=ins=0x{ins.address:08x}|target=0x{tgt:08x}|ascii={s or "NONE"}')
        # Flag direct immediates in MMIO range.
        for op in ops:
            if op.type==ARM_OP_IMM:
                val=int(op.imm)&0xffffffff
                if 0x20000000 <= val <= 0x2003ffff:
                    print(f'  V093_MMIO_IMM=ins=0x{ins.address:08x}|value=0x{val:08x}')
    return calls


def selector_context(md,data,base,va,label):
    print(f'\n=== V093_SELECTOR_CONTEXT {label} @ 0x{va:08x} ===')
    insns=decode_func(md,data,base,va)
    for ins in insns:
        print(f'  V093_SEL_INS=0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}')
        try: ops=list(ins.operands)
        except Exception: ops=[]
        if ins.mnemonic.startswith('adr') and ops and ops[-1].type==ARM_OP_IMM:
            tgt=int(ops[-1].imm)&0xffffffff
            s=printable_at(data,tgt-base)
            print(f'  V093_SEL_ADR=ins=0x{ins.address:08x}|target=0x{tgt:08x}|ascii={s or "NONE"}')
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                lit=pc_target(ins,op.mem.disp); val=u32(data,lit-base)
                s=printable_at(data,(val-base) if val is not None else -1)
                print(f'  V093_SEL_LITERAL=ins=0x{ins.address:08x}|pool=0x{lit:08x}|value={"NONE" if val is None else f"0x{val:08x}"}|ptr_ascii={s or "NONE"}')
    # Raw local strings including ones omitted by v0.92 keyword filtering.
    off=va-base
    for so,s in strings(data,off-0x80,off+0x180):
        print(f'  V093_SEL_ASCII=0x{base+so:08x}|{s}')


def main():
    if len(sys.argv)!=2: raise SystemExit('usage: m10r_b2y_selector_drivers_v093.py <sections_dir>')
    root=Path(sys.argv[1]); rows=list(csv.DictReader((root/'sections.csv').open()))
    row=next(r for r in rows if r['name']=='IMG-System')
    data=(root/row['file']).read_bytes(); base=int(row['image_base'],16)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    print(f'V093_IMG_SYSTEM=file={row["file"]}|size=0x{len(data):x}|base=0x{base:08x}')

    for sva,label in SELECTORS.items(): selector_context(md,data,base,sva,label)

    all_root_calls={}
    for root_va,root_label in ROOTS.items():
        print(f'\n=== V093_CALLTREE {root_label} ===')
        q=[(root_va,root_label,0)]; visited=set(); order=[]
        while q and len(visited)<MAX_FUNCS_PER_ROOT:
            va,label,depth=q.pop(0)
            if va in visited or not (base <= va < base+len(data)): continue
            visited.add(va); order.append(va)
            calls=analyze_one(md,data,base,va,label,depth)
            if depth < MAX_DEPTH:
                for c in calls:
                    if base <= c < base+len(data) and c not in visited:
                        q.append((c,f'callee_of_0x{va:08x}',depth+1))
        all_root_calls[root_va]=order
        print(f'V093_TREE_SUMMARY=root=0x{root_va:08x}|functions={len(order)}|nodes={",".join(f"0x{x:08x}" for x in order)}')

    # Search all literal pool words in the local root/callee neighborhoods for 0x2002xxxx.
    print('\n=== V093_MMIO_NEIGHBORHOOD_SCAN ===')
    seen=set()
    for nodes in all_root_calls.values():
        for va in nodes:
            off=va-base
            lo=max(0,off-0x20); hi=min(len(data),off+MAX_FUNC_BYTES)
            for p in range((lo+3)&~3,hi-3,4):
                val=u32(data,p)
                if val is not None and 0x20020000 <= val <= 0x2002ffff:
                    key=(p,val)
                    if key not in seen:
                        seen.add(key); print(f'V093_MMIO_WORD=at=0x{base+p:08x}|value=0x{val:08x}')

    print('OVERALL_VERDICT=V093_SELECTOR_NAMES_AND_DOWNSTREAM_WRAPPER_CALLTREES_EXTRACTED')

if __name__=='__main__': main()
