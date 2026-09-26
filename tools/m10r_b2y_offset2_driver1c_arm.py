#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

BASE=0x42000000
ENTRY=0x0d3284
MAXSPAN=0x1000

def u32(b,o): return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def strings(data,lo,hi,minlen=7):
    out=[];i=max(0,lo);hi=min(len(data),hi)
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=minlen:out.append({"offset":hex(i),"text":data[i:j].decode("ascii","replace")})
            i=j
        else:i+=1
    return out

def is_return(ins):
    s=ins.op_str.lower()
    if ins.mnemonic=="bx" and s.strip()=="lr": return True
    if ins.mnemonic=="pop" and "pc" in s: return True
    if ins.mnemonic.startswith("ldm") and "sp" in s and "pc" in s: return True
    if ins.mnemonic=="mov" and s.replace(" ","")=="pc,lr": return True
    return False

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-System")
    data=(a.sections/row["file"]).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);md.detail=True
    out=[];mmio=[];calls=[];stores=[]
    for ins in md.disasm(data[ENTRY:ENTRY+MAXSPAN],BASE+ENTRY):
        off=ins.address-BASE
        x={"offset":hex(off),"mnemonic":ins.mnemonic,"op_str":ins.op_str}
        try:ops=list(ins.operands)
        except Exception:ops=[]
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                # ARM-state PC observes current instruction address + 8.
                po=(ins.address+8+int(op.mem.disp))-BASE
                v=u32(data,po)
                x.setdefault("literals",[]).append({"pool":hex(po),"value":None if v is None else hex(v)})
                if v is not None and 0x20000000<=v<0x21000000:
                    mmio.append({"pc":hex(off),"value":hex(v),"pool":hex(po)})
        if ins.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
            tgt=int(ops[0].imm)&0xffffffff
            calls.append({"pc":hex(off),"target_va":hex(tgt),"target_offset":hex((tgt-BASE)&0xffffffff),"mnemonic":ins.mnemonic})
            x["call_target"]=hex(tgt)
        if ins.mnemonic.startswith("str"):stores.append(hex(off))
        out.append(x)
        if off>ENTRY and is_return(ins):break
    nearby=strings(data,ENTRY-0x800,ENTRY+0x1400)
    result={"schema":"M10R_B2Y_OFFSET2_DRIVER1C_ARM_V1","entry":hex(ENTRY),"isa":"ARM",
            "instruction_count":len(out),"mmio_literals":mmio,"calls":calls,
            "store_sites":stores,"nearby_strings":nearby,"instructions":out}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("ENTRY",hex(ENTRY),"ISA ARM","INSNS",len(out))
    print("MMIO",json.dumps(mmio,indent=2))
    print("CALLS",json.dumps(calls,indent=2))
    print("STRINGS")
    for s in nearby:
        if any(k in s["text"].lower() for k in ("b2y","offset","noise","color","chroma","operation")):
            print(s["offset"],s["text"])
    for x in out:
        ex=[]
        if "literals" in x:ex.append("LIT="+",".join(z["pool"]+"->"+str(z["value"]) for z in x["literals"]))
        if "call_target" in x:ex.append("CALL="+x["call_target"])
        print(f"{x['offset']}: {x['mnemonic']:8s} {x['op_str']}"+((" ; "+" ; ".join(ex)) if ex else ""))
if __name__=="__main__":main()
