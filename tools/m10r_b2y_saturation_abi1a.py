#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

SELECTOR=0x153b80
SETTER=0xd0770

def rows(root):
    with (root/"sections.csv").open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def u32(b,o):return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    rs=rows(a.sections);r=next(x for x in rs if x["name"]=="IMG-System")
    b=(a.sections/r["file"]).read_bytes();base=int(r["image_base"],16)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    out=[]
    for label,start,maxspan in (("SELECTOR_0x18",SELECTOR,0x120),("SETTER_D0770",SETTER,0x500)):
        out.append(f"=== {label} start=0x{start:x} ===")
        off=start
        for ins in md.disasm(b[off:off+maxspan],base+off):
            extras=[]
            try:ops=list(ins.operands)
            except Exception:ops=[]
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pool=((ins.address+4)&~3)+op.mem.disp
                    val=u32(b,pool-base)
                    extras.append(f"LIT@0x{pool-base:x}={'NONE' if val is None else hex(val)}")
            out.append(f"0x{ins.address-base:06x}: {ins.mnemonic:8s} {ins.op_str}"+((" ; "+" ; ".join(extras)) if extras else ""))
            if ins.address-base>start+2 and ((ins.mnemonic=="pop" and "pc" in ins.op_str) or (ins.mnemonic=="bx" and ins.op_str.strip()=="lr")):
                break
        out.append("")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text("\n".join(out)+"\n")
    print("\n".join(out))
if __name__=="__main__":main()
