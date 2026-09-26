#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE

LABELS=("M10R-30.22.23.34","M10-3.22.23.38","M10P-4.22.23.34")
KEY="_B2YMODE:STILL_CONTRAST:MEDIUM"
ACTIVE=0xA000

def sha(b):return hashlib.sha256(b).hexdigest()
def u32(b,o):return struct.unpack_from("<I",b,o)[0]

def keys(data,rec):
    h=RECORD_HEADER_OFF+rec.index*RECORD_STRIDE
    n=u32(data,h+0x0c);out=[]
    for i in range(n):
        raw=data[h+0x10+i*0x40:h+0x10+(i+1)*0x40]
        out.append(raw.split(b"\0",1)[0].decode("latin1","replace"))
    return out

def select(data,rid):
    hits=[]
    for r in parse_records(data):
        if r.record_id==rid and KEY in keys(data,r):
            hits.append(r)
    if len(hits)!=1:raise RuntimeError(f"{rid:#x} {KEY}: {len(hits)} hits")
    r=hits[0]
    return r,data[r.payload_offset:r.payload_offset+r.size]

def runs(offsets):
    if not offsets:return []
    out=[];s=p=offsets[0]
    for x in offsets[1:]:
        if x==p+1:p=x;continue
        out.append([s,p]);s=p=x
    out.append([s,p]);return out

def descriptor_decode(b):
    def get32(o):return u32(b,o) if o+4<=len(b) else None
    def get16(o):return struct.unpack_from("<H",b,o)[0] if o+2<=len(b) else None
    return {
      "size":len(b),
      "enable_u8":b[0] if b else None,
      "field_04_u32":get32(4),
      "resolution_code_08_u8":b[8] if len(b)>8 else None,
      "mode_0c_u32":get32(0x0c),
      "field_14_u16":get16(0x14),
      "field_18_u8":b[0x18] if len(b)>0x18 else None,
      "limits_78_94_u16":[get16(o) for o in range(0x78,0x96,2) if o+2<=len(b)],
      "tail_a0_end_hex":b[0xa0:].hex() if len(b)>0xa0 else "",
    }

def table_stats(blob):
    active=blob[:ACTIVE]
    if len(active)<ACTIVE:raise RuntimeError(f"tone table too short {len(blob):#x}")
    vals=list(struct.unpack("<10240I",active))
    return {
      "record_size":len(blob),"active_sha256":sha(active),"full_sha256":sha(blob),
      "min":min(vals),"max":max(vals),"unique":len(set(vals)),
      "first16":vals[:16],"last16":vals[-16:],
    },vals

def curve(vals):
    return [(x*vals[x>>1])>>15 for x in range(0x5000)]

def load(label,path):
    data=Path(path).read_bytes()
    r8,b8=select(data,0x08);r19,b19=select(data,0x19);r1a,b1a=select(data,0x1a)
    s19,v19=table_stats(b19);s1a,v1a=table_stats(b1a)
    return {
      "label":label,"b2y_sha256":sha(data),
      "descriptor":{"table_index":r8.index,"sha256":sha(b8),"hex":b8.hex(),"decoded":descriptor_decode(b8)},
      "tbl0":{"table_index":r19.index,**s19},
      "tbl1":{"table_index":r1a.index,**s1a},
      "tbl0_tbl1_active_equal":v19==v1a,
      "_tbl0_values":v19,
    }

def compare(a,b):
    ba=bytes.fromhex(a["descriptor"]["hex"]);bb=bytes.fromhex(b["descriptor"]["hex"])
    n=min(len(ba),len(bb));offs=[i for i in range(n) if ba[i]!=bb[i]]
    va=a["_tbl0_values"];vb=b["_tbl0_values"]
    idx=[i for i,(x,y) in enumerate(zip(va,vb)) if x!=y]
    ca,cb=curve(va),curve(vb)
    cd=[abs(x-y) for x,y in zip(ca,cb)]
    return {
      "descriptor_common_prefix_diff_byte_count":len(offs),
      "descriptor_diff_runs":[[hex(x),hex(y)] for x,y in runs(offs)],
      "descriptor_size_a":len(ba),"descriptor_size_b":len(bb),
      "descriptor_extra_a_hex":ba[n:].hex(),"descriptor_extra_b_hex":bb[n:].hex(),
      "tbl0_active_equal":va==vb,
      "tbl0_differing_entries":len(idx),
      "tbl0_first_diff_indices":idx[:32],
      "tbl0_max_abs_q15_gain_delta":max((abs(va[i]-vb[i]) for i in idx),default=0),
      "functional_curve_max_abs_code_delta":max(cd),
      "functional_curve_mean_abs_code_delta":sum(cd)/len(cd),
      "functional_curve_differing_codes":sum(x!=y for x,y in zip(ca,cb)),
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True);ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    specs=[x.split("|",1) for x in a.item]
    if tuple(x[0] for x in specs)!=LABELS:raise SystemExit("label/order mismatch")
    items={label:load(label,path) for label,path in specs}
    comparisons={
      "M10R_vs_M10":compare(items[LABELS[0]],items[LABELS[1]]),
      "M10R_vs_M10P":compare(items[LABELS[0]],items[LABELS[2]]),
      "M10_vs_M10P":compare(items[LABELS[1]],items[LABELS[2]]),
    }
    clean={lab:{k:v for k,v in it.items() if k!="_tbl0_values"} for lab,it in items.items()}
    result={"schema":"M10R_B2Y_TONEFAMILY1A_V1","key":KEY,"items":clean,"comparisons":comparisons,
      "guardrails":["0x08 is descriptor; 0x19/0x1A are alternate banks of one tone stage.",
                    "Only first 0xA000 bytes per table are active for resolution code 1.",
                    "Functional curve uses frozen first-parity truncating Q15 x>>1 model only.",
                    "No renderer changes."]}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    L=["# M10-R B2Y TONEFAMILY1A","",
       "Focused cross-color-family audit for "+KEY+".",""]
    for lab in LABELS:
        it=clean[lab]
        L += [f"## {lab}","",
          f"- Descriptor size {it['descriptor']['decoded']['size']}; SHA {it['descriptor']['sha256']}",
          f"- Descriptor decoded core: {it['descriptor']['decoded']}",
          f"- TBL0 active SHA {it['tbl0']['active_sha256']}; min/max {it['tbl0']['min']}/{it['tbl0']['max']}",
          f"- TBL1 active SHA {it['tbl1']['active_sha256']}",
          f"- TBL0 == TBL1 active: {it['tbl0_tbl1_active_equal']}",""]
    L += ["## Comparisons",""]
    for name,x in comparisons.items():L.append(f"- {name}: {x}")
    L += ["","## Boundary","",
      "If M10-R differs only in the calibrated Q15 table while the descriptor's already-used core fields match, the current renderer already carries the principal model-specific tone calibration.",
      "Any descriptor-only differences must be mapped to proven hardware semantics before being promoted.",
      ""]
    a.report.write_text("\n".join(L))
    print(json.dumps(comparisons,indent=2))
if __name__=="__main__":main()
