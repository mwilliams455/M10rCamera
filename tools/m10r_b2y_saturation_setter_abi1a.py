#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,struct,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC

ENTRY=0xD0770
MAX=0x500

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    r=next(x for x in rows if x["name"]=="IMG-System")
    data=(a.sections/r["file"]).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    insns=[]
    for ins in md.disasm(data[ENTRY:ENTRY+MAX],ENTRY):
        row={"address":hex(ins.address),"size":ins.size,"mnemonic":ins.mnemonic,"op_str":ins.op_str}
        lits=[]
        try:ops=list(ins.operands)
        except Exception:ops=[]
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                p=((ins.address+4)&~3)+op.mem.disp
                v=u32(data,p)
                lits.append({"pool":hex(p),"value":None if v is None else hex(v)})
        if lits:row["literals"]=lits
        if ins.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
            row["call_target"]=hex(int(ops[0].imm)&0xffffffff)
        insns.append(row)
        if len(insns)>3 and ((ins.mnemonic=="pop" and "pc" in ins.op_str) or (ins.mnemonic=="bx" and ins.op_str.strip()=="lr")):
            break
    result={"schema":"M10R_B2Y_SATURATION_SETTER_ABI1A_V1","entry":hex(ENTRY),"instruction_count":len(insns),"instructions":insns}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    for x in insns:
        extra=""
        if "literals" in x:extra+=" LIT="+",".join(z["pool"]+"->"+str(z["value"]) for z in x["literals"])
        if "call_target" in x:extra+=" CALL="+x["call_target"]
        print(f"{x['address']}: {x['mnemonic']:8s} {x['op_str']}{extra}")
if __name__=="__main__":main()
