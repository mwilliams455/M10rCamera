#!/usr/bin/env python3
"""Recover SAM7 Im_B2Y_Ctrl_Chroma_Suppress ownership of page 0x20021100."""
from __future__ import annotations
import argparse,csv,struct,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_OP_REG,ARM_OP_IMM,ARM_REG_PC

PAGE=0x20021100
DIAG=b"Im_B2Y_Ctrl_Chroma_Suppress error."

def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def md():
    m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);m.detail=True;return m

def refs(data,lit):
    m=md();out=[]
    lo=max(0,lit-0x20000)&~1; hi=min(len(data)-4,lit+0x400)
    for off in range(lo,hi,2):
        ins=next(m.disasm(data[off:off+4],off,count=1),None)
        if ins is None: continue
        try: ops=list(ins.operands)
        except Exception: continue
        for op in ops:
            if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                if ((off+4)&~3)+int(op.mem.disp)==lit:
                    out.append((off,ins));break
    return out

def func_start(data,ref):
    m=md();best=None
    for off in range(max(0,ref-0x1000)&~1,ref+1,2):
        ins=next(m.disasm(data[off:off+4],off,count=1),None)
        if ins and ins.mnemonic=="push" and "lr" in ins.op_str: best=off
    return best

def disfunc(data,start,maxlen=0x1800):
    m=md();out=[];off=start;seen=set();limit=min(len(data),start+maxlen)
    while off<limit and off not in seen:
        seen.add(off)
        ins=next(m.disasm(data[off:off+4],off,count=1),None)
        if ins is None: break
        out.append(ins)
        if len(out)>4 and ((ins.mnemonic=="pop" and "pc" in ins.op_str) or (ins.mnemonic=="bx" and ins.op_str.strip()=="lr")):
            break
        # Follow unconditional branch-over-literal-pool jumps on the main path.
        if ins.mnemonic=="b":
            try:
                ops=list(ins.operands)
                if ops and ops[0].type==ARM_OP_IMM:
                    target=int(ops[0].imm)
                    if start<=target<limit:
                        off=target
                        continue
            except Exception:
                pass
        off+=ins.size
    return out

def fmt_ins(ins):
    return f"0x{ins.address:06x}: {ins.mnemonic:8s} {ins.op_str}"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path)
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open(encoding="utf-8")))
    row=next(r for r in rows if r["name"]=="IMG-SAM7")
    data=(a.sections/row["file"]).read_bytes()
    diag=[];p=0
    while True:
        q=data.find(DIAG,p)
        if q<0:break
        diag.append(q);p=q+1
    lits=[]
    needle=struct.pack("<I",PAGE)
    p=0
    while True:
        q=data.find(needle,p)
        if q<0:break
        lits.append(q);p=q+1

    funcs=[]
    for lit in lits:
        rr=refs(data,lit)
        for ref,ldr in rr:
            start=func_start(data,ref)
            insns=disfunc(data,start) if start is not None else []
            dist=min((abs(x-start) for x in diag),default=None) if start is not None else None
            funcs.append({
              "literal_offset":hex(lit),"xref":hex(ref),"function_start":None if start is None else hex(start),
              "diag_distance_from_start":dist,
              "instructions":[fmt_ins(x) for x in insns],
            })

    result={
      "schema":"M10R_SAM7_CHROMA_SUPPRESS1A_V1",
      "sam7_file":row["file"],"sam7_size":len(data),
      "diag_offsets":[hex(x) for x in diag],
      "page":"0x20021100","page_literal_offsets":[hex(x) for x in lits],
      "functions":funcs,
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("DIAG",result["diag_offsets"])
    print("PAGE_LITERALS",result["page_literal_offsets"])
    for f in funcs:
        print("\nFUNCTION",f["function_start"],"XREF",f["xref"],"LIT",f["literal_offset"],"DIAG_DIST",f["diag_distance_from_start"])
        for line in f["instructions"]:print(line)

if __name__=="__main__":main()
