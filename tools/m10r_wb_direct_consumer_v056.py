#!/usr/bin/env python3
"""M10-R v0.56 canonical WB -> B2Y hardware gain proof.

Proven archived anchor: central selector 0x42154F84 loads the B2Y runtime
halfwords local +0x04/+0x06/+0x08 into r0/r1/r2 and calls 0x420D4380.

This revision closes the software/hardware boundary.  The helper is mapped back
into IMG-System only after two independent archived string anchors yield the
same virtual-address/file-offset bias.  It then verifies the exact register
packing performed by 0x420D4380:

  r0 = R, r1 = G, r2 = B
  0x2002008c bits 10:0  <- R[10:0]
  0x2002008c bits 26:16 <- B[10:0]
  0x20020090 bits 10:0  <- G[10:0]
  0x20020090 bits 26:16 <- G[10:0]

The helper compares each input against 0x800 before programming, matching the
11-bit field width.  Canonical upstream WB gains are separately proven/clamped
to [1,2000], so they fit this ABI without reinterpretation.

No renderer/application files are touched.
"""
from __future__ import annotations

from pathlib import Path
import csv, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

TARGET = 0x420D4380
WINDOW = 0x120
STRING_ANCHORS = [
    (0x420A40AF, b'Gain R: %4.f | G: %4.f | B: %4.f'),
    (0x421E9CCD, b'ca9_cm_ColorManagementFinished'),
]
MMIO_BASE = 0x20020080
REG_RB = MMIO_BASE + 0x0C
REG_GG = MMIO_BASE + 0x10
UPPER_MASK = 0x07FF0000
LOWER_MASK = 0x000007FF


def get_img_section(root: Path):
    rows=list(csv.DictReader((root/'sections.csv').open(encoding='utf-8')))
    return [(r,(root/r['file']).read_bytes()) for r in rows if r['name']=='IMG-System']


def derive_mapping(data: bytes):
    evidence=[]
    for va,needle in STRING_ANCHORS:
        poss=[]; start=0
        while True:
            p=data.find(needle,start)
            if p<0: break
            poss.append(p); start=p+1
        evidence.append((va,needle,poss))
    if any(len(x[2])!=1 for x in evidence): return evidence,None
    biases=[va-poss[0] for va,_,poss in evidence]
    return evidence,(biases[0] if len(set(biases))==1 else None)


def u32(data: bytes, off: int):
    return struct.unpack_from('<I',data,off)[0] if 0<=off<=len(data)-4 else None


def read_cstr_va(data: bytes,bias:int,va:int,limit=256):
    off=va-bias
    if not (0<=off<len(data)): return None
    end=data.find(b'\0',off,min(len(data),off+limit))
    if end<0: end=min(len(data),off+limit)
    raw=data[off:end]
    try:
        s=raw.decode('ascii')
    except UnicodeDecodeError:
        return None
    return s if s and all((32<=ord(c)<127) or c in '\t\r\n' for c in s) else None


def literal_from_ins(ins,data,bias):
    out=[]
    try: ops=list(ins.operands)
    except Exception: return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            va=((ins.address+4)&~3)+int(op.mem.disp)
            val=u32(data,va-bias)
            if val is not None: out.append((va,val))
    return out


def adr_target(ins):
    if ins.mnemonic.lower()!='adr': return None
    # Capstone renders Thumb ADR immediate as displacement from aligned PC.
    parts=ins.op_str.split('#')
    if len(parts)!=2: return None
    try: imm=int(parts[1],0)
    except ValueError: return None
    return ((ins.address+4)&~3)+imm


