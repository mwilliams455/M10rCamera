#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM

TARGET=0x526bc

def scan(data,mode,label):
    md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
    hits=[]
    for start in range(0,2 if label=="THUMB" else 4,2 if label=="THUMB" else 4):
        try:
            ins=list(md.disasm(data[start:],start))
        except Exception:
            continue
        for i,x in enumerate(ins):
            if x.mnemonic not in ("bl","blx"):continue
            ops=getattr(x,"operands",[])
            if not ops or ops[0].type!=ARM_OP_IMM:continue
            t=int(ops[0].imm)&0xffffffff
            if t not in (TARGET,TARGET|1):continue
            ctx=[]
            for y in ins[max(0,i-18):min(len(ins),i+8)]:
                ctx.append({"address":hex(y.address),"bytes":y.bytes.hex(),"mnemonic":y.mnemonic,"op_str":y.op_str})
            hits.append({"isa":label,"pc":hex(x.address),"target":hex(t),"context":ctx})
    # de-dupe by pc
    seen=set();out=[]
    for h in hits:
        k=(h["isa"],h["pc"])
        if k not in seen:seen.add(k);out.append(h)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args();rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7");data=(a.sections/row["file"]).read_bytes()
    hits=scan(data,CS_MODE_THUMB,"THUMB")+scan(data,CS_MODE_ARM,"ARM")
    r={"schema":"M10R_YBLEND_GAMMA_CALLERS1L_V1","target":hex(TARGET),"immediate_callers":hits,
       "boundary":"No immediate caller does not exclude indirect/function-pointer use."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("CALLER_COUNT",len(hits))
    for h in hits:
        print("\nCALL",h["isa"],h["pc"])
        for x in h["context"]:
            print(x["address"],x["bytes"],x["mnemonic"],x["op_str"])
if __name__=="__main__":main()
