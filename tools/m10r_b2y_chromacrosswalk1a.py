#!/usr/bin/env python3
"""M10-R CHROMACROSSWALK1A.

Prove that the 144-byte IMG calibration record 0x18 and the compact SAM7
b2y_ctrl_cs ABI program identical B2Y chroma-suppress MMIO state.
"""
from __future__ import annotations
import argparse, hashlib, json, random, struct
from pathlib import Path

from m10r_b2y_saturation1a import find_b2y, find_section, select_modes
from m10r_yblend_bit15_audit1a import Programmer

IMG_ENTRY=0xD0770
SAM_ENTRY=0x51F1A
MODES=("LOW","MEDIUM","HIGH","MONOCHROME")

def u32(b,o): return struct.unpack_from("<I",b,o)[0]

MAP=[
    (0x00,1,0x00),(0x01,1,0x04),(0x02,1,0x08),(0x03,1,0x0c),
    (0x04,2,0x10),(0x06,2,0x14),(0x08,2,0x18),(0x0a,2,0x1c),
    (0x0c,2,0x20),(0x0e,2,0x24),
    (0x10,4,0x28),(0x14,4,0x2c),(0x18,4,0x30),(0x1c,4,0x34),
    (0x20,4,0x38),(0x24,4,0x3c),
    (0x28,2,0x40),(0x2a,2,0x44),(0x2c,2,0x48),(0x2e,2,0x4c),
    (0x30,2,0x50),(0x32,2,0x54),(0x34,2,0x58),(0x36,2,0x5c),
    (0x38,2,0x60),
    (0x3a,1,0x64),(0x3b,1,0x68),(0x3c,1,0x6c),
    (0x3e,2,0x74),(0x40,2,0x70),
    (0x42,2,0x7c),(0x44,2,0x78),
    (0x46,2,0x80),(0x48,2,0x84),(0x4a,2,0x88),(0x4c,2,0x8c),
]
COMPACT_SIZE=0x4e

def pack_compact(img_record):
    if len(img_record)!=0x90:
        raise ValueError(f"expected 0x90-byte IMG record, got {len(img_record):#x}")
    out=bytearray(COMPACT_SIZE)
    for co,w,io in MAP:
        v=u32(img_record,io)
        if w==1:
            out[co]=v&0xff
        elif w==2:
            struct.pack_into("<H",out,co,v&0xffff)
        elif w==4:
            struct.pack_into("<I",out,co,v)
        else:
            raise AssertionError(w)
    return bytes(out)

def random_record(rng):
    b=bytearray(0x90)
    for off in range(0,0x90,4):
        struct.pack_into("<I",b,off,rng.getrandbits(32))
    return bytes(b)

def first_diff(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:return i,x,y
    return None

def run_pair(img_code,sam_code,record,old):
    compact=pack_compact(record)
    img=Programmer(img_code)
    sam=Programmer(sam_code,True)
    x=img.run(IMG_ENTRY,record,old,0)
    y=sam.run(SAM_ENTRY,compact,old,0)
    return compact,x,y

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("--cases",type=int,default=256)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()

    b2y=find_b2y(args.sections).read_bytes()
    img=find_section(args.sections,"IMG-System").read_bytes()
    sam=find_section(args.sections,"IMG-SAM7").read_bytes()
    selected=select_modes(b2y)

    rng=random.Random(0xC5102026)
    real=[]
    for mode in MODES:
        record=selected[mode][1]
        old=rng.randbytes(0x4000)
        compact,x,y=run_pair(img,sam,record,old)
        d=first_diff(x,y)
        if d is not None:
            raise AssertionError(f"real mode {mode} mismatch MMIO+{d[0]:#x}: {d[1]:#x}!={d[2]:#x}")
        real.append({
            "mode":mode,
            "img_payload_sha256":hashlib.sha256(record).hexdigest(),
            "compact_sha256":hashlib.sha256(compact).hexdigest(),
            "compact_hex":compact.hex(),
            "mmio_identical":True,
        })

    random_passed=0
    for i in range(args.cases):
        record=random_record(rng)
        old=rng.randbytes(0x4000)
        compact,x,y=run_pair(img,sam,record,old)
        d=first_diff(x,y)
        if d is not None:
            raise AssertionError(f"random case {i} mismatch MMIO+{d[0]:#x}: {d[1]:#x}!={d[2]:#x}")
        random_passed+=1

    result={
      "schema":"M10R_B2Y_CHROMACROSSWALK1A_V1",
      "img_record":{"id":"0x18","size":0x90,"setter":"IMG-System +0xd0770"},
      "sam7_api":{"name":"Im_B2Y_Ctrl_Chroma_Suppress","compact_size":COMPACT_SIZE,"writer":"IMG-SAM7 +0x51f1a"},
      "crosswalk":[{"compact_offset":hex(co),"width":w,"img_offset":hex(io)} for co,w,io in MAP],
      "alignment_padding_offsets":["0x3d"],
      "real_modes":real,
      "random_cases":args.cases,
      "random_cases_passed":random_passed,
      "all_mmio_identical":True,
      "interpretation":[
        "Record 0x18 and SAM7 b2y_ctrl_cs are two software representations of the same 0x20021100 Chroma Suppress hardware control block.",
        "The LOW/MEDIUM/HIGH-only six 14-bit fields map to compact offsets 0x04..0x0e.",
        "This establishes software/control identity but not downstream pixel arithmetic or stage order."
      ],
      "guardrails":[
        "No renderer code is changed.",
        "Do not infer Q13 multiply semantics solely from coefficient encoding.",
        "Do not infer pixel-stage placement from register-programming call order."
      ],
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    lines=[
      "# M10-R B2Y CHROMACROSSWALK1A","",
      "Cross-execution proof that IMG calibration record 0x18 and SAM7 Im_B2Y_Ctrl_Chroma_Suppress are two representations of the same hardware control block.","",
      "## Result","",
      "- All four real M10-R saturation modes produced identical MMIO output through IMG +0xD0770 and SAM7 +0x51F1A after packing.",
      f"- Randomized cross-execution cases passed: {random_passed}/{args.cases}.",
      f"- Compact SAM7 structure size used: 0x{COMPACT_SIZE:X} bytes.",
      "- The six LOW/MEDIUM/HIGH saturation-strength fields map to compact offsets 0x04,0x06,0x08,0x0A,0x0C,0x0E and registers 0x20021110..0x20021118.",
      "",
      "## Consequence","",
      "Record 0x18 is now structurally bound to Leica's named Im_B2Y_Ctrl_Chroma_Suppress API, not merely inferred from the IMG selector string.",
      "",
      "This still does not recover the B2Y hardware consumer equation or prove where Chroma Suppress sits relative to CC1/Yc in the pixel path. Those remain the next boundary before renderer implementation.",
      ""
    ]
    args.report.write_text("\n".join(lines))
    print(json.dumps({"real_modes":len(real),"random_cases_passed":random_passed,"all_mmio_identical":True},indent=2))

if __name__=="__main__": main()
