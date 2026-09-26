#!/usr/bin/env python3
"""DGDISPATCH1Q: bounded static search for M10-R SAM7 Im_B2Y_Set_DGamma_Table dispatch.

Searches every extracted firmware section for:
- exact raw function offsets 0x526bc / Thumb pointer 0x526bd;
- any aligned 32-bit word whose low 20 bits equal those offsets;
- ASCII DGamma API-name occurrences;
- direct Thumb/ARM immediate branch calls in the SAM7 image;
- BLX-register sites with bounded backward literal-load evidence.

Absence remains a bounded negative result; it does not exclude runtime RPC,
relocation, dynamically built vectors, or computed function pointers.
"""
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM,ARM_OP_REG,ARM_OP_MEM,ARM_REG_PC

TARGET=0x526bc
THUMB_PTR=TARGET|1

def u32(data,o):
    return struct.unpack_from("<I",data,o)[0] if 0<=o<=len(data)-4 else None

def all_bytes(data,needle):
    out=[];p=0
    while True:
        q=data.find(needle,p)
        if q<0:return out
        out.append(q);p=q+1

def ascii_hits(data,needle=b"DGamma"):
    out=[];p=0
    while True:
        q=data.find(needle,p)
        if q<0:return out
        lo=q
        while lo>0 and 32<=data[lo-1]<127:lo-=1
        hi=q
        while hi<len(data) and 32<=data[hi]<127:hi+=1
        out.append({"offset":hex(q),"string":data[lo:hi].decode("ascii","replace")})
        p=q+1
    return out

def direct_calls(data,mode,label):
    md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
    out=[]
    # Decode from both halfword phases for Thumb; word phases for ARM.
    phases=(0,2) if label=="THUMB" else (0,)
    for phase in phases:
        for ins in md.disasm(data[phase:],phase):
            if ins.mnemonic not in ("bl","blx"):continue
            ops=getattr(ins,"operands",[])
            if ops and ops[0].type==ARM_OP_IMM:
                dst=int(ops[0].imm)&0xffffffff
                if dst in (TARGET,THUMB_PTR):
                    out.append({"isa":label,"pc":hex(ins.address),"target":hex(dst),"bytes":ins.bytes.hex(),"op_str":ins.op_str})
    # de-dupe
    seen=set();r=[]
    for x in out:
        k=(x["isa"],x["pc"])
        if k not in seen:seen.add(k);r.append(x)
    return r

def bounded_blx_reg(data):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
    ins=list(md.disasm(data,0))
    out=[]
    for i,x in enumerate(ins):
        if x.mnemonic!="blx":continue
        ops=getattr(x,"operands",[])
        if not ops or ops[0].type!=ARM_OP_REG:continue
        reg=ops[0].reg
        evidence=[]
        for y in ins[max(0,i-20):i]:
            yo=getattr(y,"operands",[])
            if not yo or yo[0].type!=ARM_OP_REG or yo[0].reg!=reg:continue
            # PC literal load into call register.
            if y.mnemonic=="ldr" and len(yo)>1 and yo[1].type==ARM_OP_MEM and yo[1].mem.base==ARM_REG_PC:
                base=(y.address+4)&~3;po=base+int(yo[1].mem.disp);v=u32(data,po)
                evidence.append({"pc":hex(y.address),"kind":"pc_literal","pool":hex(po),"value":hex(v) if v is not None else None,
                                 "matches_target":v in (TARGET,THUMB_PTR)})
            if y.mnemonic in ("mov","movs") and len(yo)>1 and yo[1].type==ARM_OP_IMM:
                v=int(yo[1].imm)&0xffffffff
                evidence.append({"pc":hex(y.address),"kind":"imm","value":hex(v),"matches_target":v in (TARGET,THUMB_PTR)})
        if any(e["matches_target"] for e in evidence):
            out.append({"pc":hex(x.address),"reg":md.reg_name(reg),"evidence":evidence})
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args();rows=list(csv.DictReader((a.sections/"sections.csv").open(encoding="utf-8")))
    exact=[];low20=[];names=[]
    sam=None
    for r in rows:
        p=a.sections/r["file"]
        try:data=p.read_bytes()
        except Exception:continue
        if r["name"]=="IMG-SAM7":sam=data
        for val,label in ((TARGET,"entry_even"),(THUMB_PTR,"thumb_ptr")):
            for off in all_bytes(data,struct.pack("<I",val)):
                exact.append({"section":r["name"],"file":r["file"],"offset":hex(off),"value":hex(val),"kind":label,"aligned4":off%4==0})
        # aligned words with matching low 20 bits, catches base-added/aliased pointers.
        for off in range(0,len(data)-3,4):
            v=struct.unpack_from("<I",data,off)[0]
            if (v&0xfffff) in (TARGET,THUMB_PTR):
                low20.append({"section":r["name"],"offset":hex(off),"value":hex(v),"low20":hex(v&0xfffff)})
        for h in ascii_hits(data):
            names.append({"section":r["name"],**h})
    assert sam is not None
    dc=direct_calls(sam,CS_MODE_THUMB,"THUMB")+direct_calls(sam,CS_MODE_ARM,"ARM")
    blx=bounded_blx_reg(sam)
    res={
      "schema":"M10R_YBLEND_DGDISPATCH1Q_V1",
      "target_entry":hex(TARGET),"target_thumb_pointer":hex(THUMB_PTR),
      "exact_pointer_occurrences":exact,
      "aligned_low20_pointer_candidates":low20,
      "dgamma_name_occurrences":names,
      "direct_immediate_calls":dc,
      "bounded_blx_register_target_evidence":blx,
      "boundary":"Static negative evidence cannot exclude external RPC dispatch, relocation records not present in extracted binaries, dynamically built tables, or computed pointers."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(res,indent=2)+"\n")
    print("EXACT",json.dumps(exact,indent=2))
    print("LOW20",json.dumps(low20,indent=2))
    print("NAMES",json.dumps(names,indent=2))
    print("DIRECT",json.dumps(dc,indent=2))
    print("BLX_TARGET",json.dumps(blx,indent=2))
if __name__=="__main__":main()
