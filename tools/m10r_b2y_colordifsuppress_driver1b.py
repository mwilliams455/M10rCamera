#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

BASE=0x42000000
ENTRY=0x0d0770
MAXSPAN=0x900
PAGE=0x20021100

def u32(b,o): return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def is_return(ins):
    s=ins.op_str.lower().replace(" ","")
    return ((ins.mnemonic=="bx" and s=="lr") or
            (ins.mnemonic=="pop" and "pc" in s) or
            (ins.mnemonic.startswith("ldm") and "pc" in s) or
            (ins.mnemonic=="mov" and s=="pc,lr"))

def decode(data,mode,name):
    md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN); md.detail=True
    rows=[];mmio=[];calls=[];payload_mem=[]
    for ins in md.disasm(data[ENTRY:ENTRY+MAXSPAN],BASE+ENTRY):
        off=ins.address-BASE
        x={"offset":hex(off),"mnemonic":ins.mnemonic,"op_str":ins.op_str}
        try: ops=list(ins.operands)
        except Exception: ops=[]
        for op in ops:
            if op.type==ARM_OP_MEM:
                base=ins.reg_name(op.mem.base) if op.mem.base else ""
                idx=ins.reg_name(op.mem.index) if op.mem.index else ""
                x.setdefault("mem",[]).append({"base":base,"index":idx,"disp":int(op.mem.disp)})
                if base=="pc":
                    pc_bias=4 if name=="THUMB" else 8
                    pc_base=((ins.address+pc_bias)&~3) if name=="THUMB" else ins.address+pc_bias
                    po=pc_base+int(op.mem.disp)-BASE
                    v=u32(data,po)
                    x.setdefault("literals",[]).append({"pool":hex(po),"value":None if v is None else hex(v)})
                    if v is not None and PAGE<=v<PAGE+0x100:
                        mmio.append({"pc":hex(off),"value":hex(v),"pool":hex(po)})
                elif base in ("r0","r1","r2","r3","r4","r5","r6","r7","r8","r9","r10","r11","ip"):
                    if ins.mnemonic.startswith("ldr") or ins.mnemonic.startswith("ldrh") or ins.mnemonic.startswith("ldrb"):
                        payload_mem.append({"pc":hex(off),"mnemonic":ins.mnemonic,"base":base,"index":idx,"disp":int(op.mem.disp),"op_str":ins.op_str})
        if ins.mnemonic in ("bl","blx") and ops and ops[0].type==ARM_OP_IMM:
            tgt=int(ops[0].imm)&0xffffffff
            calls.append({"pc":hex(off),"target_va":hex(tgt),"target_offset":hex((tgt-BASE)&0xffffffff)})
            x["call_target"]=hex(tgt)
        rows.append(x)
        if off>ENTRY and is_return(ins): break
    score=(100*len(mmio)) + (20 if rows and rows[0]["mnemonic"] in ("push","stmdb") else 0) + (10 if rows and is_return(type("I",(object,),{"mnemonic":rows[-1]["mnemonic"],"op_str":rows[-1]["op_str"]})()) else 0)
    return {"isa":name,"score":score,"instruction_count":len(rows),"mmio_literals":mmio,"calls":calls,"load_candidates":payload_mem,"instructions":rows}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-System")
    data=(a.sections/row["file"]).read_bytes()
    dec=[decode(data,CS_MODE_THUMB,"THUMB"),decode(data,CS_MODE_ARM,"ARM")]
    best=max(dec,key=lambda x:x["score"])
    result={"schema":"M10R_B2Y_COLORDIFSUPPRESS_DRIVER1B_V1","entry":hex(ENTRY),"page":hex(PAGE),
            "selected_isa":best["isa"],"selected_score":best["score"],"decodes":dec}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("SELECTED",best["isa"],"SCORE",best["score"],"INSNS",best["instruction_count"])
    print("MMIO",json.dumps(best["mmio_literals"],indent=2))
    print("CALLS",json.dumps(best["calls"],indent=2))
    print("LOAD_CANDIDATES")
    for x in best["load_candidates"]: print(json.dumps(x,sort_keys=True))
    print("DISASM")
    for x in best["instructions"]:
        ex=[]
        if "literals" in x: ex.append("LIT="+",".join(z["pool"]+"->"+str(z["value"]) for z in x["literals"]))
        if "call_target" in x: ex.append("CALL="+x["call_target"])
        print(f"{x['offset']}: {x['mnemonic']:8s} {x['op_str']}"+((" ; "+" ; ".join(ex)) if ex else ""))
if __name__=="__main__": main()
