#!/usr/bin/env python3
"""CA9 output-space audit1A.

Research-only. Scans canonical extracted M10-R firmware sections for rendered
colour-space labels/resources, resolves absolute little-endian pointer xrefs,
and classifies nearby candidate transfer-function payloads. Renderer untouched.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, re, struct
from pathlib import Path
from typing import Any

TARGETS = [
    b"StandardColorMode", b"CC0_Mode", b"CC1_Mode", b"Tone_Ctrl", b"DG_Ctrl",
    b"B2Y_TF_CA9_CM.bin", b"ColorManagementFinished", b"ca9_cm_ColorManagementFinished",
]
KEYWORDS = ("ca9", "b2y", "colormode", "color_mode", "transfer", "gamma", "cc0", "cc1", "ycc", "jpeg")


def occ(data: bytes, needle: bytes):
    p = 0
    while True:
        p = data.find(needle, p)
        if p < 0: return
        yield p
        p += 1


def printable_strings(data: bytes, minlen: int = 5):
    for m in re.finditer(rb"[ -~]{%d,}" % minlen, data):
        yield m.start(), m.group().decode("latin1", "replace")


def shannon(data: bytes) -> float:
    if not data: return 0.0
    counts = [0]*256
    for b in data: counts[b] += 1
    n = len(data)
    return -sum((c/n)*math.log2(c/n) for c in counts if c)


def seqstats(data: bytes, width: int, endian: str):
    n = len(data)//width
    if n < 4: return None
    fmt = endian + {1:"B",2:"H",4:"I"}[width]
    vals = [struct.unpack_from(fmt, data, i*width)[0] for i in range(n)]
    dif = [vals[i+1]-vals[i] for i in range(n-1)]
    mono = sum(d >= 0 for d in dif) / max(1,len(dif))
    strict = sum(d > 0 for d in dif) / max(1,len(dif))
    return {"width":width,"endian":endian,"count":n,"first":vals[:8],"last":vals[-8:],
            "min":min(vals),"max":max(vals),"nondecreasing_fraction":round(mono,6),
            "strict_increase_fraction":round(strict,6)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("json_out",type=Path)
    ap.add_argument("md_out",type=Path)
    args=ap.parse_args()
    rows=list(csv.DictReader((args.sections/"sections.csv").open(encoding="utf-8")))
    secs=[]
    for r in rows:
        p=args.sections/r["file"]
        b=p.read_bytes()
        base=int(r["image_base"],16)
        secs.append((r,p,b,base))

    hits=[]
    target_addrs={}
    for r,p,b,base in secs:
        for t in TARGETS:
            for o in occ(b,t):
                a=(base+o)&0xffffffff if base else None
                h={"target":t.decode(),"section":r["index"],"name":r["name"],"file":p.name,
                   "offset":hex(o),"address":hex(a) if a is not None else None,
                   "context":b[max(0,o-48):min(len(b),o+len(t)+96)].hex()}
                hits.append(h)
                if a is not None: target_addrs.setdefault(t.decode(),[]).append(a)

    xrefs=[]
    for target,addrs in target_addrs.items():
        for a in addrs:
            needle=struct.pack("<I",a)
            for r,p,b,base in secs:
                for o in occ(b,needle):
                    src=(base+o)&0xffffffff if base else None
                    xrefs.append({"target":target,"target_address":hex(a),"section":r["index"],"name":r["name"],
                                  "offset":hex(o),"source_address":hex(src) if src is not None else None,
                                  "context":b[max(0,o-32):min(len(b),o+36)].hex()})

    keyword_strings=[]
    for r,p,b,base in secs:
        for o,s in printable_strings(b):
            sl=s.lower()
            if any(k in sl for k in KEYWORDS):
                keyword_strings.append({"section":r["index"],"name":r["name"],"offset":hex(o),
                                        "address":hex(base+o) if base else None,"string":s[:240]})
    keyword_strings=keyword_strings[:4000]

    tf_candidates=[]
    # Candidate discrete sections plus windows following an exact TF filename string.
    for r,p,b,base in secs:
        nl=r["name"].lower()
        if "b2y" in nl and ("tf" in nl or "transfer" in nl or "ca9" in nl):
            sample=b[:min(len(b),0x20000)]
            tf_candidates.append({"kind":"section","section":r["index"],"name":r["name"],"size":len(b),
                                  "sha256":hashlib.sha256(b).hexdigest(),"entropy":round(shannon(sample),6),
                                  "stats":[x for x in (seqstats(sample,1,"<"),seqstats(sample,2,"<"),seqstats(sample,4,"<")) if x]})
        for o in occ(b,b"B2Y_TF_CA9_CM.bin"):
            lo=max(0,o-0x100); hi=min(len(b),o+0x1000)
            sample=b[lo:hi]
            tf_candidates.append({"kind":"filename_window","section":r["index"],"name":r["name"],
                                  "filename_offset":hex(o),"window_offset":hex(lo),"window_size":len(sample),
                                  "entropy":round(shannon(sample),6),"strings":[{"offset":hex(x),"s":s[:160]} for x,s in list(printable_strings(sample))[:60]],
                                  "stats":[x for x in (seqstats(sample,1,"<"),seqstats(sample,2,"<"),seqstats(sample,4,"<")) if x]})

    report={"schema":"m10r.ca9.outputspace_audit1a.v1","scope":"static canonical firmware section scan; no renderer changes",
            "targets":hits,"absolute_pointer_xrefs":xrefs,"keyword_strings":keyword_strings,"tf_candidates":tf_candidates}
    args.json_out.parent.mkdir(parents=True,exist_ok=True)
    args.json_out.write_text(json.dumps(report,indent=2)+"\n")

    lines=["# M10-R CA9 OUTPUT-SPACE AUDIT1A","","Research-only. Renderer unchanged.","",
           "## Exact target locations","","| Target | Section | Address | Offset |","|---|---|---:|---:|"]
    for h in hits: lines.append(f"| `{h['target']}` | `{h['section']} {h['name']}` | `{h['address']}` | `{h['offset']}` |")
    lines += ["","## Absolute pointer xrefs","","| Target | Target addr | Source section | Source addr |","|---|---:|---|---:|"]
    for x in xrefs: lines.append(f"| `{x['target']}` | `{x['target_address']}` | `{x['section']} {x['name']}` | `{x['source_address']}` |")
    lines += ["","## TF candidates",""]
    if not tf_candidates: lines.append("- No discrete section or exact filename window found.")
    for c in tf_candidates:
        lines.append(f"- `{c['kind']}` section `{c['section']} {c['name']}` size/window `{c.get('size',c.get('window_size'))}` entropy `{c['entropy']}`")
        for s in c.get("stats",[]): lines.append(f"  - {s}")
        for s in c.get("strings",[])[:20]: lines.append(f"  - string {s['offset']}: `{s['s']}`")
    lines += ["","## Relevant strings",""]
    for s in keyword_strings[:500]: lines.append(f"- `{s['section']} {s['name']}` `{s['address']}` `{s['string']}`")
    args.md_out.write_text("\n".join(lines)+"\n")
    print("CA9_TARGET_HITS="+str(len(hits)))
    print("CA9_POINTER_XREFS="+str(len(xrefs)))
    print("CA9_TF_CANDIDATES="+str(len(tf_candidates)))
    for h in hits: print("CA9_HIT="+json.dumps({k:h[k] for k in ("target","section","name","offset","address")}))

if __name__=="__main__": main()
