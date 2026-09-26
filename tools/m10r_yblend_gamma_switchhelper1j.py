#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

HELPER=0xB1B78
HLO=HELPER-0x30
HHI=HELPER+0x90
FUNC_LO=0x526BC
FUNC_HI=0x5277C

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def disasm(data,lo,hi):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    out=[]
    for ins in md.disasm(data[lo:hi],lo):
        x={"address":ins.address,"mnemonic":ins.mnemonic,"op_str":ins.op_str,"size":ins.size,
           "bytes":ins.bytes.hex()}
        lits=[]
        for op in getattr(ins,"operands",[]):
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                base=(ins.address+4)&~3
                po=base+int(op.mem.disp)
                v=u32(data,po)
                lits.append({"pool":po,"value":v})
            if op.type==ARM_OP_IMM and ins.mnemonic.startswith("b"):
                x.setdefault("branch_immediates",[]).append(int(op.imm)&0xffffffff)
        if lits:x["literals"]=lits
        out.append(x)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    helper=disasm(data,HLO,HHI)
    func=disasm(data,FUNC_LO,FUNC_HI)
    inline=data[0x52708:0x52712]
    result={
      "schema":"M10R_YBLEND_GAMMA_SWITCHHELPER1J_V1",
      "helper_window":[hex(HLO),hex(HHI)],
      "helper_bytes":data[HLO:HHI].hex(),
      "helper_disasm":helper,
      "func_window":[hex(FUNC_LO),hex(FUNC_HI)],
      "func_bytes":data[FUNC_LO:FUNC_HI].hex(),
      "func_disasm":func,
      "inline_after_switch_call":{"start":"0x52708","end":"0x52712","hex":inline.hex(),"u8":list(inline)},
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("INLINE",inline.hex(),list(inline))
    print("=== HELPER ===")
    for x in helper:
        extra=[]
        for z in x.get("literals",[]): extra.append(f"LIT {hex(z['pool'])}->{hex(z['value'])}")
        if x.get("branch_immediates"):extra.append("BR "+",".join(hex(v) for v in x["branch_immediates"]))
        print(f"{hex(x['address'])}: {x['bytes']:<10} {x['mnemonic']:<8} {x['op_str']}"+((" ; "+" ; ".join(extra)) if extra else ""))
    print("=== FUNC ===")
    for x in func:
        extra=[]
        for z in x.get("literals",[]):extra.append(f"LIT {hex(z['pool'])}->{hex(z['value'])}")
        if x.get("branch_immediates"):extra.append("BR "+",".join(hex(v) for v in x["branch_immediates"]))
        print(f"{hex(x['address'])}: {x['bytes']:<10} {x['mnemonic']:<8} {x['op_str']}"+((" ; "+" ; ".join(extra)) if extra else ""))
if __name__=="__main__":main()
