#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

LO=0x52800
HI=0x52c80
FULL=[0x20A68000+i*0x1000 for i in range(5)]
DIFF=[0x20A40000+i*0x8000 for i in range(5)]

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def ascii_strings(data,lo,hi):
    out=[];i=max(0,lo);hi=min(len(data),hi)
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=5:out.append({"offset":hex(i),"text":data[i:j].decode("ascii","replace")})
            i=j
        else:i+=1
    return out

def decode(data,mode,name):
    md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
    ins=[]
    for i in md.disasm(data[LO:HI],LO):
        x={"address":hex(i.address),"mnemonic":i.mnemonic,"op_str":i.op_str}
        try:ops=list(i.operands)
        except Exception:ops=[]
        lits=[]
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                if name=="THUMB":
                    base=(i.address+4)&~3
                else:
                    base=i.address+8
                po=base+int(op.mem.disp)
                v=u32(data,po)
                if v is not None:
                    lits.append({"pool":hex(po),"value":hex(v),
                                 "gamma_slot":("full"+str(FULL.index(v)) if v in FULL else ("diff"+str(DIFF.index(v)) if v in DIFF else None))})
        if lits:x["literals"]=lits
        if i.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
            x["call_target"]=hex(int(ops[0].imm)&0xffffffff)
        ins.append(x)
    score=sum(20 for x in ins for z in x.get("literals",[]) if z.get("gamma_slot")) + sum(1 for x in ins if x["mnemonic"] in ("push","pop"))
    return {"isa":name,"score":score,"instructions":ins}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open(encoding="utf-8")))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    dec=[decode(data,CS_MODE_THUMB,"THUMB"),decode(data,CS_MODE_ARM,"ARM")]
    best=max(dec,key=lambda x:x["score"])
    strings=ascii_strings(data,LO-0x800,HI+0x1200)
    gamma_strings=[x for x in strings if any(k in x["text"].lower() for k in ("gamma","yb","table","r2y","b2y"))]
    result={"schema":"M10R_YBLEND_GAMMA_SAM7_1G_V1","window":[hex(LO),hex(HI)],
            "full_slots":[hex(x) for x in FULL],"diff_slots":[hex(x) for x in DIFF],
            "selected_isa":best["isa"],"selected_score":best["score"],
            "gamma_strings":gamma_strings,"decodes":dec}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("SELECTED",best["isa"],"SCORE",best["score"])
    print("GAMMA_STRINGS",json.dumps(gamma_strings,indent=2))
    for x in best["instructions"]:
        slot=[z for z in x.get("literals",[]) if z.get("gamma_slot")]
        if slot or x["mnemonic"] in ("push","pop","bl","blx","bx","cmp","beq","bne","b","tbb","tbh"):
            ex=[]
            if slot:ex.append("SLOT="+",".join(z["gamma_slot"]+"@"+z["value"] for z in slot))
            if "call_target" in x:ex.append("CALL="+x["call_target"])
            print(f"{x['address']}: {x['mnemonic']:8s} {x['op_str']}"+((" ; "+" ; ".join(ex)) if ex else ""))
if __name__=="__main__":main()
