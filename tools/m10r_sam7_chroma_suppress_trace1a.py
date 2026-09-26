#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,struct,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

LO=0x52000
HI=0x52520
TARGET_STR=b"Im_B2Y_Ctrl_Chroma_Suppress"
TARGET_PAGE=0x20021100

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    s=data.find(TARGET_STR)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    ins=[]
    prologues=[]
    page_refs=[]
    str_refs=[]
    for pc in range(LO,HI,2):
        one=next(md.disasm(data[pc:pc+4],pc,count=1),None)
        if not one: continue
        x={"address":hex(pc),"mnemonic":one.mnemonic,"op_str":one.op_str}
        if one.mnemonic=="push" and "lr" in one.op_str: prologues.append(hex(pc))
        try:ops=list(one.operands)
        except Exception:ops=[]
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                pool=((pc+4)&~3)+int(op.mem.disp);v=u32(data,pool)
                if v is not None:
                    x.setdefault("literals",[]).append({"pool":hex(pool),"value":hex(v)})
                    if v==TARGET_PAGE:page_refs.append(hex(pc))
        if one.mnemonic.startswith("adr") and ops and ops[-1].type==ARM_OP_IMM:
            tgt=((pc+4)&~3)+int(ops[-1].imm)
            if tgt==s:str_refs.append(hex(pc))
            x["adr_target"]=hex(tgt)
        ins.append(x)
    result={"schema":"M10R_SAM7_CHROMA_SUPPRESS_TRACE1A_V1","string_offset":hex(s),"prologues":prologues,
            "page_0x20021100_refs":page_refs,"string_adr_refs":str_refs,"instructions":ins}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("string",hex(s),"prologues",prologues)
    print("page refs",page_refs)
    print("string refs",str_refs)
    for x in ins:
        ad=int(x["address"],16)
        if (page_refs and any(abs(ad-int(p,16))<0x100 for p in page_refs)) or (str_refs and any(abs(ad-int(p,16))<0x100 for p in str_refs)):
            extra=""
            if "literals" in x:extra+=" LIT="+",".join(z["pool"]+"->"+z["value"] for z in x["literals"])
            if "adr_target" in x:extra+=" ADR="+x["adr_target"]
            print(f"{x['address']}: {x['mnemonic']:8s} {x['op_str']}{extra}")
if __name__=="__main__":main()
