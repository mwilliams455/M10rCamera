#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from collections import deque
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

ENTRY=0x51da6
LO=0x51d80
HI=0x51f1a
PAGE=0x20020900

def u32(b,o): return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None
def one(md,data,pc): return next(md.disasm(data[pc:pc+4],pc,count=1),None)
def target(i):
    try:ops=list(i.operands)
    except:return None
    if ops and ops[-1].type==ARM_OP_IMM:return int(ops[-1].imm)&0xffffffff
    return None
def ret(i):
    return (i.mnemonic=="pop" and "pc" in i.op_str) or (i.mnemonic in ("bx","bxj") and i.op_str.strip()=="lr")
def width(mn):
    if mn.startswith("ldrb"): return 1
    if mn.startswith("ldrh"): return 2
    if mn.startswith("ldr"): return 4
    return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    q=deque([ENTRY]);seen=set();insns={};edges=[];calls=[]
    while q:
        st=q.popleft()
        if not (LO<=st<HI):continue
        pc=st
        for _ in range(600):
            if not (LO<=pc<HI) or pc in seen:break
            i=one(md,data,pc)
            if not i:break
            seen.add(pc);insns[pc]=i
            t=target(i)
            if i.mnemonic in ("bl","blx"):
                if t is not None:calls.append({"pc":hex(pc),"target":hex(t)})
                pc+=i.size;continue
            if ret(i):break
            if i.mnemonic=="b":
                if t is not None and LO<=t<HI:q.append(t);edges.append({"from":hex(pc),"to":hex(t),"kind":"b"})
                break
            if (i.mnemonic.startswith("b") and i.mnemonic not in ("bl","blx","bx","bxj")) or i.mnemonic in ("cbz","cbnz"):
                if t is not None and LO<=t<HI:q.append(t);edges.append({"from":hex(pc),"to":hex(t),"kind":i.mnemonic})
                pc+=i.size;continue
            pc+=i.size

    loads=[];lits=[];stores=[];rowsout=[]
    for pc in sorted(insns):
        i=insns[pc];x={"pc":hex(pc),"mnemonic":i.mnemonic,"op_str":i.op_str}
        try:ops=list(i.operands)
        except:ops=[]
        for op in ops:
            if op.type!=ARM_OP_MEM:continue
            base=md.reg_name(op.mem.base) if op.mem.base else ""
            idx=md.reg_name(op.mem.index) if op.mem.index else ""
            disp=int(op.mem.disp)
            if base=="pc":
                po=((pc+4)&~3)+disp;v=u32(data,po)
                x.setdefault("literals",[]).append({"pool":hex(po),"value":None if v is None else hex(v)})
                if v is not None:lits.append({"pc":hex(pc),"pool":hex(po),"value":hex(v)})
            elif i.mnemonic.startswith("ldr"):
                loads.append({"pc":hex(pc),"mnemonic":i.mnemonic,"width":width(i.mnemonic),"base":base,"index":idx,"disp":disp,"op_str":i.op_str})
            elif i.mnemonic.startswith("str"):
                stores.append({"pc":hex(pc),"mnemonic":i.mnemonic,"base":base,"index":idx,"disp":disp,"op_str":i.op_str})
        rowsout.append(x)

    result={"schema":"M10R_SAM7_YCCONVERT_FIELDTRACE1C_V1","entry":hex(ENTRY),
            "reachable_count":len(rowsout),"calls":calls,"edges":edges,
            "loads":loads,"stores":stores,"literals":lits,"instructions":rowsout}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("ENTRY",hex(ENTRY),"REACHABLE",len(rowsout))
    print("CALLS",json.dumps(calls,indent=2))
    print("MMIO_LITERALS")
    for z in lits:
        v=int(z["value"],16)
        if 0x20000000<=v<0x21000000: print(json.dumps(z))
    print("LOADS")
    for z in loads:print(json.dumps(z,sort_keys=True))
    print("STORES")
    for z in stores:print(json.dumps(z,sort_keys=True))
    print("DISASM")
    for x in rowsout:
        ex=""
        if "literals" in x: ex=" ; "+",".join(z["pool"]+"->"+str(z["value"]) for z in x["literals"])
        print(f"{x['pc']}: {x['mnemonic']:8s} {x['op_str']}{ex}")
if __name__=="__main__":main()
