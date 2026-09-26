#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

LO=0x51d00
HI=0x52240
TARGET_SUB=b"Im_B2Y_Ctrl_Chroma_Suppress"
TARGET_PAGE=0x20021100

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def one(md,data,pc):
    return next(md.disasm(data[pc:pc+4],pc,count=1),None)

def decode_func(md,data,start,maxend=HI):
    out=[];pc=start
    while pc<maxend:
        i=one(md,data,pc)
        if i is None: break
        out.append(i);pc+=i.size
        if len(out)>2 and ((i.mnemonic=="pop" and "pc" in i.op_str) or
                           (i.mnemonic=="bx" and i.op_str.strip()=="lr")):
            break
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    inside=data.find(TARGET_SUB)
    run=inside
    while run>0 and 32<=data[run-1]<127: run-=1

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    pro=[]
    for pc in range(LO,HI,2):
        i=one(md,data,pc)
        if i and i.mnemonic=="push" and "lr" in i.op_str:
            pro.append(pc)

    funcs=[]
    for p in pro:
        ins=decode_func(md,data,p)
        if not ins: continue
        end=ins[-1].address+ins[-1].size
        refs=[];pages=[];calls=[]
        for i in ins:
            try:ops=list(i.operands)
            except Exception:ops=[]
            if i.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
                calls.append({"pc":hex(i.address),"target":hex(int(ops[0].imm)&0xffffffff)})
            if i.mnemonic.startswith("adr") and ops and ops[-1].type==ARM_OP_IMM:
                tgt=((i.address+4)&~3)+int(ops[-1].imm)
                if abs(tgt-run)<=4 or abs(tgt-inside)<=4:
                    refs.append({"pc":hex(i.address),"target":hex(tgt)})
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pool=((i.address+4)&~3)+int(op.mem.disp);v=u32(data,pool)
                    if v==TARGET_PAGE: pages.append({"pc":hex(i.address),"pool":hex(pool)})
        funcs.append({"start":hex(p),"end":hex(end),"insn_count":len(ins),"string_refs":refs,"page_refs":pages,"calls":calls})

    # Candidate is the last well-formed function ending immediately before the error-tail / next prologue.
    # Keep all candidates for audit; select those ending in 0x52220..0x52240.
    candidates=[f for f in funcs if 0x52220<=int(f["end"],16)<=0x52240]

    result={"schema":"M10R_SAM7_CHROMA_SUPPRESS_TRACE1B_V1","string_sub_offset":hex(inside),
            "string_run_start":hex(run),"prologues":[hex(x) for x in pro],
            "functions":funcs,"candidate_functions":candidates}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")

    print("string",hex(inside),"run",hex(run))
    print("prologues",[hex(x) for x in pro])
    print("CANDIDATES")
    for f in candidates: print(json.dumps(f,sort_keys=True))
    for f in candidates:
        p=int(f["start"],16);end=int(f["end"],16)
        print(f"\n=== FUNC {p:#x}..{end:#x} ===")
        for i in decode_func(md,data,p):
            extra=[]
            try:ops=list(i.operands)
            except Exception:ops=[]
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pool=((i.address+4)&~3)+int(op.mem.disp);v=u32(data,pool)
                    if v is not None: extra.append(f"LIT@{pool:#x}={v:#x}")
            if i.mnemonic.startswith("adr") and ops and ops[-1].type==ARM_OP_IMM:
                tgt=((i.address+4)&~3)+int(ops[-1].imm);extra.append(f"ADR->{tgt:#x}")
            if i.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
                extra.append(f"CALL->{int(ops[0].imm)&0xffffffff:#x}")
            print(f"{i.address:#08x}: {i.mnemonic:8s} {i.op_str}" + ((" ; "+" ; ".join(extra)) if extra else ""))
if __name__=="__main__":main()
