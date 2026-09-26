#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from m10r_b2y_assets import parse_records

LABELS=("M10R-20.20.47.37","M10M-2.12.8.0","M10M-3.21.2.50")
FIELDS={
  0x06:[
    ("enable_bit0",0x00,1,0x01),
    ("tail_2c_low8",0x2c,2,0x00ff),
    ("tail_30_low8",0x30,4,0x000000ff),
    ("tail_34_low8",0x34,2,0x00ff),
    ("tail_38_u16",0x38,2,0xffff),
    ("tail_3c_low15",0x3c,2,0x7fff),
  ],
  0x0a:[
    ("enable_bit0",0x00,1,0x01),
    ("tail_2c_low15",0x2c,2,0x7fff),
    ("tail_30_u16",0x30,2,0xffff),
    ("tail_34_low15",0x34,2,0x7fff),
    ("tail_38_u16",0x38,2,0xffff),
    ("tail_3c_low15",0x3c,2,0x7fff),
    ("tail_40_u16",0x40,4,0xffff),
  ],
}
MATRIX_REGION={0x06:(0x08,0x2c),0x0a:(0x08,0x2c)}

def sha(b): return hashlib.sha256(b).hexdigest()
def readv(b,o,w):
    if w==1:return b[o]
    if w==2:return struct.unpack_from("<H",b,o)[0]
    if w==4:return struct.unpack_from("<I",b,o)[0]
    raise ValueError(w)
