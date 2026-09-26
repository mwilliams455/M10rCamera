#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

BASES={
    "IMG-System":0x42000000,
    "IMG-SAM7":0x43000000,
}
TARGETS=[0x20020900,0x2002092c,0x20020930,0x20020934]
PAGE_LO=0x20020900
PAGE_HI=0x20020a00

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def ascii_runs(data,lo,hi,minlen=7):
    out=[];lo=max(0,lo);hi=min(len(data),hi);i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=minlen:
                out.append({"offset":hex(i),"text":data[i:j].decode("ascii","replace")})
            i=j
        else:i+=1
    return out

def find_words(data):
    hits=[]
    for o in range(0,len(data)-3,4):
        v=u32(data,o)
        if v in TARGETS or PAGE_LO<=v<PAGE_HI:
            hits.append({"offset":o,"value":v})
    return hits

def local_xrefs(data,base,pool_off,mode_name):
    mode=CS_MODE_THUMB if mode_name=="THUMB" else CS_MODE_ARM
    md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
    align=2 if mode_name=="THUMB" else 4
    lo=max(0,pool_off-0x1000)
    lo-=lo%align
    hi=min(len(data),pool_off+8)
    out=[]
    # Start at several aligned positions in the preceding window because data/code
    # boundaries can desync a single linear sweep.
    starts=range(lo,min(pool_off,lo+0x100),align)
    seen=set()
    for start in starts:
        for ins in md.disasm(data[start:hi],base+start):
            off=ins.address-base
            if off>pool_off:break
            try:ops=list(ins.operands)
            except Exception:ops=[]
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    if mode_name=="THUMB":
                        pcbase=(ins.address+4)&~3
                    else:
                        pcbase=ins.address+8
                    po=pcbase+int(op.mem.disp)-base
                    if po==pool_off:
                        k=(off,ins.mnemonic,ins.op_str)
                        if k not in seen:
                            seen.add(k)
                            out.append({"pc":hex(off),"mnemonic":ins.mnemonic,"op_str":ins.op_str})
            if off>=pool_off:break
    return sorted(out,key=lambda x:int(x["pc"],16))

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open()))
    result={"schema":"M10R_YBLEND_REGISTERXREF1B_V1","targets":[hex(x) for x in TARGETS],"sections":[]}
    for row in rows:
        p=a.sections/row["file"]
        try:data=p.read_bytes()
        except Exception:continue
        hits=find_words(data)
        if not hits:continue
        name=row["name"]
        base=BASES.get(name)
        sec={"name":name,"file":row["file"],"size":len(data),"hits":[]}
        for h in hits:
            item={"offset":hex(h["offset"]),"value":hex(h["value"]),
                  "nearby_strings":ascii_runs(data,h["offset"]-0x500,h["offset"]+0x500)}
            if base is not None:
                item["thumb_xrefs"]=local_xrefs(data,base,h["offset"],"THUMB")
                item["arm_xrefs"]=local_xrefs(data,base,h["offset"],"ARM")
            sec["hits"].append(item)
        result["sections"].append(sec)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("SECTIONS_WITH_TARGET_WORDS",len(result["sections"]))
    for sec in result["sections"]:
        print("\nSECTION",sec["name"],sec["file"],"hits",len(sec["hits"]))
        for h in sec["hits"]:
            print(" HIT",h["offset"],h["value"])
            for mode in ("thumb_xrefs","arm_xrefs"):
                for x in h.get(mode,[]): print("  ",mode,x)
            for s in h["nearby_strings"]:
                t=s["text"].lower()
                if any(k in t for k in ("blend","b2y","yc","color","chroma","satur","difference","diff")):
                    print("  STRING",s["offset"],s["text"])
if __name__=="__main__":main()
