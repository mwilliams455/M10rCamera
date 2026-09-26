#!/usr/bin/env python3
"""Key-aware B2Y diff across Leica M10-R, M10 and M10-P.

The useful discriminator is:
    M10 == M10-P, while M10-R differs.
Those records are model-specific M10-R calibration candidates.

Repeated record IDs are resolved by exact 64-byte key lookup semantics.
Keyless records are aligned by occurrence ordinal within record ID.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path

from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE

LABELS=("M10R-30.22.23.34","M10-3.22.23.38","M10P-4.22.23.34")
R=M10R=LABELS[0]; M10=LABELS[1]; M10P=LABELS[2]

def sha(b): return hashlib.sha256(b).hexdigest()
def u32(b,o): return struct.unpack_from("<I",b,o)[0]

def parse_inventory(path:Path):
    out=defaultdict(list)
    if not path.exists(): return {}
    for raw in path.read_text(errors="replace").splitlines():
        if not raw.startswith("V094_MAP="): continue
        fields={}
        for tok in raw[len("V094_MAP="):].split("|"):
            if "=" in tok:
                k,v=tok.split("=",1);fields[k]=v
        try: rid=int(fields.get("record","UNKNOWN"),0)
        except Exception: continue
        name=fields.get("name","UNKNOWN")
        if name not in out[rid]: out[rid].append(name)
    return dict(out)

def keys_for(data,rec):
    h=RECORD_HEADER_OFF+rec.index*RECORD_STRIDE
    n=u32(data,h+0x0c);out=[]
    for i in range(n):
        raw=data[h+0x10+i*0x40:h+0x10+(i+1)*0x40]
        out.append(raw.split(b"\0",1)[0].decode("latin1","replace"))
    return out

def scope(key):
    if key is None:return "NO_KEY"
    if key.startswith("_B2YMODE:STILLLINK"):return "STILLLINK"
    if key.startswith("_B2YMODE:STILL"):return "STILL"
    if key.startswith("_B2YMODE:SLIVE"):return "SLIVE"
    if key.startswith("_B2YMODE:SMAGNI"):return "SMAGNI"
    if "_COLORSPACE:" in key:return "COLORSPACE"
    if "_SATURATION:" in key:return "SATURATION"
    if "_CONTRAST:" in key:return "CONTRAST"
    if "_ISO:" in key:return "ISO"
    return "OTHER"

def load(label,path):
    data=Path(path).read_bytes();recs=parse_records(data)
    rows=[];nokey_ord=defaultdict(int)
    for rec in recs:
        payload=data[rec.payload_offset:rec.payload_offset+rec.size]
        ks=keys_for(data,rec)
        row={"record_id":rec.record_id,"record_id_hex":f"0x{rec.record_id:02x}",
             "table_index":rec.index,"size":rec.size,"sha256":sha(payload),
             "keys":ks,"payload_offset":hex(rec.payload_offset)}
        if not ks:
            row["nokey_ordinal"]=nokey_ord[rec.record_id];nokey_ord[rec.record_id]+=1
        rows.append(row)

    # Firmware lookup: first record in table order containing exact key wins.
    identities={}
    duplicate_keys=defaultdict(list)
    for row in rows:
        rid=row["record_id"]
        if row["keys"]:
            for key in row["keys"]:
                ident=f"0x{rid:02x}|key:{key}"
                duplicate_keys[ident].append(row["table_index"])
                identities.setdefault(ident,row)
        else:
            ident=f"0x{rid:02x}|nokey#{row['nokey_ordinal']}"
            identities[ident]=row
    return {"label":label,"path":str(path),"b2y_sha256":sha(data),
            "record_count":len(rows),"records":rows,"identities":identities,
            "duplicate_key_warnings":{k:v for k,v in duplicate_keys.items() if len(v)>1}}

def pair_eq(a,b):
    return a is not None and b is not None and a["size"]==b["size"] and a["sha256"]==b["sha256"]

def status(by):
    vals=[by[x] for x in LABELS]
    if all(v is not None for v in vals):
        return "exact_equal_all" if pair_eq(vals[0],vals[1]) and pair_eq(vals[0],vals[2]) else "changed"
    return "missing_or_added"

def key_from_ident(ident):
    return ident.split("|key:",1)[1] if "|key:" in ident else None

def rid_from_ident(ident): return int(ident.split("|",1)[0],16)

def report(result):
    L=["# M10 FAMILY B2Y COLORFAMILYDIFF1A","",
       "Key-aware B2Y comparison of M10-R 30.22.23.34 vs M10 3.22.23.38 and M10-P 4.22.23.34.","",
       "Primary discriminator: M10 and M10-P resolve to the same payload while M10-R resolves to a different payload.","",
       "## Summary","",
       f"- Aligned identities: **{result['summary']['identity_count']}**",
       f"- Exact-equal across all three: **{result['summary']['exact_equal_all']}**",
       f"- M10-R-specific changed identities: **{result['summary']['m10r_specific_changed']}**",
       f"- Missing/added identities: **{result['summary']['missing_or_added']}**","",
       "## M10-R-specific record groups","",
       "| Record | Selector mapping | Changed keys | STILL | Other scopes | Sample keys |",
       "|---|---|---:|---:|---|---|"]
    for g in result["m10r_specific_groups"]:
        scopes=", ".join(f"{k}:{v}" for k,v in sorted(g["scope_counts"].items()) if k!="STILL") or "-"
        samples="<br>".join(g["sample_keys"][:6]) if g["sample_keys"] else "(keyless)"
        L.append(f"| {g['record_id']} | {', '.join(g['selector_names']) or 'UNKNOWN'} | {g['count']} | {g['scope_counts'].get('STILL',0)} | {scopes} | {samples} |")
    L += ["","## Interpretation boundary","",
          "- A cross-color-family difference is a calibration candidate, not proof of pixel arithmetic.",
          "- M10/M10-P agreement is used as a control to isolate M10-R-specific state.",
          "- Generic color-family records that are byte-identical (for example record 0x18 saturation payloads) are intentionally deprioritized as M10-R-specific causes.",
          "- No Android renderer change is made by this audit.",""]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inventory",type=Path,required=True)
    ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    specs=[]
    for s in a.item:
        label,path=s.split("|",1);specs.append((label,Path(path)))
    if tuple(x[0] for x in specs)!=LABELS:raise SystemExit(f"labels/order {tuple(x[0] for x in specs)}")
    items={label:load(label,path) for label,path in specs}
    inv=parse_inventory(a.inventory)
    identities=sorted(set().union(*(set(v["identities"]) for v in items.values())),
                      key=lambda x:(rid_from_ident(x),x))
    rows=[]
    cnt=Counter()
    groups=defaultdict(lambda:{"keys":[],"scope_counts":Counter()})
    for ident in identities:
        by={lab:items[lab]["identities"].get(ident) for lab in LABELS}
        st=status(by);cnt[st]+=1
        sib_eq=pair_eq(by[M10],by[M10P])
        r_eq_sib=pair_eq(by[M10R],by[M10]) if sib_eq else False
        specific=(sib_eq and by[M10R] is not None and not r_eq_sib)
        missing=any(v is None for v in by.values())
        rid=rid_from_ident(ident);key=key_from_ident(ident);sc=scope(key)
        row={"identity":ident,"record_id":f"0x{rid:02x}","selector_names":inv.get(rid,[]),
             "key":key,"scope":sc,"status":st,"m10_m10p_equal":sib_eq,
             "m10r_specific_changed":specific,
             "by_firmware":{lab:(None if v is None else {"table_index":v["table_index"],"size":v["size"],"sha256":v["sha256"]}) for lab,v in by.items()}}
        rows.append(row)
        if specific:
            g=groups[rid];g["keys"].append(key);g["scope_counts"][sc]+=1

    g_rows=[]
    for rid,g in groups.items():
        keys=[x for x in g["keys"] if x is not None]
        g_rows.append({"record_id":f"0x{rid:02x}","record_id_int":rid,
                       "selector_names":inv.get(rid,[]),"count":sum(g["scope_counts"].values()),
                       "scope_counts":dict(g["scope_counts"]),
                       "sample_keys":keys[:12]})
    g_rows.sort(key=lambda x:(-x["scope_counts"].get("STILL",0),-x["count"],x["record_id_int"]))

    result={"schema":"M10_FAMILY_B2Y_COLORFAMILYDIFF1A_V1","labels":list(LABELS),
            "items":{lab:{k:v for k,v in item.items() if k!="identities"} for lab,item in items.items()},
            "records":rows,"m10r_specific_groups":g_rows,
            "summary":{"identity_count":len(rows),"exact_equal_all":cnt["exact_equal_all"],
                       "changed":cnt["changed"],"missing_or_added":cnt["missing_or_added"],
                       "m10r_specific_changed":sum(r["m10r_specific_changed"] for r in rows)},
            "guardrails":["Exact-key lookup semantics used for keyed records.","Keyless records aligned by occurrence ordinal.","No renderer changes."]}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n");a.report.write_text(report(result))
    print(json.dumps(result["summary"],indent=2))
    for g in g_rows[:30]:print(g)
if __name__=="__main__":main()
