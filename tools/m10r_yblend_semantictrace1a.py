#!/usr/bin/env python3
"""Y_BLEND SEMANTICTRACE1A.

Static/executable evidence pass after D4480 PRODUCER1A.

Goals:
1) census exact normal Y_BLEND payload/compact-ABI duplicates and plausible
   mode variants across verified extracted firmware sections;
2) census direct calls and stored function pointers for IMG D4480 and SAM7
   Im_B2Y_Ctrl_Yc_Convert (0x51DA6);
3) verify the watched Y_BLEND MMIO page has no additional literal owner hidden
   by the earlier named-control search;
4) emit bounded context for any pointer/table occurrences so the next pass can
   trace an indirect dispatcher if one exists.

This DOES NOT recover ISP pixel arithmetic and makes no photographic claim.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM

IMG_SHA="53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4"
SAM_SHA="c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae"
B2Y_SHA="ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b"

IMG_D4480=0x000d4480
SAM_YCC=0x00051da6
MMIO_BASE=0x20020900
WATCH=(0x2002092c,0x20020930,0x20020934)

NORMAL_U32=[0,32,0x3fff,0x3fff,0x3fff,0x3fff]
NORMAL_RAW=struct.pack("<6I",*NORMAL_U32)
NORMAL_COMPACT_TAIL=bytes.fromhex("0020ff3fff3fff3fff3fff3f")
FULL_COMPACT=bytes.fromhex(
    "c8046309d5014dfdb3fa000800084df9b3feff3fff3fff3fff3fff3fff3f"
    "0020ff3fff3fff3fff3fff3f"
)

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def direct_thumb_bl_hits(data:bytes,target:int)->list[int]:
    hits=[]
    n=len(data)
    for pc in range(0,n-3,2):
        h1=data[pc] | (data[pc+1]<<8)
        if (h1 & 0xf800) != 0xf000:
            continue
        h2=data[pc+2] | (data[pc+3]<<8)
        if (h2 & 0xd000) != 0xd000:
            continue
        s=(h1>>10)&1; imm10=h1&0x3ff
        j1=(h2>>13)&1; j2=(h2>>11)&1; imm11=h2&0x7ff
        i1=(~(j1^s))&1; i2=(~(j2^s))&1
        imm=(s<<24)|(i1<<23)|(i2<<22)|(imm10<<12)|(imm11<<1)
        if imm&(1<<24): imm-=1<<25
        dest=(pc+4+imm)&0xffffffff
        if dest==target:hits.append(pc)
    return hits

def find_all(data:bytes,needle:bytes)->list[int]:
    out=[];p=0
    while True:
        i=data.find(needle,p)
        if i<0:return out
        out.append(i);p=i+1

def safe_ascii(b:bytes)->str:
    return ''.join(chr(x) if 32<=x<127 else '.' for x in b)

def words_context(data:bytes,off:int,radius_words:int=8):
    lo=max(0,(off&~3)-radius_words*4)
    hi=min(len(data),((off+3)&~3)+(radius_words+1)*4)
    rows=[]
    for p in range(lo,hi,4):
        if p+4<=len(data):
            v=struct.unpack_from("<I",data,p)[0]
            rows.append({"off":hex(p),"u32":hex(v)})
    return rows

def load_sections(secdir:Path):
    rows=[]
    with (secdir/"sections.csv").open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p=secdir/r["file"]
            rows.append({
                "index":int(r["index"]),
                "name":r["name"],
                "file":r["file"],
                "path":p,
                "size":int(r["size"]),
                "kind":r["kind"],
                "image_base":r["image_base"],
            })
    return rows

def plausible_yblend_windows(data:bytes):
    """4-byte aligned 24-byte windows shaped like D4480's 6xU32 ABI.

    Deliberately narrow to keep false positives bounded:
    p0,p1 <= 63 and each paired field is one of values observed in the
    normal/fallback programming families or exact 14/15-bit full-scale values.
    """
    allowed={0,0x1fff,0x3fff,0x7fff,0x8000,0xffff}
    out=[]
    for p in range(0,len(data)-23,4):
        vals=struct.unpack_from("<6I",data,p)
        if vals[0]<=63 and vals[1]<=63 and all(v in allowed for v in vals[2:]):
            out.append((p,list(vals)))
    return out

def pc_literal_refs_thumb(data:bytes,value:int):
    """Find Thumb LDR-literal instructions whose resolved pool word equals value.

    Bounded static decode, not a control-flow proof.
    """
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    refs=[]
    # Linear decode per halfword, single instruction, to avoid losing sync on data.
    for pc in range(0,len(data)-4,2):
        xs=list(md.disasm(data[pc:pc+4],pc,count=1))
        if not xs:continue
        i=xs[0]
        if i.mnemonic not in ("ldr","ldr.w") or len(i.operands)<2:
            continue
        op=i.operands[1]
        # Capstone ARM memory op: base PC and displacement.
        if getattr(op,"type",None)!=3: # ARM_OP_MEM
            continue
        mem=op.mem
        if i.reg_name(mem.base)!="pc":
            continue
        pool=((pc+4)&~3)+mem.disp
        if 0<=pool<=len(data)-4:
            v=struct.unpack_from("<I",data,pool)[0]
            if v==value:
                refs.append({"pc":hex(pc),"pool":hex(pool),"op":i.op_str})
    return refs

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()

    rows=load_sections(args.sections)
    byfile={r["file"]:r for r in rows}
    img=(args.sections/"092_IMG-System.bin").read_bytes()
    sam=(args.sections/"100_IMG-SAM7.bin").read_bytes()
    b2y=(args.sections/"074_IMG_Calibration_Data_data_calib_B2Y.bin.bin").read_bytes()
    assert sha(img)==IMG_SHA
    assert sha(sam)==SAM_SHA
    assert sha(b2y)==B2Y_SHA

    exact=[]
    compact=[]
    strings=[]
    candidates=[]
    patterns=[
        ("normal_record0d_u32",NORMAL_RAW),
        ("normal_compact_yblend_tail",NORMAL_COMPACT_TAIL),
        ("full_ycc_yblend_compact_40B",FULL_COMPACT),
    ]
    string_needles=[b"Y BLEND",b"y_blend",b"Y_BLEND",b"Im_B2Y_Ctrl_Yc_Convert"]

    for r in rows:
        data=r["path"].read_bytes()
        for label,needle in patterns:
            for off in find_all(data,needle):
                (compact if "compact" in label else exact).append({
                    "label":label,"section":r["file"],"section_name":r["name"],
                    "offset":hex(off),"context_sha256":sha(data[max(0,off-32):min(len(data),off+len(needle)+32)])
                })
        for needle in string_needles:
            for off in find_all(data,needle):
                strings.append({
                    "needle":needle.decode("ascii"),"section":r["file"],"section_name":r["name"],
                    "offset":hex(off),
                    "ascii_context":safe_ascii(data[max(0,off-48):min(len(data),off+len(needle)+96)])
                })
        # Candidate D4480 ABI windows only for calibration/data-ish sections or exact B2Y section,
        # keeping scope bounded.
        lname=(r["name"]+" "+r["file"]).lower()
        if "calib" in lname or "b2y" in lname:
            for off,vals in plausible_yblend_windows(data):
                candidates.append({
                    "section":r["file"],"section_name":r["name"],
                    "offset":hex(off),"u32":vals,
                    "is_exact_normal":vals==NORMAL_U32,
                })

    # Direct calls.
    img_bl=direct_thumb_bl_hits(img,IMG_D4480)
    sam_bl=direct_thumb_bl_hits(sam,SAM_YCC)

    # Stored code pointers: raw even and Thumb-bit forms.
    pointer_hits={}
    for label,data,target in [
        ("IMG_D4480",img,IMG_D4480),("SAM_YCC",sam,SAM_YCC)
    ]:
        hs=[]
        for vkind,v in [("even",target),("thumb",target|1)]:
            for off in find_all(data,struct.pack("<I",v)):
                hs.append({
                    "kind":vkind,"offset":hex(off),
                    "surrounding_words":words_context(data,off,10),
                    "ascii_context":safe_ascii(data[max(0,off-48):min(len(data),off+80)]),
                })
        pointer_hits[label]=hs

    # MMIO literal census in both executable sections.
    mmio={}
    for label,data in [("IMG",img),("SAM7",sam)]:
        mmio[label]={}
        for value in (MMIO_BASE,)+WATCH:
            raw=find_all(data,struct.pack("<I",value))
            # Only run PC-literal ref decode for the page base / watched words.
            refs=pc_literal_refs_thumb(data,value)
            mmio[label][hex(value)]={
                "raw_u32_occurrences":[hex(x) for x in raw],
                "thumb_pc_literal_refs":refs,
            }

    # Canonical assertions / useful negative results.
    normal_exact=[x for x in exact if x["label"]=="normal_record0d_u32"]
    b2y_exact=[x for x in normal_exact if x["section"]=="074_IMG_Calibration_Data_data_calib_B2Y.bin.bin"]
    assert any(int(x["offset"],16)==0x131874 for x in b2y_exact)
    assert 0x154e68 in img_bl
    # SAM7 function can be indirectly dispatched; do not require a direct BL.
    assert any(x["needle"]=="Im_B2Y_Ctrl_Yc_Convert" and x["section"]=="100_IMG-SAM7.bin" for x in strings)

    report={
        "schema":"M10R_YBLEND_SEMANTICTRACE1A_V1",
        "scope":"bounded firmware static census after D4480 producer provenance; NOT pixel arithmetic",
        "hashes":{"img":IMG_SHA,"sam7":SAM_SHA,"b2y":B2Y_SHA},
        "exact_payload_occurrences":exact,
        "compact_occurrences":compact,
        "specific_strings":strings,
        "plausible_yblend_abi_windows":candidates,
        "direct_thumb_calls":{
            "IMG_D4480":[hex(x) for x in img_bl],
            "SAM7_0x51DA6":[hex(x) for x in sam_bl],
        },
        "stored_function_pointer_occurrences":pointer_hits,
        "mmio_literal_census":mmio,
        "interpretation_guardrails":[
            "A raw pointer/table occurrence is not proof of a call unless control flow is established.",
            "No direct BL to SAM7 0x51DA6 would imply an indirect/API-dispatch path is likely, not that the function is unused.",
            "Plausible 6xU32 windows are candidate data shapes only; they are not Y BLEND records without record/container provenance.",
            "No result in this pass establishes p1=32 fixed-point semantics or a pixel equation."
        ],
        "all_assertions_passed":True,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
