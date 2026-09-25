#!/usr/bin/env python3
"""Cross-firmware M10-R Y BLEND record comparison.

Input: one verified/extracted firmware section directory from tools/m10r_sections.py.
Output: the B2Y record 0x0D and adjacent YC CONVERSION record 0x0C, plus hashes
and duplicate counts. This is calibration provenance only, not ISP pixel arithmetic.
"""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,struct,sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_REG

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def load_module_path(p:Path,name:str):
    s=importlib.util.spec_from_file_location(name,p)
    if s is None or s.loader is None:raise RuntimeError("module spec "+str(p))
    m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def load_parser(repo:Path):
    return load_module_path(repo/"tools"/"m10r_b2y_assets.py","m10r_b2y_assets_crossfw")

def section_rows(secdir:Path):
    with (secdir/"sections.csv").open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))

def find_section(secdir:Path,needle:str)->Path:
    hits=[]
    for r in section_rows(secdir):
        if needle.lower() in (r["name"]+" "+r["file"]).lower():
            hits.append(secdir/r["file"])
    if len(hits)!=1:raise RuntimeError(f"{needle}: expected one section, found {hits}")
    return hits[0]

def find_b2y_section(secdir:Path,mod):
    # Newer firmware carries the full internal path in the section name.
    named=[]
    for r in section_rows(secdir):
        s=(r["name"]+" "+r["file"]).lower()
        if "data/calib/b2y.bin" in s:
            named.append(secdir/r["file"])
    if len(named)==1:
        return named[0], "named_data_calib_B2Y"

    # Early M10-family firmware has generic "Calibration Data" labels. Identify
    # B2Y structurally with the proven parser and the adjacent 0x0C/0x0D ABIs.
    hits=[]
    for r in section_rows(secdir):
        s=(r["name"]+" "+r["file"]).lower()
        if "calibration data" not in s and "calib" not in s:
            continue
        p=secdir/r["file"]
        try:
            data=p.read_bytes()
            recs=mod.parse_records(data)
        except Exception:
            continue
        c0=[x for x in recs if x.record_id==0x0c and x.size==60]
        d0=[x for x in recs if x.record_id==0x0d and x.size==24]
        if len(c0)==1 and len(d0)==1:
            hits.append(p)
    if len(hits)!=1:
        raise RuntimeError(f"structural B2Y identification expected one section, found {hits}")
    return hits[0], "structural_record0C0D_ABI"

