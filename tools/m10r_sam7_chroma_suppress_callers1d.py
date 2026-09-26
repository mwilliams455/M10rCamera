#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC

TARGET=0x51f1a
PTRS=(TARGET,TARGET|1)
CTX=0x90

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def strings(data,lo,hi,minlen=5):
    out=[];i=max(0,lo);hi=min(len(data),hi)
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=minlen:
                out.append({"offset":hex(i),"text":data[i:j].decode("ascii","replace")})
            i=j
        else:i+=1
    return out

def one(md,data,pc):
    return next(md.disasm(data[pc:pc+4],pc,count=1),None)

def prologue(md,data,pc):
    best=None
    lo=max(0,pc-0x600)&~1
    for x in range(lo,pc+1,2):
        i=one(md,data,x)
        if i and ((i.mnemonic=="push" and "lr" in i.op_str) or
                  (i.mnemonic.startswith("stm") and "sp" in i.op_str and "lr" in i.op_str)):
            best=x
    return best

def fmt(i):
    return {"address":hex(i.address),"mnemonic":i.mnemonic,"op_str":i.op_str}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    rows=list(csv.DictReader((args.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(args.sections/row["file"]).read_bytes()
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    direct=[]
    for pc in range(0,len(data)-4,2):
        i=one(md,data,pc)
        if not i or i.mnemonic not in ("bl","blx"):continue
        try:ops=list(i.operands)
        except Exception:continue
        if ops and ops[0].type==ARM_OP_IMM and (int(ops[0].imm)&0xfffffffe)==TARGET:
            direct.append(pc)

    ptr_literals=[]
    for val in PTRS:
        needle=struct.pack("<I",val)
        pos=0
        while True:
            q=data.find(needle,pos)
            if q<0:break
            ptr_literals.append({"offset":q,"value":val});pos=q+1

    literal_xrefs=[]
    for item in ptr_literals:
        lit=item["offset"]
        for pc in range(max(0,lit-0x20000)&~1,min(len(data)-4,lit+0x200),2):
            i=one(md,data,pc)
            if not i:continue
            try:ops=list(i.operands)
            except Exception:continue
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pool=((pc+4)&~3)+int(op.mem.disp)
                    if pool==lit:
                        literal_xrefs.append({"pc":pc,"literal":lit,"value":item["value"],"ins":fmt(i)})
                        break

    contexts=[]
    sites=sorted(set(direct+[x["pc"] for x in literal_xrefs]))
    for pc in sites:
        start=prologue(md,data,pc)
        ins=[]
        for x in range(max(0,pc-CTX)&~1,min(len(data)-4,pc+CTX),2):
            i=one(md,data,x)
            if i:ins.append(fmt(i))
        contexts.append({
            "site":hex(pc),
            "kind":["direct_bl" if pc in direct else None,
                    "literal_xref" if any(x["pc"]==pc for x in literal_xrefs) else None],
            "nearest_prologue":None if start is None else hex(start),
            "instructions":ins,
            "strings":strings(data,(start if start is not None else pc)-0x200,pc+0x500),
        })

    # Also scan for compact-ABI-sized copies/memcpy-like immediates near call sites.
    abi_hints=[]
    for c in contexts:
        hints=[]
        for i in c["instructions"]:
            s=(i["mnemonic"]+" "+i["op_str"]).lower()
            if "#0x4e" in s or "#0x4c" in s or "#0x50" in s or "#0x48" in s:
                hints.append(i)
        if hints:abi_hints.append({"site":c["site"],"hints":hints})

    result={
      "schema":"M10R_SAM7_CHROMA_SUPPRESS_CALLERS1D_V1",
      "target":hex(TARGET),
      "direct_call_sites":[hex(x) for x in direct],
      "function_pointer_literals":[{"offset":hex(x["offset"]),"value":hex(x["value"])} for x in ptr_literals],
      "function_pointer_xrefs":[{"pc":hex(x["pc"]),"literal":hex(x["literal"]),"value":hex(x["value"]),"ins":x["ins"]} for x in literal_xrefs],
      "contexts":contexts,
      "compact_abi_hints":abi_hints,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({
      "direct_call_sites":result["direct_call_sites"],
      "function_pointer_literals":result["function_pointer_literals"],
      "function_pointer_xrefs":result["function_pointer_xrefs"],
      "compact_abi_hints":result["compact_abi_hints"]
    },indent=2))
    for c in contexts:
        print("\n=== SITE",c["site"],"FUNC",c["nearest_prologue"],"===")
        for s in c["strings"]:
            if any(k in s["text"].lower() for k in ("b2y","chroma","color","sat","hue","phase","ctrl","suppress")):
                print("STR",s["offset"],s["text"])
        for i in c["instructions"]:
            print(f"{i['address']}: {i['mnemonic']:8s} {i['op_str']}")
if __name__=="__main__":main()
