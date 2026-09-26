#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import defaultdict, Counter
from pathlib import Path
from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE

LABELS=("M10R-20.20.47.37","M10M-2.12.8.0","M10M-3.21.2.50")
RIDS=(0x16,0x18)

def sha(b): return hashlib.sha256(b).hexdigest()
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def spec(s):
    p=s.split("|",4)
    if len(p)!=5: raise ValueError("--item LABEL|B2Y|FW_SHA|DEC_SHA|IDENT")
    return p[0],Path(p[1]),p[2],p[3],p[4]
def decode_key(raw):
    z=raw.split(b"\0",1)[0]
    return z.decode("latin1","replace")
def scope(k):
    if k.startswith("_B2YMODE:STILLLINK"): return "STILLLINK"
    if k.startswith("_B2YMODE:STILL"): return "STILL"
    if k.startswith("_B2YMODE:SLIVE"): return "SLIVE"
    if k.startswith("_B2YMODE:SMAGNI"): return "SMAGNI"
    if k.startswith("_B2YMODE:"): return "OTHER_B2YMODE"
    return "OTHER"

def load(label,path,fw,dec,ident):
    data=path.read_bytes(); recs=parse_records(data)
    out={"label":label,"firmware_sha256":fw,"decoded_sha256":dec,
         "b2y_identification":ident,"b2y_sha256":sha(data),"records":{}}
    for rid in RIDS:
        rows=[]
        ordinal=0
        for r in recs:
            if r.record_id!=rid: continue
            h=RECORD_HEADER_OFF+r.index*RECORD_STRIDE
            kc=u32(data,h+0x0c)
            keys=[]
            for i in range(kc):
                off=h+0x10+i*0x40
                keys.append(decode_key(data[off:off+0x40]))
            payload=data[r.payload_offset:r.payload_offset+r.size]
            rows.append({"ordinal":ordinal,"table_index":r.index,"relative_offset":hex(r.rel_offset),
                         "payload_offset":hex(r.payload_offset),"size":r.size,
                         "payload_sha256":sha(payload),"payload_hex":payload.hex(),
                         "key_count":kc,"keys":keys,
                         "key_scopes":dict(Counter(scope(k) for k in keys))})
            ordinal+=1
        out["records"][hex(rid)]=rows
    return out

def first_match_map(rows):
    m=defaultdict(list)
    for row in rows:
        for k in row["keys"]:
            m[k].append(row)
    first={}
    dups={}
    for k,z in m.items():
        first[k]=z[0]
        if len(z)>1:
            dups[k]=[{"ordinal":r["ordinal"],"table_index":r["table_index"],"payload_sha256":r["payload_sha256"]} for r in z]
    return first,dups

def status(vals):
    present=[v for v in vals.values() if v is not None]
    if len(present)!=len(vals): return "missing_or_added"
    return "exact_equal" if len(set(present))==1 else "changed"

