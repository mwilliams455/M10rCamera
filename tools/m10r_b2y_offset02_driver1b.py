#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

ENTRY=0xD3284
BASE=0x42000000
MAXSPAN=0x500

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-System")
    data=(a.sections/row["file"]).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    insns=[];mmio=[];calls=[]
    for ins in md.disasm(data[ENTRY:ENTRY+MAXSPAN],BASE+ENTRY):
        off=ins.address-BASE
        x={"offset":hex(off),"va":hex(ins.address),"mnemonic":ins.mnemonic,"op_str":ins.op_str}
        try:ops=list(ins.operands)
        except Exception:ops=[]
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                po=(((ins.address+4)&~3)+int(op.mem.disp))-BASE
                v=u32(data,po)
                x.setdefault("literals",[]).append({"pool_offset":hex(po),"value":None if v is None else hex(v)})
                if v is not None and 0x20000000<=v<0x21000000:
                    mmio.append({"pc":hex(off),"pool_offset":hex(po),"value":hex(v)})
        if ins.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
            tgt=int(ops[0].imm)&0xffffffff
            calls.append({"pc":hex(off),"target_va":hex(tgt),"target_offset":hex((tgt-BASE)&0xffffffff)})
            x["call_target"]=hex(tgt)
        insns.append(x)
        if off>ENTRY+2 and ((ins.mnemonic=="pop" and "pc" in ins.op_str) or (ins.mnemonic=="bx" and ins.op_str.strip()=="lr")):
            break

    strings=[];lo=max(0,ENTRY-0x400);hi=min(len(data),ENTRY+0x800);i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=8:
                s=data[i:j].decode("ascii","replace")
                if any(k in s.lower() for k in ("b2y","offset","chroma","color","luma","ycb","yc","noise")):
                    strings.append({"offset":hex(i),"text":s})
            i=j
        else:i+=1

    result={"schema":"M10R_B2Y_OFFSET02_DRIVER1B_V1","entry":hex(ENTRY),
            "instruction_count":len(insns),"mmio_literals":mmio,
            "calls":calls,"nearby_strings":strings,"instructions":insns}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("ENTRY",hex(ENTRY),"INSNS",len(insns))
    print("MMIO",json.dumps(mmio,indent=2))
    print("CALLS",json.dumps(calls,indent=2))
    print("STRINGS",json.dumps(strings,indent=2))
    for x in insns:
        ex=[]
        if "literals" in x: ex.append("LIT="+",".join(z["pool_offset"]+"->"+str(z["value"]) for z in x["literals"]))
        if "call_target" in x: ex.append("CALL="+x["call_target"])
        print(f"{x['offset']}: {x['mnemonic']:8s} {x['op_str']}"+((" ; "+" ; ".join(ex)) if ex else ""))
if __name__=="__main__":main()
