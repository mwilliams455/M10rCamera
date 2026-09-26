#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path

from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE

RIDS=(0x13,0x14,0x15,0x17)
NAMES={0x13:"color_dif_lpf_A",0x14:"unknown_page21000",0x15:"colorcorrection0_A",0x17:"post_processing_filter"}
LABELS=("M10R-20.20.47.37","M10M-2.12.8.0","M10M-3.21.2.50")

def sha(b):return hashlib.sha256(b).hexdigest()
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def s32(v):return v-0x100000000 if v&0x80000000 else v
def spec(s):
    p=s.split("|",4)
    if len(p)!=5:raise ValueError("--item LABEL|B2Y|FW_SHA|DEC_SHA|IDENT")
    return p[0],Path(p[1]),p[2],p[3],p[4]
def keystr(raw):return raw.split(b"\0",1)[0].decode("latin1","replace")
def scope(k):
    if k.startswith("_B2YMODE:STILLLINK"):return "STILLLINK"
    if k.startswith("_B2YMODE:STILL"):return "STILL"
    if k.startswith("_B2YMODE:SLIVE"):return "SLIVE"
    if k.startswith("_B2YMODE:SMAGNI"):return "SMAGNI"
    if k.startswith("_B2YMODE:"):return "OTHER_B2YMODE"
    return "OTHER"

def load(label,path,fw,dec,ident):
    data=path.read_bytes();recs=parse_records(data)
    blocks={}
    for rid in RIDS:
        rows=[];ordn=0
        for r in recs:
            if r.record_id!=rid:continue
            h=RECORD_HEADER_OFF+r.index*RECORD_STRIDE;n=u32(data,h+0x0c)
            keys=[]
            for i in range(n):
                off=h+0x10+i*0x40;keys.append(keystr(data[off:off+0x40]))
            p=data[r.payload_offset:r.payload_offset+r.size]
            words=[u32(p,o) for o in range(0,len(p)//4*4,4)]
            rows.append({
              "ordinal":ordn,"table_index":r.index,"payload_offset":hex(r.payload_offset),
              "size":r.size,"sha256":sha(p),"keys":keys,
              "scopes":dict(Counter(scope(k) for k in keys)),
              "u32_words":words,"s32_words":[s32(x) for x in words],
              "payload_hex":p.hex()
            });ordn+=1
        blocks[hex(rid)]=rows
    return {"label":label,"fw_sha256":fw,"decoded_sha256":dec,"identification":ident,
            "b2y_sha256":sha(data),"records":blocks}

def first_map(rows):
    d=defaultdict(list)
    for r in rows:
        for k in r["keys"]:d[k].append(r)
    return {k:v[0] for k,v in d.items()},{k:v for k,v in d.items() if len(v)>1}

def stat(vals):
    p=[v for v in vals.values() if v is not None]
    if len(p)!=len(vals):return "missing_or_added"
    return "exact_equal" if len(set(p))==1 else "changed"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True);ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args();ss=[spec(x) for x in a.item]
    if tuple(x[0] for x in ss)!=LABELS:raise SystemExit("unexpected labels/order")
    items={x[0]:load(*x) for x in ss}
    comparisons={};summary={}

    for rid in RIDS:
        rk=hex(rid);maps={};dups={}
        for lab in LABELS:maps[lab],dups[lab]=first_map(items[lab]["records"][rk])
        keys=sorted(set().union(*(set(x) for x in maps.values())))
        rows=[]
        for k in keys:
            vals={};by={}
            for lab in LABELS:
                r=maps[lab].get(k);vals[lab]=None if r is None else r["sha256"]
                by[lab]=None if r is None else {
                    "ordinal":r["ordinal"],"table_index":r["table_index"],
                    "size":r["size"],"sha256":r["sha256"],
                    "u32_words":r["u32_words"],"s32_words":r["s32_words"]
                }
            rows.append({"key":k,"scope":scope(k),"status":stat(vals),"by_firmware":by})
        comparisons[rk]=rows
        sc=defaultdict(Counter);tot=Counter()
        for x in rows:sc[x["scope"]][x["status"]]+=1;tot[x["scope"]]+=1
        still=[x for x in rows if x["scope"]=="STILL"]
        summary[rk]={
          "name":NAMES[rid],
          "record_counts":{lab:len(items[lab]["records"][rk]) for lab in LABELS},
          "union_key_count":len(rows),"scope_totals":dict(tot),
          "scope_counts":{k:dict(v) for k,v in sc.items()},
          "still_key_count":len(still),
          "still_changed":sum(x["status"]=="changed" for x in still),
          "still_missing_or_added":sum(x["status"]=="missing_or_added" for x in still),
          "still_exact_equal":sum(x["status"]=="exact_equal" for x in still),
          "duplicate_key_warnings":{lab:{k:[r["ordinal"] for r in v] for k,v in dups[lab].items()} for lab in LABELS},
        }

    result={"schema":"M10R_B2Y_COLORCANDIDATES1A_V1","labels":list(LABELS),
      "record_names":{hex(k):v for k,v in NAMES.items()},"items":items,
      "comparisons":comparisons,"summary":summary,
      "guardrails":["Exact key matching is used for repeated records.","No renderer changes are made.","Changed calibration is not automatically interpreted as pixel arithmetic."]}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")

    L=["# M10-R B2Y COLOR CANDIDATES1A","",
       "Key-aware cross-model audit of the remaining near-color B2Y records 0x13, 0x14, 0x15 and 0x17.",""]
    for rid in RIDS:
        rk=hex(rid);s=summary[rk]
        L += [f"## {rk} {s['name']}","",
              f"- Record counts: {s['record_counts']}",
              f"- Union keys: **{s['union_key_count']}**",
              f"- STILL: exact={s['still_exact_equal']}, changed={s['still_changed']}, missing/added={s['still_missing_or_added']}","",
              "| STILL key | Status | M10-R ord | M10M 2.12 ord | M10M 3.21 ord |",
              "|---|---|---:|---:|---:|"]
        for x in comparisons[rk]:
            if x["scope"]!="STILL":continue
            vals=[]
            for lab in LABELS:
                z=x["by_firmware"][lab];vals.append("-" if z is None else str(z["ordinal"]))
            L.append(f"| {x['key']} | {x['status']} | {vals[0]} | {vals[1]} | {vals[2]} |")
        L += ["","Representative M10-R occurrences:","",
              "| Ord | Size | Keys | First 12 signed words |",
              "|---:|---:|---|---|"]
        for r in items[LABELS[0]]["records"][rk]:
            ks=", ".join(r["keys"][:5])+(" ..." if len(r["keys"])>5 else "")
            L.append(f"| {r['ordinal']} | {r['size']} | {ks} | {r['s32_words'][:12]} |")
        L.append("")
    L += ["## Interpretation boundary","",
          "This pass only identifies model/version-specific key-resolved calibration. Selector identities and hardware fields must be recovered before any renderer experiment.",""]
    a.report.write_text("\n".join(L))
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