def s32s(b):
    q=struct.unpack("<"+"I"*(len(b)//4),b[:len(b)//4*4])
    return [x-0x100000000 if x&0x80000000 else x for x in q]
def spec(s):
    p=s.split("|",4)
    if len(p)!=5: raise ValueError("--item LABEL|B2Y|FW_SHA|DEC_SHA|IDENT")
    return p[0],Path(p[1]),p[2],p[3],p[4]
def one_rec(data,rid):
    z=[r for r in parse_records(data) if r.record_id==rid]
    if len(z)!=1: raise RuntimeError(f"record {rid:#x} count {len(z)}")
    r=z[0]; return r,data[r.payload_offset:r.payload_offset+r.size]

def load(label,path,fw,dec,ident):
    data=path.read_bytes()
    out={"label":label,"firmware_sha256":fw,"decoded_sha256":dec,
         "b2y_identification":ident,"b2y_sha256":sha(data),"records":{}}
    for rid in (0x06,0x0a):
        r,b=one_rec(data,rid); lo,hi=MATRIX_REGION[rid]
        fs={}
        for name,o,w,m in FIELDS[rid]:
            raw=readv(b,o,w)
            fs[name]={"offset":hex(o),"width":w,"mask":hex(m),"raw":raw,"effective":raw&m}
        out["records"][hex(rid)]={
          "record_table_index":r.index,"payload_offset":hex(r.payload_offset),"size":r.size,
          "payload_sha256":sha(b),"payload_hex":b.hex(),"s32_words":s32s(b),
          "default_matrix_region":{"offset_range":[hex(lo),hex(hi)],"sha256":sha(b[lo:hi]),"s32":s32s(b[lo:hi])},
          "normal_static_fields":fs,
        }
    return out

def report(d):
    L=["# M10-R B2Y CC-CONTROL CROSSMODEL1A","",
       "Focused comparison of static B2Y CC0 (0x06) and CC1 (0x0A) records.","",
       "## Architectural boundary","",
       "Frozen firmware research proves the normal live helper path takes per-frame matrix coefficients from the CA9-rendered runtime CC object. The static B2Y record contributes the enable bit and tail control/limit fields. Whole-record inequality therefore does not by itself prove a different live color transform.",""]
    for rid,name in ((0x06,"CC0"),(0x0a,"CC1")):
        rk=hex(rid); L += [f"## {rk} {name}","",
          "| Field | M10-R | M10M 2.12.8.0 | M10M 3.21.2.50 | Equal all | M10-R vs latest |",
          "|---|---:|---:|---:|---|---|"]
        for fname,_,_,_ in FIELDS[rid]:
            c=d["comparisons"][rk]["normal_static_fields"][fname]; v=c["values"]
            L.append(f"| {fname} | {v[LABELS[0]]} | {v[LABELS[1]]} | {v[LABELS[2]]} | {c['equal_all']} | {c['m10r_vs_latest_equal']} |")
        m=d["comparisons"][rk]["default_matrix_region"]
        L += ["",f"Default/baseline 3x3-looking region equal across all: **{m['equal_all']}**.",
              f"M10-R vs latest Monochrom default region equal: **{m['m10r_vs_latest_equal']}**.",""]
    L += ["## Decision",""]
    if d["summary"]["all_normal_static_fields_equal_all"]:
        L += ["**All normal-path static CC0/CC1 fields are invariant across the three inputs.**","",
              "The whole-record cross-model differences therefore sit outside the static control/limit fields consumed by the normal live helper path. Deprioritize the static 0x06/0x0A record differences as the explanation for the remaining M10-R skin/color mismatch.",
              "Keep CA9-rendered per-frame CC0/CC1 authoritative and do not add the static matrices as a second transform.",""]
    else:
        L += ["**At least one normal-path static CC0/CC1 field differs across models.**","",
              "Only those differing effective fields remain plausible model-specific B2Y controls; trace their exact MMIO bit semantics before changing the renderer.",""]
    L += ["## Next","",
          "1. If the normal-path static fields are invariant, move priority to changed chroma-shaping records 0x16/0x18 while keeping tone/DG separate.",
          "2. If any live static field differs, trace only that field into its destination register bits.",
          "3. Keep Y_BLEND 0x0D and YC CONVERSION 0x0C as invariant controls.",
          "4. Make no Android renderer change in this pass.",""]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args(); ss=[spec(x) for x in a.item]
    if tuple(x[0] for x in ss)!=LABELS: raise SystemExit("unexpected labels/order")
    items={x[0]:load(*x) for x in ss}
    comps={}; live=[]
    for rid in (0x06,0x0a):
        rk=hex(rid); fc={}
        for fname,_,_,_ in FIELDS[rid]:
            vals={lab:items[lab]["records"][rk]["normal_static_fields"][fname]["effective"] for lab in LABELS}
            c={"values":vals,"equal_all":len(set(vals.values()))==1,
               "m10r_vs_latest_equal":vals[LABELS[0]]==vals[LABELS[2]]}
            fc[fname]=c; live.append(c["equal_all"])
        h={lab:items[lab]["records"][rk]["default_matrix_region"]["sha256"] for lab in LABELS}
        comps[rk]={"normal_static_fields":fc,"default_matrix_region":{
          "hashes":h,"equal_all":len(set(h.values()))==1,
          "m10r_vs_latest_equal":h[LABELS[0]]==h[LABELS[2]]}}
    result={"schema":"M10R_B2Y_CC_CONTROL_CROSSMODEL1A_V1","labels":list(LABELS),
      "items":items,"comparisons":comps,
      "summary":{"all_normal_static_fields_equal_all":all(live),
        "changed_normal_static_fields":[f"{rk}:{n}" for rk,b in comps.items() for n,c in b["normal_static_fields"].items() if not c["equal_all"]],
        "cc0_default_matrix_equal_all":comps["0x6"]["default_matrix_region"]["equal_all"],
        "cc1_default_matrix_equal_all":comps["0xa"]["default_matrix_region"]["equal_all"]},
      "frozen_references":["research/M10R_v179_b2y_fixed_cc.txt","research/M10R_v185_CA9_RENDERED_CC_TO_B2Y_FROZEN.md","research/M10R_v232_B2Y_CC0_INTERNAL_CC1_OUTPUT_ARCHITECTURE_FROZEN.md"],
      "guardrails":["Static 0x06/0x0A matrices are not applied as a second transform.","CA9-rendered runtime CC0/CC1 remain authoritative.","No renderer changes are made by this audit."]}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n"); a.report.write_text(report(result))
    print(json.dumps(result["summary"],indent=2))
if __name__=="__main__": main()
