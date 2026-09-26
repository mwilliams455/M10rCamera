#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

TABLE_LO=0x52a98
TABLE_HI=0x52aac
SCAN_LO=0x51000
SCAN_HI=0x52a98

def one(md,data,pc):
    return next(md.disasm(data[pc:pc+4],pc,count=1),None)

def pool_target(ins,mode):
    try:ops=list(ins.operands)
    except Exception:return []
    out=[]
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            base=((ins.address+4)&~3) if mode=="THUMB" else ins.address+8
            out.append(base+int(op.mem.disp))
    return out

def nearest_prologue(md,data,pc,mode):
    step=2 if mode=="THUMB" else 4
    lo=max(0,pc-0x1200)
    best=None
    for p in range(lo-(lo%step),pc+1,step):
        i=one(md,data,p)
        if not i:continue
        s=i.op_str.lower()
        if (i.mnemonic=="push" and "lr" in s) or (i.mnemonic=="stmdb" and "sp" in s and "lr" in s):
            best=p
    return best

def strings(data,lo,hi):
    out=[];i=max(0,lo);hi=min(len(data),hi)
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=6:out.append({"offset":hex(i),"text":data[i:j].decode("ascii","replace")})
            i=j
        else:i+=1
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open(encoding="utf-8")))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    hits=[]
    for mode_name,mode,step in (("THUMB",CS_MODE_THUMB,2),("ARM",CS_MODE_ARM,4)):
        md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
        for pc in range(SCAN_LO-(SCAN_LO%step),SCAN_HI,step):
            ins=one(md,data,pc)
            if not ins:continue
            for pool in pool_target(ins,mode_name):
                if TABLE_LO<=pool<TABLE_HI:
                    hits.append({"isa":mode_name,"pc":hex(pc),"mnemonic":ins.mnemonic,"op_str":ins.op_str,
                                 "pool":hex(pool),"nearest_prologue":None if nearest_prologue(md,data,pc,mode_name) is None else hex(nearest_prologue(md,data,pc,mode_name))})
    contexts=[]
    for h in hits:
        mode=CS_MODE_THUMB if h["isa"]=="THUMB" else CS_MODE_ARM
        step=2 if h["isa"]=="THUMB" else 4
        md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
        start=int(h["nearest_prologue"],16) if h["nearest_prologue"] else max(SCAN_LO,int(h["pc"],16)-0x100)
        end=min(TABLE_LO,start+0x1400)
        ins=[]
        for pc in range(start,end,step):
            i=one(md,data,pc)
            if not i:continue
            x={"address":hex(pc),"mnemonic":i.mnemonic,"op_str":i.op_str}
            pools=pool_target(i,h["isa"])
            if pools:x["pc_pools"]=[hex(x) for x in pools]
            ins.append(x)
        contexts.append({"hit":h,"start":hex(start),"instructions":ins,
                         "nearby_strings":strings(data,start-0x400,min(len(data),end+0x800))})
    result={"schema":"M10R_YBLEND_GAMMA_TABLEXREF1H_V1","table_range":[hex(TABLE_LO),hex(TABLE_HI)],
            "hits":hits,"contexts":contexts}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("HITS",json.dumps(hits,indent=2))
    for c in contexts:
        print("\n=== CONTEXT",c["hit"],"===")
        for s in c["nearby_strings"]:
            if any(k in s["text"].lower() for k in ("gamma","dgamma","table","yb")):print("STR",s)
        for i in c["instructions"]:
            pc=int(i["address"],16)
            if abs(pc-int(c["hit"]["pc"],16))<=0x100 or any(TABLE_LO<=int(p,16)<TABLE_HI for p in i.get("pc_pools",[])):
                print(i["address"],i["mnemonic"],i["op_str"],i.get("pc_pools",""))
if __name__=="__main__":main()
