#!/usr/bin/env python3
from __future__ import annotations
import csv, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

TARGET_TEXTS={
    'EDGE_GAIN':'        Edge Gain = %f',
    'EXTRACTED_CORING':'extracted coring: %d',
    'EXTRACTED_CORING_ZERO':'extracted coring: 0',
}

def load_section(sections,name):
    rows=list(csv.DictReader((sections/'sections.csv').open()))
    r=next(x for x in rows if x['name']==name)
    return (sections/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def u32(b,o): return struct.unpack_from('<I',b,o)[0]

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: m10r_edge_gain_coring_xref_v113.py <sections_dir>')
    sections=Path(sys.argv[1]); b,base,fn=load_section(sections,'IMG-System')
    print(f'V113_IMG_SYSTEM={fn}|base=0x{base:08x}|size=0x{len(b):x}')
    targets={}
    for label,text in TARGET_TEXTS.items():
        off=b.find(text.encode())
        if off<0:
            print(f'V113_TARGET_MISSING={label}|{text}')
            continue
        va=base+off; targets[label]=va
        print(f'V113_TARGET={label}|va=0x{va:08x}|text={text}')

    # First find exact little-endian pointers to each string. These are high-confidence
    # literal-pool/data references and make LDR-pool xref recovery cheap and exact.
    pool_to_label={}
    for label,va in targets.items():
        needle=struct.pack('<I',va)
        p=0; count=0
        while True:
            k=b.find(needle,p)
            if k<0: break
            poolva=base+k
            pool_to_label.setdefault(poolva,[]).append(label)
            print(f'V113_RAW_PTR={label}|pool=0x{poolva:08x}')
            count+=1; p=k+1
        print(f'V113_RAW_PTR_COUNT={label}|count={count}')

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True; md.skipdata=True
    xrefs=[]
    # Full linear Thumb sweep. Accept both LDR literal pools and multiple ADR operand
    # conventions because Capstone versions differ in whether ADR imm is exposed as
    # displacement or resolved address.
    for ins in md.disasm(b,base):
        try: ops=list(ins.operands)
        except Exception: ops=[]
        pc=(int(ins.address)+4)&~3
        hits=[]
        if ins.mnemonic.startswith('ldr'):
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pool=pc+int(op.mem.disp)
                    if pool in pool_to_label:
                        for label in pool_to_label[pool]: hits.append((label,'LDR_LITERAL',targets[label],pool))
        if ins.mnemonic.startswith('adr'):
            for op in ops:
                if op.type==ARM_OP_IMM:
                    imm=int(op.imm)&0xffffffff
                    candidates={imm,(pc+imm)&0xffffffff,(pc-imm)&0xffffffff}
                    for label,t in targets.items():
                        if t in candidates: hits.append((label,'ADR',t,None))
        for label,kind,t,pool in hits:
            rec=(label,int(ins.address),kind,t,pool)
            if rec not in xrefs: xrefs.append(rec)

    print(f'V113_XREF_COUNT={len(xrefs)}')
    for label,site,kind,t,pool in xrefs:
        print(f'\n=== V113_XREF {label} site=0x{site:08x} kind={kind} target=0x{t:08x} pool={"-" if pool is None else hex(pool)} ===')
        # Dump a generous window around each reference; start on an even Thumb boundary.
        a=max(base,(site-0x180)&~1); z=min(base+len(b),site+0x220)
        off=a-base
        for ins in md.disasm(b[off:off+(z-a)],a):
            ann=[]
            try: ops=list(ins.operands)
            except Exception: ops=[]
            if ins.mnemonic in ('bl','blx') and ops and ops[0].type==ARM_OP_IMM:
                ann.append('CALL=0x%08x'%(int(ops[0].imm)&0xffffffff))
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pp=((int(ins.address)+4)&~3)+int(op.mem.disp); po=pp-base
                    if 0<=po<=len(b)-4:
                        vv=u32(b,po); ann.append('LIT@0x%08x=0x%08x'%(pp,vv))
            mark='|XREF_SITE=1' if int(ins.address)==site else ''
            print(f'V113_INS={label}|0x{ins.address:08x}|{ins.mnemonic} {ins.op_str}{mark}'+(('|'+'|'.join(ann)) if ann else ''))

    # Also expose compact neighborhoods around raw pointer pools for manual inspection.
    print('\n=== V113_POINTER_POOL_NEIGHBORHOODS ===')
    for pool,labels in sorted(pool_to_label.items()):
        o=pool-base; a=max(0,o-32); z=min(len(b),o+36)
        print(f'V113_POOL={"+".join(labels)}|va=0x{pool:08x}|hex={b[a:z].hex()}')

    print('\nV113_GOAL=identify_runtime_sources_for_firmware_edge_gain_and_coring_debug_values')
    print('OVERALL_VERDICT=V113_EDGE_GAIN_CORING_XREFS_EXTRACTED')

if __name__=='__main__': main()
