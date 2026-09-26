#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from pathlib import Path
from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE

LABELS=("M10R-30.22.23.34","M10-3.22.23.38","M10P-4.22.23.34")
RID=0x18
MODES=("LOW","MEDIUM","HIGH","MONOCHROME")

def sha(b):return hashlib.sha256(b).hexdigest()
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def keys(data,rec):
    h=RECORD_HEADER_OFF+rec.index*RECORD_STRIDE
    n=u32(data,h+0x0c);out=[]
    for i in range(n):
        x=data[h+0x10+i*0x40:h+0x10+(i+1)*0x40].split(b"\0",1)[0]
        out.append(x.decode("latin1","replace"))
    return out
def load(spec):
    label,path=spec.split("|",1);data=Path(path).read_bytes()
    rows=[]
    for r in parse_records(data):
        if r.record_id!=RID:continue
        blob=data[r.payload_offset:r.payload_offset+r.size]
        rows.append({"table_index":r.index,"keys":keys(data,r),"size":r.size,"sha256":sha(blob),
                     "words":[u32(blob,o) for o in range(0,len(blob),4)],"payload_hex":blob.hex()})
    sat={}
    for mode in MODES:
        key=f"_B2YMODE:STILL_SATURATION:{mode}"
        hit=[x for x in rows if key in x["keys"]]
        if len(hit)==1:sat[mode]=hit[0]
    return {"label":label,"b2y_sha256":sha(data),"records":rows,"saturation":sat}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--item",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True);ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    items={x.split("|",1)[0]:load(x) for x in a.item}
    if tuple(items)!=LABELS:raise SystemExit(f"labels {tuple(items)}")
    summary={}
    for label,item in items.items():
        sat=item["saturation"]
        row={"has_all_modes":set(sat)==set(MODES)}
        if row["has_all_modes"]:
            med=sat["MEDIUM"]["words"]
            row["gain_words"]=med[4:10]
            row["words_0x40_0x50"]=med[16:21]
            row["range_words_0x54_0x60"]=med[21:25]
            row["control_words_0x64_0x7c"]=med[25:32]
            row["range_words_0x80_0x8c"]=med[32:36]
            row["low_gain_words"]=sat["LOW"]["words"][4:10]
            row["high_gain_words"]=sat["HIGH"]["words"][4:10]
            row["mono_gain_words"]=sat["MONOCHROME"]["words"][4:10]
            row["low_med_diff_offsets"]=[hex(i*4) for i,(x,y) in enumerate(zip(sat["LOW"]["words"],med)) if x!=y]
            row["high_med_diff_offsets"]=[hex(i*4) for i,(x,y) in enumerate(zip(sat["HIGH"]["words"],med)) if x!=y]
        summary[label]=row
    comparable=[v for v in summary.values() if v["has_all_modes"]]
    exact_geometry=False
    if len(comparable)>=2:
        fields=("gain_words","words_0x40_0x50","range_words_0x54_0x60","control_words_0x64_0x7c","range_words_0x80_0x8c")
        exact_geometry=all(len({tuple(v[f]) for v in comparable})==1 for f in fields)
    result={"schema":"M10_FAMILY_B2Y_COLOR_SECTOR1A_V1","items":items,"summary":summary,
            "exact_medium_geometry_across_color_models":exact_geometry,
            "guardrails":["Cross-model calibration identity does not prove hardware arithmetic.","No renderer changes."]}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    lines=["# M10 FAMILY B2Y COLOR SECTOR1A","",
           "Cross-model audit of record 0x18 STILL saturation structure in M10-R, M10 and M10-P.",""]
    for label,row in summary.items():
        lines += [f"## {label}","",f"All four saturation modes found: **{row['has_all_modes']}**."]
        if row["has_all_modes"]:
            lines += [f"- MEDIUM six gain words: {row['gain_words']}",
                      f"- LOW six gain words: {row['low_gain_words']}",
                      f"- HIGH six gain words: {row['high_gain_words']}",
                      f"- MEDIUM words +0x40..+0x50: {row['words_0x40_0x50']}",
                      f"- LOW-vs-MEDIUM diffs: {row['low_med_diff_offsets']}",
                      f"- HIGH-vs-MEDIUM diffs: {row['high_med_diff_offsets']}",""]
    lines += [f"Exact medium geometry across color models with full saturation modes: **{exact_geometry}**.","",
              "Interpretation boundary: recurrence supports a generic M10-family color-control geometry, but does not by itself label the six lanes or five coordinates.",""]
    a.report.write_text("\n".join(lines))
    print(json.dumps({"summary":summary,"exact_medium_geometry":exact_geometry},indent=2))
if __name__=="__main__":main()
