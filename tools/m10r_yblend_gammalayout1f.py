#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from pathlib import Path

DIFF_BASE=0x20A40000
DIFF_STRIDE=0x8000
FULL_BASE=0x20A68000
FULL_STRIDE=0x1000
COUNT=5

def u32le(x:int)->bytes:return struct.pack("<I",x)

def all_hits(data:bytes,needle:bytes):
    out=[];p=0
    while True:
        q=data.find(needle,p)
        if q<0:return out
        out.append(q);p=q+1

def main():
    ap=argparse.ArgumentParser();ap.add_argument("sections",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rows=list(csv.DictReader((a.sections/"sections.csv").open(encoding="utf-8")))
    slots=[]
    for family,base,stride in (("diff",DIFF_BASE,DIFF_STRIDE),("full",FULL_BASE,FULL_STRIDE)):
        for idx in range(COUNT):
            addr=base+idx*stride
            hits=[]
            for r in rows:
                p=a.sections/r["file"]
                try:data=p.read_bytes()
                except Exception:continue
                for off in all_hits(data,u32le(addr)):
                    hits.append({"section":r["name"],"file":r["file"],"offset":hex(off)})
            slots.append({"family":family,"index":idx,"address":hex(addr),"hits":hits})

    # Scan all literal values within the hypothesized two contiguous regions.
    range_hits=[]
    lo=DIFF_BASE; hi=FULL_BASE+COUNT*FULL_STRIDE
    for r in rows:
        p=a.sections/r["file"]
        try:data=p.read_bytes()
        except Exception:continue
        for off in range(0,len(data)-3,4):
            v=struct.unpack_from("<I",data,off)[0]
            if lo<=v<hi and (v&0xfff)==0:
                range_hits.append({"section":r["name"],"offset":hex(off),"value":hex(v)})
    result={
      "schema":"M10R_YBLEND_GAMMALAYOUT1F_V1",
      "hypothesis":{
        "diff_base":hex(DIFF_BASE),"diff_stride":hex(DIFF_STRIDE),
        "full_base":hex(FULL_BASE),"full_stride":hex(FULL_STRIDE),"slot_count":COUNT,
        "reason":"0x20A68000 - 0x20A40000 == 5*0x8000"
      },
      "slots":slots,
      "aligned_literals_in_combined_region":range_hits,
      "summary":{
        "populated_literal_slots":[f"{x['family']}:{x['index']}" for x in slots if x["hits"]],
        "all_exact_slot_addresses":[x["address"] for x in slots],
      },
      "boundary":"Literal absence does not prove a hardware slot is unused if address arithmetic or broadcast/common-table selection is used."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["summary"],indent=2))
    for x in slots:
        print(x["family"],x["index"],x["address"],"hits",len(x["hits"]),x["hits"][:12])
    print("RANGE_LITERALS",json.dumps(range_hits[:200],indent=2))
if __name__=="__main__":main()