def main():
    if len(sys.argv)!=2: raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); imgs=get_img_section(root)
    print('V056_ANCHOR=0x42154f84:local+04/+06/+08->r0/r1/r2->0x420d4380')
    print('V056_ARGUMENT_ABI=r0:R|r1:G|r2:B')
    print(f'V056_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG_SECTION'); return 0
    row,data=imgs[0]
    print(f"V056_SECTION={row['index']}:{row['name']}")
    evidence,bias=derive_mapping(data)
    for va,needle,poss in evidence:
        print(f"V056_MAP_ANCHOR=0x{va:08x}|{needle.decode('ascii')}|hits={len(poss)}|offsets={','.join(hex(x) for x in poss) or '-'}")
        for p in poss: print(f'V056_MAP_BIAS_CANDIDATE=0x{va-p:08x}')
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_ARCHIVE_TO_FILE_MAPPING'); return 0
    off=TARGET-bias
    print(f'V056_MAP_BIAS=0x{bias:08x}')
    print(f'V056_CALLEE_FILE_OFFSET=0x{off:x}')
    if not (0<=off<len(data)):
        print('OVERALL_VERDICT=UNRESOLVED_CALLEE_OFFSET'); return 0

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True
    insns=[]; literals=[]; adrs=[]
    for ins in md.disasm(data[off:off+WINDOW],TARGET):
        insns.append(ins)
        print(f'{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}'.rstrip())
        for pool,val in literal_from_ins(ins,data,bias):
            literals.append((ins.address,pool,val))
            print(f'  V056_LITERAL=0x{ins.address:08x}|pool=0x{pool:08x}|value=0x{val:08x}')
        at=adr_target(ins)
        if at is not None:
            s=read_cstr_va(data,bias,at)
            adrs.append((ins.address,at,s))
            print(f"  V056_ADR=0x{ins.address:08x}|target=0x{at:08x}|ascii={s!r}")
        if ins.mnemonic.lower()=='pop' and 'pc' in ins.op_str: break

    by={i.address:(i.mnemonic.lower(),i.op_str.lower().replace(' ','')) for i in insns}
    litvals={a:v for a,_,v in literals}

    checks=[]
    def ck(name,cond,detail):
        checks.append((name,bool(cond),detail)); print(f"V056_CHECK={name}|{'PASS' if cond else 'FAIL'}|{detail}")

    ck('arg_R_to_r5', by.get(0x420D4382)==('movs','r5,r0'), str(by.get(0x420D4382)))
    ck('arg_G_to_r4', by.get(0x420D4384)==('movs','r4,r1'), str(by.get(0x420D4384)))
    ck('arg_B_to_r6', by.get(0x420D4386)==('movs','r6,r2'), str(by.get(0x420D4386)))
    ck('threshold_2048', by.get(0x420D439C)==('movs','r0,#1') and by.get(0x420D439E)==('lsls','r0,r0,#0xb'), '0x800')
    ck('mmio_literal', litvals.get(0x420D43B4)==MMIO_BASE, f"0x{litvals.get(0x420D43B4,0):08x}")
    ck('upper_clear_mask_literal', litvals.get(0x420D43B8)==0xF800FFFF, f"0x{litvals.get(0x420D43B8,0):08x}")

    # G upper 11 bits -> +0x10.
    ck('G_upper_shift', by.get(0x420D43BC)==('lsls','r1,r4,#0x10'), str(by.get(0x420D43BC)))
    ck('G_upper_store', by.get(0x420D43C8)==('str','r0,[r1,#0x10]'), str(by.get(0x420D43C8)))
    # G lower 11 bits -> +0x10.
    ck('G_lower_extract', by.get(0x420D43D2)==('lsls','r1,r4,#0x15') and by.get(0x420D43D4)==('lsrs','r1,r1,#0x15'), 'G & 0x7ff')
    ck('G_lower_store', by.get(0x420D43DA)==('str','r0,[r1,#0x10]'), str(by.get(0x420D43DA)))
    # R lower 11 bits -> +0x0c.
    ck('R_lower_extract', by.get(0x420D43E4)==('lsls','r1,r5,#0x15') and by.get(0x420D43E6)==('lsrs','r1,r1,#0x15'), 'R & 0x7ff')
    ck('R_lower_store', by.get(0x420D43EC)==('str','r0,[r1,#0xc]'), str(by.get(0x420D43EC)))
    # B upper 11 bits -> +0x0c.
    ck('B_upper_shift', by.get(0x420D43F6)==('lsls','r1,r6,#0x10'), str(by.get(0x420D43F6)))
    ck('B_upper_store', by.get(0x420D43FE)==('str','r0,[r1,#0xc]'), str(by.get(0x420D43FE)))

    print(f'V056_REGISTER_RB=0x{REG_RB:08x}|bits10_0=R10_0|bits26_16=B10_0')
    print(f'V056_REGISTER_GG=0x{REG_GG:08x}|bits10_0=G10_0|bits26_16=G10_0')
    print(f'V056_FIELD_MASK_LOWER=0x{LOWER_MASK:08x}')
    print(f'V056_FIELD_MASK_UPPER=0x{UPPER_MASK:08x}')
    print('V056_HARDWARE_CHANNEL_VECTOR=R,G,G,B')
    print('V056_CANONICAL_GAIN_RANGE=1..2000')
    print('V056_HARDWARE_EXCLUSIVE_CEILING=2048')
    print('V056_RANGE_FITS_11BIT_ABI=1')
    print(f'V056_CHECKS={sum(x[1] for x in checks)}/{len(checks)}')

    if checks and all(x[1] for x in checks):
        print('OVERALL_VERDICT=DIRECT_WB_GAIN_HARDWARE_PROGRAMMER_PROVEN')
    else:
        print('OVERALL_VERDICT=UNRESOLVED_REGISTER_LAYOUT_CHECK_FAILED')

if __name__=='__main__': main()
