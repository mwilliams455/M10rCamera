#!/usr/bin/env python3
"""M10-R SATURATIONFIELDS1A - basis-value proof for the six 0x18 saturation fields."""
from __future__ import annotations
import argparse, json, struct
from pathlib import Path
from m10r_b2y_saturation1a import DELTA_OFFSETS, find_b2y, find_section, select_modes, run_original, u32
from m10r_yblend_bit15_audit1a import MMIO

PROBES=(0,1,0x1fff,0x2000,0x3fff,0x4000,0x7fff,0xffff)

def put32(b,o,v):
    struct.pack_into("<I",b,o,v&0xffffffff)

def diff_words(a,b):
    out=[]
    for off in range(0,min(len(a),len(b)),4):
        x=u32(a,off); y=u32(b,off)
        if x!=y: out.append((MMIO+off,x,y))
    return out

def trailing_zero_bits(x):
    if x==0: return 32
    return (x & -x).bit_length()-1

def contiguous_width(mask,shift):
    x=mask>>shift; w=0
    while x&1:
        w+=1; x>>=1
    if x: raise RuntimeError(f"non-contiguous mask {mask:#x}")
    return w

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()

    b2y=find_b2y(a.sections).read_bytes()
    img=find_section(a.sections,"IMG-System").read_bytes()
    selected=select_modes(b2y)
    med=selected["MEDIUM"][1]
    old=bytes((i*37+0x5a)&0xff for i in range(0x4000))

    fields=[]
    for poff in DELTA_OFFSETS:
        outs={}
        for v in PROBES:
            p=bytearray(med); put32(p,poff,v)
            outs[v]=run_original(img,bytes(p),old)
        d01=diff_words(outs[0],outs[1])
        if len(d01)!=1:
            raise RuntimeError(f"offset {poff:#x}: 0->1 changed {d01}")
        addr=d01[0][0]
        z=u32(outs[0],addr-MMIO)
        ff=u32(outs[0xffff],addr-MMIO)
        mask=z^ff
        shift=trailing_zero_bits(mask)
        width=contiguous_width(mask,shift)
        enc={}
        for v in PROBES:
            word=u32(outs[v],addr-MMIO)
            enc[hex(v)]=(word&mask)>>shift
        if width!=14:
            raise RuntimeError(f"offset {poff:#x}: expected 14-bit field, mask={mask:#x} width={width}")
        if enc["0x0"]!=0 or enc["0x1"]!=1 or enc["0x3fff"]!=0x3fff:
            raise RuntimeError(f"offset {poff:#x}: basic encode mismatch {enc}")
        if enc["0x4000"]!=0 or enc["0x7fff"]!=0x3fff or enc["0xffff"]!=0x3fff:
            raise RuntimeError(f"offset {poff:#x}: truncation mismatch {enc}")
        fields.append({
            "payload_offset":hex(poff),"mmio_address":hex(addr),"mask":hex(mask),
            "shift":shift,"width":width,"probe_encoded_values":enc
        })

    expected=[
      ("0x10","0x20021110","0x3fff",0),
      ("0x14","0x20021110","0x3fff0000",16),
      ("0x18","0x20021114","0x3fff",0),
      ("0x1c","0x20021114","0x3fff0000",16),
      ("0x20","0x20021118","0x3fff",0),
      ("0x24","0x20021118","0x3fff0000",16),
    ]
    got=[(f["payload_offset"],f["mmio_address"],f["mask"],f["shift"]) for f in fields]
    if got!=expected:
        raise RuntimeError(f"unexpected field map {got}")

    result={
      "schema":"M10R_B2Y_SATURATIONFIELDS1A_V1",
      "record_id":"0x18","selector":"color_dif_suppression","setter":"IMG-System +0xd0770",
      "fields":fields,
      "pair_registers":["0x20021110","0x20021114","0x20021118"],
      "field_encoding":{
        "width_bits":14,
        "pair_layout":"low field bits 0..13; high field bits 16..29; bits 14..15 and 30..31 preserved",
        "input_behavior":"setter consumes low 14 bits of each payload halfword",
        "medium_code":"0x2000","low_code":"0x1b34","high_code":"0x2666",
        "q13_compatibility":"0x2000 equals 2^13 and LOW/HIGH are approximately 0.85x/1.20x, but hardware numeric semantics remain unproven until the consumer equation is recovered"
      },
      "guardrails":[
        "This proves field packing and truncation in the original setter.",
        "It does not prove that the hardware consumer interprets the fields as Q13 multipliers.",
        "It does not prove pixel-stage placement.",
        "No renderer code is changed."
      ]
    }
    a.out.parent.mkdir(parents=True,exist_ok=True); a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    lines=[
      "# M10-R B2Y SATURATIONFIELDS1A","",
      "Basis-value execution of the original Leica 0x18 color-difference-suppression setter.","",
      "## Proven field map","",
      "| Payload | Register | Field | Width |","|---|---|---|---:|"
    ]
    for f in fields:
        hi=f["shift"]+f["width"]-1
        lines.append(f"| {f['payload_offset']} | {f['mmio_address']} | bits {f['shift']}..{hi} | {f['width']} |")
    lines += ["",
      "The six LOW/MEDIUM/HIGH values are three paired 14-bit register coefficients. Values above 0x3FFF are truncated to the low 14 bits by the original setter; 0x4000 encodes as zero and 0xFFFF encodes as 0x3FFF.",
      "",
      "MEDIUM uses 0x2000 = 8192 = 2^13; LOW uses 0x1B34 = 6964 (0.85009765625 relative to MEDIUM) and HIGH uses 0x2666 = 9830 (1.199951171875 relative to MEDIUM). This is Q13-compatible calibration structure, but the hardware consumer equation is not yet recovered, so Q13 multiplier semantics are not frozen yet.",
      "",
      "## Next boundary","",
      "Recover the SAM7/hardware meaning of the three coefficient pairs and constrain their pixel-stage placement relative to CC1/Yc. Do not add an Android chroma multiplier solely from the numeric pattern.",""
    ]
    a.report.write_text("\n".join(lines))
    print(json.dumps(result["field_encoding"],indent=2))
    for f in fields: print(f)

if __name__=="__main__": main()
