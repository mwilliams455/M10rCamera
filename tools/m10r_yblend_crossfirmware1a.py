#!/usr/bin/env python3
"""Cross-firmware M10-R Y BLEND record comparison.

Input: one verified/extracted firmware section directory from tools/m10r_sections.py.
Output: the B2Y record 0x0D and adjacent YC CONVERSION record 0x0C, plus hashes
and duplicate counts. This is calibration provenance only, not ISP pixel arithmetic.
"""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,struct,sys
from pathlib import Path

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def load_parser(repo:Path):
    p=repo/"tools"/"m10r_b2y_assets.py"
    s=importlib.util.spec_from_file_location("m10r_b2y_assets_crossfw",p)
    if s is None or s.loader is None:raise RuntimeError("parser spec")
    m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def find_section(secdir:Path,needle:str)->Path:
    hits=[]
    with (secdir/"sections.csv").open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if needle.lower() in (r["name"]+" "+r["file"]).lower():
                hits.append(secdir/r["file"])
    if len(hits)!=1:raise RuntimeError(f"{needle}: expected one section, found {hits}")
    return hits[0]

def u32s(blob:bytes):return list(struct.unpack("<"+"I"*(len(blob)//4),blob))
def s32(v:int):return v-0x100000000 if v&0x80000000 else v

def all_occ(data:bytes,needle:bytes):
    out=[];p=0
    while True:
        i=data.find(needle,p)
        if i<0:return out
        out.append(i);p=i+1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("repo",type=Path)
    ap.add_argument("--version",required=True)
    ap.add_argument("--firmware-sha256",required=True)
    ap.add_argument("--decoded-sha256",required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()

    b2yp=find_section(args.sections,"data/calib/B2Y.bin")
    imgp=find_section(args.sections,"IMG-System")
    samp=find_section(args.sections,"IMG-SAM7")
    b2y=b2yp.read_bytes();img=imgp.read_bytes();sam=samp.read_bytes()

    mod=load_parser(args.repo)
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

    result={
      "schema":"M10R_YBLEND_CROSSFIRMWARE1A_ITEM_V1",
      "version":args.version,
      "firmware_sha256":args.firmware_sha256,
      "decoded_sha256":args.decoded_sha256,
      "sections":{
        "b2y_file":b2yp.name,"b2y_sha256":sha(b2y),
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