def report(d):
    L=["# M10-R B2Y CHROMA-KEY CROSSMODEL1A","",
       "Key-aware comparison of B2Y 0x16 color_dif_lpf and 0x18 color_dif_suppression.","",
       "Lookup model: firmware scans records in table order for the requested record ID, then compares the runtime selector string against each 64-byte key slot; the first exact key match supplies the payload.",""]
    for rid,name in ((0x16,"color_dif_lpf"),(0x18,"color_dif_suppression")):
        rk=hex(rid); s=d["summary"][rk]
        L += [f"## {rk} {name}","",
              f"Union keys: **{s['key_count']}**; exact-equal: **{s['exact_equal']}**; changed: **{s['changed']}**; missing/added: **{s['missing_or_added']}**.",
              f"STILL keys changed: **{s['scope_counts'].get('STILL',{}).get('changed',0)}** of **{s['scope_totals'].get('STILL',0)}**.",
              f"STILLLINK keys changed: **{s['scope_counts'].get('STILLLINK',{}).get('changed',0)}** of **{s['scope_totals'].get('STILLLINK',0)}**.",
              f"SLIVE keys changed: **{s['scope_counts'].get('SLIVE',{}).get('changed',0)}** of **{s['scope_totals'].get('SLIVE',0)}**.",
              f"SMAGNI keys changed: **{s['scope_counts'].get('SMAGNI',{}).get('changed',0)}** of **{s['scope_totals'].get('SMAGNI',0)}**.","",
              "### Changed STILL keys","",
              "| Key | M10-R occurrence | M10M latest occurrence | Status |",
              "|---|---:|---:|---|"]
        rows=[x for x in d["comparisons"][rk] if x["scope"]=="STILL" and x["status"]!="exact_equal"]
        if not rows: L.append("| — | — | — | none |")
        for x in rows:
            a=x["by_firmware"][LABELS[0]]; b=x["by_firmware"][LABELS[2]]
            L.append(f"| {x['key']} | {('-' if a is None else a['ordinal'])} | {('-' if b is None else b['ordinal'])} | {x['status']} |")
        L += ["","### Record occurrences","",
              "| Firmware | Ordinal | Table index | Keys | Scope counts | SHA256 |",
              "|---|---:|---:|---:|---|---|"]
        for lab in LABELS:
            for r in d["items"][lab]["records"][rk]:
                L.append(f"| {lab} | {r['ordinal']} | {r['table_index']} | {r['key_count']} | {r['key_scopes']} | {r['payload_sha256']} |")
        L.append("")
    L += ["## Decision boundary","",
          "- A changed ordinal is not enough; only a changed key-resolved payload can affect that exact runtime selector key.",
          "- Prioritize changed STILL keys first for the saved-still renderer.",
          "- STILLLINK/SLIVE/SMAGNI differences are useful controls but should not be substituted for STILL behavior.",
          "- Do not change the Android renderer until the selected 0x16/0x18 payload fields are mapped to the setter/MMIO arithmetic.",""]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True); ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args(); ss=[spec(x) for x in a.item]
    if tuple(x[0] for x in ss)!=LABELS: raise SystemExit("unexpected labels/order")
    items={x[0]:load(*x) for x in ss}
    comps={}; sums={}
    for rid in RIDS:
        rk=hex(rid); maps={}; dups={}
        for lab in LABELS:
            maps[lab],dups[lab]=first_match_map(items[lab]["records"][rk])
        keys=sorted(set().union(*(set(m.keys()) for m in maps.values())))
        rows=[]
        for k in keys:
            by={}
            vals={}
            for lab in LABELS:
                r=maps[lab].get(k)
                by[lab]=None if r is None else {"ordinal":r["ordinal"],"table_index":r["table_index"],"payload_sha256":r["payload_sha256"],"size":r["size"]}
                vals[lab]=None if r is None else r["payload_sha256"]
            rows.append({"key":k,"scope":scope(k),"status":status(vals),"by_firmware":by})
        comps[rk]=rows
        sc=defaultdict(Counter); totals=Counter()
        for x in rows: sc[x["scope"]][x["status"]]+=1; totals[x["scope"]]+=1
        sums[rk]={"key_count":len(rows),"exact_equal":sum(x["status"]=="exact_equal" for x in rows),
                  "changed":sum(x["status"]=="changed" for x in rows),
                  "missing_or_added":sum(x["status"]=="missing_or_added" for x in rows),
                  "scope_counts":{k:dict(v) for k,v in sc.items()},"scope_totals":dict(totals),
                  "duplicate_key_warnings":dups}
    result={"schema":"M10R_B2Y_CHROMA_KEY_CROSSMODEL1A_V1","labels":list(LABELS),
            "lookup_semantics":"table-order record-id match then exact 64-byte key match; first match wins",
            "items":items,"comparisons":comps,"summary":sums,
            "frozen_references":["research/M10R_v072_b2y_lookup_targeted.txt","research/M10R_v177b_b2y_calibration_layout_pfx4.txt","research/M10R_v094_b2y_selector_inventory.txt"],
            "guardrails":["Key-aware comparison supersedes occurrence-only interpretation for repeated IDs.","Saved-still priority is exact STILL-key mapping.","No renderer changes are made by this audit."]}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n"); a.report.write_text(report(result))
    print(json.dumps(result["summary"],indent=2))
if __name__=="__main__": main()
