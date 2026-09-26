#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from collections import deque
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC

ENTRY=0x51f1a
LO=0x51f1a
HI=0x5223e
STR_SUB=b"Im_B2Y_Ctrl_Chroma_Suppress"
PAGE=0x20021100

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def one(md,data,pc):
    return next(md.disasm(data[pc:pc+4],pc,count=1),None)

def branch_target(i):
    try: ops=list(i.operands)
    except Exception: return None
    if ops and ops[-1].type==ARM_OP_IMM:
        return int(ops[-1].imm)&0xffffffff
    return None

def is_ret(i):
    return (i.mnemonic=="pop" and "pc" in i.op_str) or (i.mnemonic in ("bx","bxj") and i.op_str.strip()=="lr")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    inside=data.find(STR_SUB); run=inside
    while run>0 and 32<=data[run-1]<127:run-=1

    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    q=deque([ENTRY]);seen_blocks=set();reachable={}
    edges=[];calls=[];page_refs=[];string_refs=[]

    while q:
        start=q.popleft()
        if start in seen_blocks or not (LO<=start<HI):continue
        seen_blocks.add(start)
        pc=start
        for _ in range(800):
            if not (LO<=pc<HI):break
            i=one(md,data,pc)
            if not i:break
            if pc in reachable:
                edges.append({"from":hex(start),"to":hex(pc),"kind":"merge"})
                break
            reachable[pc]=i
            try:ops=list(i.operands)
            except Exception:ops=[]
            if i.mnemonic in ("bl","blx"):
                t=branch_target(i)
                if t is not None:calls.append({"pc":hex(pc),"target":hex(t)})
                pc+=i.size;continue
            if i.mnemonic.startswith("adr") and ops and ops[-1].type==ARM_OP_IMM:
                tgt=((pc+4)&~3)+int(ops[-1].imm)
                if abs(tgt-run)<=4 or abs(tgt-inside)<=4:
                    string_refs.append({"pc":hex(pc),"target":hex(tgt)})
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pool=((pc+4)&~3)+int(op.mem.disp);v=u32(data,pool)
                    if v==PAGE:page_refs.append({"pc":hex(pc),"pool":hex(pool)})
            if is_ret(i):break
            mn=i.mnemonic
            if mn in ("cbz","cbnz"):
                t=branch_target(i)
                if t is not None and LO<=t<HI:
                    q.append(t);edges.append({"from":hex(pc),"to":hex(t),"kind":mn})
                pc+=i.size;continue
            if mn=="b":
                t=branch_target(i)
                if t is not None and LO<=t<HI:
                    q.append(t);edges.append({"from":hex(pc),"to":hex(t),"kind":"b"})
                break
            if mn.startswith("b") and mn not in ("bl","blx","bx","bxj"):
                t=branch_target(i)
                if t is not None and LO<=t<HI:
                    q.append(t);edges.append({"from":hex(pc),"to":hex(t),"kind":mn})
                pc+=i.size;continue
            pc+=i.size

    rowsout=[]
    for pc in sorted(reachable):
        i=reachable[pc];x={"address":hex(pc),"mnemonic":i.mnemonic,"op_str":i.op_str}
        extra=[]
        try:ops=list(i.operands)
        except Exception:ops=[]
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                pool=((pc+4)&~3)+int(op.mem.disp);v=u32(data,pool)
                if v is not None:x.setdefault("literals",[]).append({"pool":hex(pool),"value":hex(v)})
        if i.mnemonic.startswith("adr") and ops and ops[-1].type==ARM_OP_IMM:
            x["adr_target"]=hex(((pc+4)&~3)+int(ops[-1].imm))
        rowsout.append(x)

    result={"schema":"M10R_SAM7_CHROMA_SUPPRESS_CFG1C_V1","entry":hex(ENTRY),
      "string_sub_offset":hex(inside),"string_run_start":hex(run),
      "reachable_instruction_count":len(rowsout),"reachable_min":hex(min(reachable)) if reachable else None,
      "reachable_max":hex(max(reachable)) if reachable else None,
      "reaches_main_programmer":all(x in reachable for x in (0x52038,0x52110,0x5221e)),
      "reaches_error_tail":any(0x52226<=x<=0x5223c for x in reachable),
      "page_refs":page_refs,"string_refs":string_refs,"calls":calls,"edges":edges,"instructions":rowsout}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("entry","reachable_instruction_count","reachable_min","reachable_max","reaches_main_programmer","reaches_error_tail","page_refs","string_refs","calls")},indent=2))
    print("\n=== REACHABLE CODE ===")
    for x in rowsout:
        pc=int(x["address"],16)
        if pc<0x51f90 or pc>=0x52210 or pc in (0x52038,0x52048,0x52110,0x52144):
            ex=[]
            if "literals" in x:ex+=["LIT "+",".join(z["pool"]+"->"+z["value"] for z in x["literals"])]
            if "adr_target" in x:ex+=["ADR "+x["adr_target"]]
            print(f"{pc:#08x}: {x['mnemonic']:8s} {x['op_str']}"+((" ; "+" ; ".join(ex)) if ex else ""))
if __name__=="__main__":main()
