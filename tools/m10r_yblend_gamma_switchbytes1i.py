#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN

LO=0x526f8
HI=0x5277c

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open(encoding="utf-8")))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    raw=data[LO:HI]
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    ins=[]
    for i in md.disasm(raw,LO):
        ins.append({"address":hex(i.address),"size":i.size,"bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"op_str":i.op_str})
    # Explicit candidate branch-table bytes following the suspicious instruction area.
    windows={}
    for x,y in [(0x52700,0x52720),(0x52700,0x52730),(0x52702,0x52712),(0x52704,0x52714)]:
        windows[f"{x:#x}-{y:#x}"]=data[x:y].hex()
    result={"schema":"M10R_YBLEND_GAMMA_SWITCHBYTES1I_V1","range":[hex(LO),hex(HI)],"raw_hex":raw.hex(),"windows":windows,"instructions":ins}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("WINDOWS",json.dumps(windows,indent=2))
    for x in ins:print(x["address"],x["bytes"],x["mnemonic"],x["op_str"])
if __name__=="__main__":main()
