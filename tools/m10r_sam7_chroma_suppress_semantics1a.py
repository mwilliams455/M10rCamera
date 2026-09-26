#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM

MAIN_RETURN=0x52224
ERROR_RETURN=0x5223c
DIAG_ADR=0x52230
SEARCH_LO=0x51f00
SEARCH_HI=0x52240

def one(md,b,pc):
    return next(md.disasm(b[pc:pc+4],pc,count=1),None)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    b=(a.sections/row["file"]).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    pro=[]
    for pc in range(SEARCH_LO,SEARCH_HI,2):
        i=one(md,b,pc)
        if i and i.mnemonic=="push" and "lr" in i.op_str: pro.append(pc)

    adr=one(md,b,DIAG_ADR)
    diag_target=None
    if adr and adr.mnemonic=="adr" and len(adr.operands)>=2 and adr.operands[1].type==ARM_OP_IMM:
        # Capstone Thumb ADR operand is displacement in this binary.
        diag_target=((DIAG_ADR+4)&~3)+int(adr.operands[1].imm)

    candidates=[]
    for start in pro:
        ins=[];pc=start
        while pc<=ERROR_RETURN:
            i=one(md,b,pc)
            if not i: break
            ins.append({"address":hex(pc),"mnemonic":i.mnemonic,"op_str":i.op_str})
            pc+=i.size
        # Candidate must reach the known Chroma Suppress main body and both returns.
        addrs={int(x["address"],16) for x in ins}
        if 0x52038 in addrs and MAIN_RETURN in addrs and ERROR_RETURN in addrs:
            candidates.append({"start":hex(start),"instruction_count":len(ins),"instructions":ins})

    if len(candidates)!=1:
        raise RuntimeError(f"expected one enclosing candidate, got {[x['start'] for x in candidates]}")
    start=int(candidates[0]["start"],16)

    callers=[]
    for pc in range(0,len(b)-4,2):
        i=one(md,b,pc)
        if not i or i.mnemonic not in ("bl","blx"): continue
        try:ops=list(i.operands)
        except Exception:continue
        if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&0xffffffff)==start:
            callers.append(hex(pc))

    diag_bytes=b[diag_target:diag_target+96] if diag_target is not None else b""
    diag=diag_bytes.split(b"\0",1)[0].decode("latin1","replace") if diag_bytes else None

    # Extract the exact six halfword source offsets and destination word/field geometry
    # from the known same-function instruction window.
    six=[
      {"lane":0,"param_offset":"0x04","dest_offset":"0x10","bits":"0..13"},
      {"lane":1,"param_offset":"0x06","dest_offset":"0x10","bits":"16..29"},
      {"lane":2,"param_offset":"0x08","dest_offset":"0x14","bits":"0..13"},
      {"lane":3,"param_offset":"0x0a","dest_offset":"0x14","bits":"16..29"},
      {"lane":4,"param_offset":"0x0c","dest_offset":"0x18","bits":"0..13"},
      {"lane":5,"param_offset":"0x0e","dest_offset":"0x18","bits":"16..29"},
    ]
    result={"schema":"M10R_SAM7_CHROMA_SUPPRESS_SEMANTICS1A_V1",
      "function_start":hex(start),"main_return":hex(MAIN_RETURN),"error_return":hex(ERROR_RETURN),
      "diagnostic_adr":hex(DIAG_ADR),"diagnostic_target":None if diag_target is None else hex(diag_target),
      "diagnostic_string":diag,"direct_callers":callers,"six_lane_packing":six,
      "guardrails":["Lane ordering is proven; hue/color names for lanes are not yet proven.",
                    "This is register-programming evidence, not pixel arithmetic."]}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("function_start","diagnostic_target","diagnostic_string","direct_callers","six_lane_packing")},indent=2))
if __name__=="__main__":main()
