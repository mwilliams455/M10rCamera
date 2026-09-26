#!/usr/bin/env python3
"""M10-R SATURATION1A: execute original 0x18 color_dif_suppression setter.

Research-only. This proves register programming, not ISP pixel arithmetic.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from pathlib import Path

from m10r_b2y_assets import parse_records, RECORD_HEADER_OFF, RECORD_STRIDE
from m10r_yblend_bit15_audit1a import Programmer, MMIO

RID=0x18
ENTRY=0xD0770
MODES=("LOW","MEDIUM","HIGH","MONOCHROME")
DELTA_OFFSETS=tuple(range(0x10,0x28,4))

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def u32(b:bytes,o:int)->int:return struct.unpack_from("<I",b,o)[0]
def put32(b:bytearray,o:int,v:int)->None:struct.pack_into("<I",b,o,v&0xffffffff)

def section_rows(secdir:Path):
    with (secdir/"sections.csv").open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))

def find_section(secdir:Path,name:str)->Path:
    hits=[secdir/r["file"] for r in section_rows(secdir) if r["name"]==name]
    if len(hits)!=1:raise RuntimeError(f"{name}: found {hits}")
    return hits[0]

def find_b2y(secdir:Path)->Path:
    rows=section_rows(secdir)
    named=[secdir/r["file"] for r in rows if "data/calib/b2y.bin" in (r["name"]+" "+r["file"]).lower()]
    if len(named)==1:return named[0]
    hits=[]
    for r in rows:
        s=(r["name"]+" "+r["file"]).lower()
        if "calibration data" not in s and "calib" not in s:continue
        p=secdir/r["file"]
        try:recs=parse_records(p.read_bytes())
        except Exception:continue
        if len([x for x in recs if x.record_id==0x0c and x.size==60])==1 and len([x for x in recs if x.record_id==0x0d and x.size==24])==1:
            hits.append(p)
    if len(hits)!=1:raise RuntimeError(f"B2Y structural identification found {hits}")
    return hits[0]

def rec_keys(data:bytes,rec)->list[str]:
    h=RECORD_HEADER_OFF+rec.index*RECORD_STRIDE
    n=u32(data,h+0x0c)
    out=[]
    for i in range(n):
        raw=data[h+0x10+i*0x40:h+0x10+(i+1)*0x40]
        out.append(raw.split(b"\0",1)[0].decode("latin1","replace"))
    return out

def select_modes(data:bytes):
    found={}
    for rec in parse_records(data):
        if rec.record_id!=RID:continue
        keys=rec_keys(data,rec)
        blob=data[rec.payload_offset:rec.payload_offset+rec.size]
        for mode in MODES:
            key=f"_B2YMODE:STILL_SATURATION:{mode}"
            if key in keys:
                if mode in found:raise RuntimeError(f"duplicate key {key}")
                found[mode]=(rec,blob,key)
    if set(found)!=set(MODES):raise RuntimeError(f"missing saturation modes {set(MODES)-set(found)}")
    return found

def changed_words(before:bytes,after:bytes):
    out=[]
    for off in range(0,min(len(before),len(after)),4):
        a=u32(before,off);b=u32(after,off)
        if a!=b:out.append({"mmio_address":hex(MMIO+off),"mmio_offset":hex(off),"before":a,"after":b,"xor":a^b})
    return out

def diff_words(a:bytes,b:bytes):
    out=[]
    for off in range(0,min(len(a),len(b)),4):
        x=u32(a,off);y=u32(b,off)
        if x!=y:out.append({"mmio_address":hex(MMIO+off),"mmio_offset":hex(off),"a":x,"b":y,"xor":x^y})
    return out

def run_original(img:bytes,payload:bytes,old:bytes)->bytes:
    p=Programmer(img)
    return p.run(ENTRY,payload,old,0)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()

    b2yp=find_b2y(args.sections); imgp=find_section(args.sections,"IMG-System")
    b2y=b2yp.read_bytes();img=imgp.read_bytes()
    selected=select_modes(b2y)
    payloads={m:b for m,(_,b,_) in selected.items()}
    if any(len(x)!=0x90 for x in payloads.values()):raise RuntimeError("unexpected 0x18 payload size")

    med=payloads["MEDIUM"]
    diff_offsets={}
    for mode in ("LOW","HIGH"):
        diffs=[off for off in range(0,0x90,4) if u32(payloads[mode],off)!=u32(med,off)]
        diff_offsets[mode]=diffs
        assert diffs==list(DELTA_OFFSETS),(mode,diffs)

    scale_words={m:[u32(payloads[m],o) for o in DELTA_OFFSETS] for m in ("LOW","MEDIUM","HIGH")}
    assert len(set(scale_words["LOW"]))==1
    assert len(set(scale_words["MEDIUM"]))==1
    assert len(set(scale_words["HIGH"]))==1
    lo=scale_words["LOW"][0];unity=scale_words["MEDIUM"][0];hi=scale_words["HIGH"][0]

    old_zero=bytes(0x4000)
    old_pattern=bytes((i*37+0x5a)&0xff for i in range(0x4000))
    zero_out={m:run_original(img,payloads[m],old_zero) for m in MODES}
    pattern_out={m:run_original(img,payloads[m],old_pattern) for m in MODES}

    mode_vs_medium={}
    for mode in ("LOW","HIGH","MONOCHROME"):
        mode_vs_medium[mode]={
            "zero_initial":diff_words(zero_out["MEDIUM"],zero_out[mode]),
            "pattern_initial":diff_words(pattern_out["MEDIUM"],pattern_out[mode]),
        }

    sensitivity=[]
    for poff in DELTA_OFFSETS:
        test=bytearray(med);put32(test,poff,lo)
        got=run_original(img,bytes(test),old_pattern)
        d=diff_words(pattern_out["MEDIUM"],got)
        sensitivity.append({"payload_offset":hex(poff),"medium":unity,"low_substitute":lo,"mmio_differences":d})
        assert d,f"payload {poff:#x} produced no programmer output delta"

    sens_addrs={x["mmio_address"] for s in sensitivity for x in s["mmio_differences"]}
    low_addrs={x["mmio_address"] for x in mode_vs_medium["LOW"]["pattern_initial"]}
    high_addrs={x["mmio_address"] for x in mode_vs_medium["HIGH"]["pattern_initial"]}
    assert sens_addrs==low_addrs==high_addrs,(sens_addrs,low_addrs,high_addrs)

    result={
      "schema":"M10R_B2Y_SATURATION1A_V1",
      "b2y_sha256":sha(b2y),"img_system_sha256":sha(img),
      "record_id":"0x18","selector":"color_dif_suppression","setter_offset":hex(ENTRY),
      "keys":{m:selected[m][2] for m in MODES},
      "payload_sha256":{m:sha(payloads[m]) for m in MODES},
      "low_medium_high_only_differ_at_payload_offsets":[hex(x) for x in DELTA_OFFSETS],
      "scale_words":scale_words,
      "scale_relative_to_medium":{
        "low":lo/unity,"medium":1.0,"high":hi/unity,
        "low_exact":f"{lo}/{unity}","high_exact":f"{hi}/{unity}",
      },
      "programmer":{
        "zero_initial_changed_words":{m:changed_words(old_zero,zero_out[m]) for m in MODES},
        "pattern_initial_changed_words":{m:changed_words(old_pattern,pattern_out[m]) for m in MODES},
        "mode_vs_medium":mode_vs_medium,
        "single_word_sensitivity_low_substitute":sensitivity,
        "scale_output_addresses":sorted(sens_addrs),
        "six_scale_words_fully_explain_low_high_programmer_delta":True,
      },
      "guardrails":[
        "This proves original firmware register programming, not ISP pixel arithmetic.",
        "0x2000 is the MEDIUM calibration reference value; hardware Q-format remains separate unless proven.",
        "LOW/MEDIUM/HIGH key semantics and exact numeric ratios are firmware facts.",
        "No renderer change is made by this pass.",
      ],
    }

    lines=[
      "# M10-R B2Y SATURATION1A",
      "",
      "Original-firmware execution of record 0x18 (color_dif_suppression) for M10-R STILL saturation LOW/MEDIUM/HIGH.",
      "",
      "## Payload result",
      "",
      f"- LOW: six words at 0x10..0x24 = {lo:#06x} ({lo}), ratio to MEDIUM = {lo/unity:.8f}x.",
      f"- MEDIUM: six words at 0x10..0x24 = {unity:#06x} ({unity}).",
      f"- HIGH: six words at 0x10..0x24 = {hi:#06x} ({hi}), ratio to MEDIUM = {hi/unity:.8f}x.",
      "- Apart from those six words, LOW/MEDIUM/HIGH 144-byte payloads are identical.",
      "",
      "## Original setter execution",
      "",
      f"Setter: IMG-System +{ENTRY:#x}.",
      f"The six scale words affect exactly {len(sens_addrs)} MMIO word address(es): " + ", ".join(sorted(sens_addrs)) + ".",
      "",
      "Each of the six payload words was perturbed independently from MEDIUM to the LOW value. Their union exactly equals the full LOW-vs-MEDIUM and HIGH-vs-MEDIUM register-programmer delta under a nonzero deterministic MMIO initial state.",
      "",
      "Therefore the LOW/MEDIUM/HIGH distinction in the M10-R 0x18 still-saturation record is fully isolated to these six firmware-programmed values.",
      "",
      "## Boundary",
      "",
      "This does not yet prove the hardware pixel equation or Q-format. Do not simply multiply Android chroma by 0.85/1.0/1.2 until the destination-register semantics and signal domain are recovered.",
      "",
      "## Next",
      "",
      "Trace the exact destination register bitfields for the six scale words, then identify where the equivalent operation belongs relative to POSTYC1A / CC1 in the renderer. Validate offline first; keep the Android renderer frozen.",
      "",
    ]
    args.out.parent.mkdir(parents=True,exist_ok=True);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    args.report.write_text("\n".join(lines))
    print(json.dumps({"scale_words":scale_words,"ratios":result["scale_relative_to_medium"],"scale_output_addresses":sorted(sens_addrs)},indent=2))

if __name__=="__main__":main()