def u32s(blob:bytes):return list(struct.unpack("<"+"I"*(len(blob)//4),blob))
def s32(v:int):return v-0x100000000 if v&0x80000000 else v

def all_occ(data:bytes,needle:bytes):
    out=[];p=0
    while True:
        i=data.find(needle,p)
        if i<0:return out
        out.append(i);p=i+1

def locate_yblend_selector(img:bytes):
    """Locate the Y BLEND selector from its own diagnostic ADR and recover D4480 target."""
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    strings=all_occ(img,b"Y BLEND     String:%s")
    if len(strings)!=1:
        raise RuntimeError(f"expected one Y BLEND label, found {strings}")
    s_off=strings[0]
    adr_hits=[]
    for pc in range(max(0,s_off-0x100),s_off,2):
        xs=list(md.disasm(img[pc:pc+4],pc,count=1))
        if not xs: continue
        i=xs[0]
        if i.mnemonic=="adr" and len(i.operands)>=2 and i.operands[1].type==ARM_OP_IMM:
            target=((pc+4)&~3)+i.operands[1].imm
            if target==s_off:
                adr_hits.append(pc)
    if len(adr_hits)!=1:
        raise RuntimeError(f"Y BLEND ADR hits {adr_hits}")
    adr=adr_hits[0]

    ins={}
    for pc in range(max(0,adr-0x40),min(len(img)-4,adr+0x60),2):
        xs=list(md.disasm(img[pc:pc+4],pc,count=1))
        if xs: ins[pc]=xs[0]

    rid=None; lookup=None
    for pc in range(adr,min(adr+0x20,len(img)-4),2):
        i=ins.get(pc)
        if not i or i.mnemonic!="movs" or len(i.operands)<2: continue
        if i.operands[0].type==ARM_OP_REG and i.reg_name(i.operands[0].reg)=="r1" and i.operands[1].type==ARM_OP_IMM and i.operands[1].imm==0x0d:
            rid=pc
            # canonical next direct BL is record lookup
            for q in range(pc+2,min(pc+10,len(img)-4),2):
                j=ins.get(q)
                if j and j.mnemonic=="bl" and j.operands and j.operands[0].type==ARM_OP_IMM:
                    lookup=(q,j.operands[0].imm); break
            break
    if rid is None or lookup is None:
        raise RuntimeError("could not recover record-0D lookup sequence")

    driver=None
    for pc in range(lookup[0]+2,min(adr+0x40,len(img)-8),2):
        a=ins.get(pc); b=ins.get(pc+2); d=ins.get(pc+4)
        if not (a and b and d): continue
        if a.mnemonic=="movs" and b.mnemonic=="movs" and d.mnemonic=="bl":
            if (len(a.operands)>=2 and len(b.operands)>=2 and
                a.operands[0].type==ARM_OP_REG and a.reg_name(a.operands[0].reg)=="r1" and
                a.operands[1].type==ARM_OP_REG and a.reg_name(a.operands[1].reg)=="r6" and
                b.operands[0].type==ARM_OP_REG and b.reg_name(b.operands[0].reg)=="r0" and
                b.operands[1].type==ARM_OP_REG and b.reg_name(b.operands[1].reg)=="r4" and
                d.operands[0].type==ARM_OP_IMM):
                driver=(pc+4,d.operands[0].imm); break
    if driver is None:
        raise RuntimeError("could not recover Y BLEND driver call")

    func_start=None
    for pc in range(adr,max(-1,adr-0x50),-2):
        i=ins.get(pc)
        if i and i.mnemonic=="push":
            func_start=pc; break
    return {
        "string_offset":s_off,
        "adr_pc":adr,
        "function_start":func_start,
        "record_id_pc":rid,
        "lookup_call_pc":lookup[0],
        "lookup_target":lookup[1],
        "driver_call_pc":driver[0],
        "driver_target":driver[1],
    }

def execute_yblend_driver(img:bytes,repo:Path,driver:int,vals:list[int]):
    audit=load_module_path(repo/"tools"/"m10r_yblend_bit15_audit1a.py","m10r_yblend_bit15_audit1a_crossfw")
    p=audit.Programmer(img)
    old=bytes(0x4000)
    def run(fallback:int):
        got=p.run(driver,struct.pack("<6I",*vals),old,fallback)
        return {
          "0x2002092c":int.from_bytes(got[0x92c:0x930],"little"),
          "0x20020930":int.from_bytes(got[0x930:0x934],"little"),
          "0x20020934":int.from_bytes(got[0x934:0x938],"little"),
        }
    return {"normal":run(0),"fallback":run(1),"bit15_mutations":len(p.bit15_changes)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("repo",type=Path)
    ap.add_argument("--version",required=True)
    ap.add_argument("--firmware-sha256",required=True)
    ap.add_argument("--decoded-sha256",required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()

    mod=load_parser(args.repo)
    b2yp,b2y_identification=find_b2y_section(args.sections,mod)
    imgp=find_section(args.sections,"IMG-System")
    samp=find_section(args.sections,"IMG-SAM7")
    b2y=b2yp.read_bytes();img=imgp.read_bytes();sam=samp.read_bytes()

    records=mod.parse_records(b2y)
    r0d=[r for r in records if r.record_id==0x0d]
    r0c=[r for r in records if r.record_id==0x0c]
    if len(r0d)!=1 or len(r0c)!=1:
        raise RuntimeError(f"unexpected record counts 0D={len(r0d)} 0C={len(r0c)}")
    d=r0d[0];c=r0c[0]
    bd=b2y[d.payload_offset:d.payload_offset+d.size]
    bc=b2y[c.payload_offset:c.payload_offset+c.size]
    if len(bd)%4 or len(bc)%4:raise RuntimeError("non-u32 record length")
    du=u32s(bd);cu=u32s(bc)
    if len(du)!=6:raise RuntimeError(f"record0D length {len(du)}")
    if len(cu)!=15:raise RuntimeError(f"record0C length {len(cu)}")

    yblend_strings=[]
    for needle in (b"Y BLEND",b"y_blend"):
        yblend_strings += [{"needle":needle.decode(),"offset":hex(x)} for x in all_occ(img,needle)]

    selector=locate_yblend_selector(img)
    driver=selector["driver_target"]
    executed=execute_yblend_driver(img,args.repo,driver,du)
    expected_normal={"0x2002092c":0x00002000,"0x20020930":0x3fff3fff,"0x20020934":0x3fff3fff}
    expected_fallback={"0x2002092c":0x00000000,"0x20020930":0x80007fff,"0x20020934":0x80007fff}
    if executed["normal"]!=expected_normal or executed["fallback"]!=expected_fallback:
        raise RuntimeError(f"Y BLEND execution mismatch {executed}")
    if executed["bit15_mutations"]!=0:
        raise RuntimeError(f"unexpected bit15 mutation {executed}")

    result={
      "schema":"M10R_YBLEND_CROSSFIRMWARE1A_ITEM_V1",
      "version":args.version,
      "firmware_sha256":args.firmware_sha256,
      "decoded_sha256":args.decoded_sha256,
      "sections":{
        "b2y_file":b2yp.name,"b2y_identification":b2y_identification,"b2y_sha256":sha(b2y),
        "img_file":imgp.name,"img_sha256":sha(img),
        "sam7_file":samp.name,"sam7_sha256":sha(sam),
      },
      "record_count":len(records),
      "record_0x0d":{
        "index":d.index,"payload_offset":hex(d.payload_offset),"size":d.size,
        "raw_hex":bd.hex(),"raw_sha256":sha(bd),"u32":du,
        "exact_payload_occurrences_in_b2y":[hex(x) for x in all_occ(b2y,bd)],
      },
      "record_0x0c":{
        "index":c.index,"payload_offset":hex(c.payload_offset),"size":c.size,
        "raw_sha256":sha(bc),
        "u32":cu,
        "signed_matrix":[s32(x) for x in cu[:9]],
        "tail_u32":cu[9:],
      },
      "img_yblend_strings":yblend_strings,
      "yblend_selector_driver":{
        **{k:(hex(v) if isinstance(v,int) else v) for k,v in selector.items()},
        "driver_first_0xf0_sha256":sha(img[driver:driver+0xf0]),
        "original_thumb_execution":executed,
      },
      "guardrails":[
        "Cross-version calibration equality constrains stability, not field semantics.",
        "A stable value 32 does not establish Q5/Q6 or 0.5.",
        "No pixel arithmetic is inferred by this tool."
      ],
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
