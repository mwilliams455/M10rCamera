#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path

from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE

RID=0x0e
LABELS=("M10R-20.20.47.37","M10M-2.12.8.0","M10M-3.21.2.50")

def sha(b): return hashlib.sha256(b).hexdigest()
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def s32(v): return v-0x100000000 if v&0x80000000 else v
def decode_key(raw): return raw.split(b"\0",1)[0].decode("latin1","replace")

def spec(s):
    p=s.split("|",4)
    if len(p)!=5: raise ValueError("--item LABEL|B2Y|FW_SHA|DEC_SHA|IDENT")
    return p[0],Path(p[1]),p[2],p[3],p[4]

def scope(k):
    if k.startswith("_B2YMODE:STILLLINK"): return "STILLLINK"
    if k.startswith("_B2YMODE:STILL"): return "STILL"
    if k.startswith("_B2YMODE:SLIVE"): return "SLIVE"
    if k.startswith("_B2YMODE:SMAGNI"): return "SMAGNI"
    if k.startswith("_B2YMODE:"): return "OTHER_B2YMODE"
    return "OTHER"

def load(label,path,fw,dec,ident):
    data=path.read_bytes(); recs=parse_records(data); rows=[];ordinal=0
    for r in recs:
        if r.record_id!=RID: continue
        h=RECORD_HEADER_OFF+r.index*RECORD_STRIDE
        n=u32(data,h+0x0c)
        keys=[]
        for i in range(n):
            off=h+0x10+i*0x40
            keys.append(decode_key(data[off:off+0x40]))
        payload=data[r.payload_offset:r.payload_offset+r.size]
        words=[u32(payload,o) for o in range(0,len(payload)//4*4,4)]
        rows.append({
          "ordinal":ordinal,"table_index":r.index,"payload_offset":hex(r.payload_offset),
          "size":r.size,"payload_sha256":sha(payload),"payload_hex":payload.hex(),
          "u32_words":words,"s32_words":[s32(x) for x in words],
          "key_count":n,"keys":keys,"key_scopes":dict(Counter(scope(k) for k in keys)),
        })
        ordinal+=1
    return {"label":label,"firmware_sha256":fw,"decoded_sha256":dec,
            "b2y_identification":ident,"b2y_sha256":sha(data),"records":rows}

def first_map(rows):
    out=defaultdict(list)
    for r in rows:
        for k in r["keys"]: out[k].append(r)
    return {k:v[0] for k,v in out.items()}, {k:v for k,v in out.items() if len(v)>1}

def status(vals):
    p=[v for v in vals.values() if v is not None]
    if len(p)!=len(vals): return "missing_or_added"
    return "exact_equal" if len(set(p))==1 else "changed"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    ss=[spec(x) for x in a.item]
    if tuple(x[0] for x in ss)!=LABELS: raise SystemExit("unexpected labels/order")
    items={x[0]:load(*x) for x in ss}
    maps={};dups={}
    for lab in LABELS: maps[lab],dups[lab]=first_map(items[lab]["records"])
    keys=sorted(set().union(*(set(m) for m in maps.values())))
    rows=[]
    for k in keys:
        by={};vals={}
        for lab in LABELS:
            r=maps[lab].get(k)
            by[lab]=None if r is None else {
              "ordinal":r["ordinal"],"table_index":r["table_index"],
              "payload_sha256":r["payload_sha256"],"size":r["size"],
              "u32_words":r["u32_words"],"s32_words":r["s32_words"]
            }
            vals[lab]=None if r is None else r["payload_sha256"]
        rows.append({"key":k,"scope":scope(k),"status":status(vals),"by_firmware":by})

    sc=defaultdict(Counter);tot=Counter()
    for x in rows:
        sc[x["scope"]][x["status"]]+=1;tot[x["scope"]]+=1

    still=[x for x in rows if x["scope"]=="STILL"]
    changed_still=[x for x in still if x["status"]!="exact_equal"]

    result={
      "schema":"M10R_B2Y_OFFSET_CROSSMODEL1A_V1",
      "record_id":"0x0e","selector":"offset",
      "lookup_semantics":"table-order record-id match then exact 64-byte key match; first match wins",
      "items":items,"comparisons":rows,
      "summary":{
        "record_counts":{lab:len(items[lab]["records"]) for lab in LABELS},
        "union_key_count":len(rows),
        "scope_totals":dict(tot),
        "scope_counts":{k:dict(v) for k,v in sc.items()},
        "still_key_count":len(still),
        "changed_or_missing_still_keys":len(changed_still),
        "duplicate_key_warnings":{lab:{k:[r["ordinal"] for r in v] for k,v in dups[lab].items()} for lab in LABELS},
      },
      "guardrails":[
        "Key-aware matching supersedes occurrence ordinal for repeated 0x0e records.",
        "Whole-record differences are not interpreted as pixel arithmetic.",
        "No renderer changes are made by this pass."
      ]
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")

    L=["# M10-R B2Y OFFSET CROSSMODEL1A","",
       "Key-aware cross-model audit of record 0x0E (offset).","",
       "## Summary","",
       f"- Record counts: {result['summary']['record_counts']}",
       f"- Union keys: **{len(rows)}**",
       f"- STILL keys: **{len(still)}**",
       f"- STILL keys changed/missing across models: **{len(changed_still)}**","",
       "## STILL keys","",
       "| Key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |",
       "|---|---|---:|---:|---:|"]
    for x in still:
        vals=[]
        for lab in LABELS:
            z=x["by_firmware"][lab]
            vals.append("-" if z is None else str(z["ordinal"]))
        L.append(f"| {x['key']} | {x['status']} | {vals[0]} | {vals[1]} | {vals[2]} |")
    L += ["","## Record inventory","",
          "| Firmware | Ordinal | Keys | SHA256 | First 8 signed words |",
          "|---|---:|---|---|---|"]
    for lab in LABELS:
        for r in items[lab]["records"]:
            ks=", ".join(r["keys"][:4])+(" ..." if len(r["keys"])>4 else "")
            L.append(f"| {lab} | {r['ordinal']} | {ks} | {r['payload_sha256']} | {r['s32_words'][:8]} |")
    L += ["","## Next","",
          "Map the key-resolved M10-R STILL payload(s) through setter 0x140154 and determine whether the effective fields are chroma/color offsets, luma offsets, or another B2Y state. Keep renderer frozen.",""]
    a.report.write_text("\n".join(L))
    print(json.dumps(result["summary"],indent=2))
    for x in changed_still[:80]:
        print(x["status"],x["key"])
if __name__=="__main__":main()
