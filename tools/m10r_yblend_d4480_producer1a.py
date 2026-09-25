#!/usr/bin/env python3
"""D4480 PRODUCER1A: source-anchor the normal M10-R Y BLEND field producer.

This tool does NOT recover ISP pixel arithmetic. It establishes, with executable
checks, the software path from B2Y calibration record 0x0D into the D4480
register programmer and distinguishes the normal record path from fallback.

Evidence:
- independently parse record 0x0D from verified B2Y calibration data;
- verify the selector's sequential Thumb dataflow: lookup(0x0D) result is passed
  directly to D4480 as r0, while r1 is the fallback flag;
- execute original D4480 instructions with the real record and with one-field
  perturbations to prove which record field controls which destination bits.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_REG

IMG_SHA="53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4"
B2Y_SHA="ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b"
SELECTOR=0x154e18
LOOKUP=0x1a0fc4
DRIVER=0xd4480
WATCH=(0x2002092c,0x20020930,0x20020934)

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError("module spec "+str(path))
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def insns(img:bytes,start:int,end:int):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    return list(md.disasm(img[start:end],start))

def assert_selector_flow(img:bytes):
    seq=insns(img,SELECTOR,0x154e70)
    by={i.address:i for i in seq}
    def need(pc,mnemonic):
        i=by.get(pc)
        if i is None or i.mnemonic!=mnemonic:
            raise AssertionError(f"selector {pc:#x}: expected {mnemonic}, got {i}")
        return i
    i=need(0x154e48,"movs")
    assert i.reg_name(i.operands[0].reg)=="r1" and i.operands[1].type==ARM_OP_IMM and i.operands[1].imm==0x0d
    i=need(0x154e4c,"bl"); assert i.operands[0].imm==LOOKUP
    i=need(0x154e50,"movs")
    assert i.reg_name(i.operands[0].reg)=="r4" and i.reg_name(i.operands[1].reg)=="r0"
    # r4 is not written again before it is moved into r0 for D4480.
    for x in seq:
        if 0x154e52 <= x.address < 0x154e66:
            _reads,writes=x.regs_access()
            if any(x.reg_name(reg)=="r4" for reg in writes):
                raise AssertionError(f"selector rewrites record pointer r4 at {x.address:#x}")
    i=need(0x154e64,"movs")
    assert i.reg_name(i.operands[0].reg)=="r1" and i.reg_name(i.operands[1].reg)=="r6"
    i=need(0x154e66,"movs")
    assert i.reg_name(i.operands[0].reg)=="r0" and i.reg_name(i.operands[1].reg)=="r4"
    i=need(0x154e68,"bl"); assert i.operands[0].imm==DRIVER

    # r6 starts at zero and is set to one only on lookup failure.
    i=need(0x154e20,"movs")
    assert i.reg_name(i.operands[0].reg)=="r6" and i.operands[1].imm==0
    i=need(0x154e56,"movs")
    assert i.reg_name(i.operands[0].reg)=="r6" and i.operands[1].imm==1

    return [{
      "pc":hex(i.address),"mnemonic":i.mnemonic,"op_str":i.op_str
    } for i in seq if i.address in (0x154e20,0x154e48,0x154e4c,0x154e50,0x154e56,0x154e64,0x154e66,0x154e68)]

def direct_bl_census(img:bytes,target:int):
    # Decode all halfword-aligned potential Thumb-2 BL instructions. A data word
    # can coincidentally encode a branch, so this is a direct-encoding census,
    # not proof against indirect calls.
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    hits=[]
    for pc in range(0,len(img)-4,2):
        xs=list(md.disasm(img[pc:pc+4],pc,count=1))
        if not xs:continue
        i=xs[0]
        if i.mnemonic=="bl" and i.size==4 and i.operands and i.operands[0].type==ARM_OP_IMM and i.operands[0].imm==target:
            hits.append(pc)
    return hits

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("sections",type=Path)
    ap.add_argument("repo",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()

    img=(args.sections/"092_IMG-System.bin").read_bytes()
    if sha(img)!=IMG_SHA:raise RuntimeError("IMG-System hash mismatch")
    b2yp=args.sections/"074_IMG_Calibration_Data_data_calib_B2Y.bin.bin"
    b2y=b2yp.read_bytes()
    if sha(b2y)!=B2Y_SHA:raise RuntimeError("B2Y calibration hash mismatch")

    assets=load_module(args.repo/"tools"/"m10r_b2y_assets.py","m10r_b2y_assets_producer1a")
    records=assets.parse_records(b2y)
    recs=[r for r in records if r.record_id==0x0d]
    if len(recs)!=1:raise AssertionError(f"record 0x0D count {len(recs)}")
    rec=recs[0]
    raw=b2y[rec.payload_offset:rec.payload_offset+rec.size]
    if rec.size!=24:raise AssertionError(f"record 0x0D size {rec.size}")
    vals=list(struct.unpack("<6I",raw))
    expected=[0,32,0x3fff,0x3fff,0x3fff,0x3fff]
    if vals!=expected:raise AssertionError((vals,expected))

    selector_trace=assert_selector_flow(img)
    bl_hits=direct_bl_census(img,DRIVER)
    if 0x154e68 not in bl_hits:raise AssertionError("canonical D4480 BL missing")

    audit=load_module(args.repo/"tools"/"m10r_yblend_bit15_audit1a.py","m10r_yblend_bit15_audit1a_producer")
    p=audit.Programmer(img)
    old=bytes(0x4000)

    def run(v,fallback=0):
        got=p.run(DRIVER,struct.pack("<6I",*v),old,fallback)
        return {hex(a):int.from_bytes(got[a-0x20020000:a-0x20020000+4],"little") for a in WATCH}

    normal=run(vals,0)
    fallback=run(vals,1)
    assert normal=={
      "0x2002092c":0x00002000,
      "0x20020930":0x3fff3fff,
      "0x20020934":0x3fff3fff,
    }
    assert fallback=={
      "0x2002092c":0x00000000,
      "0x20020930":0x80007fff,
      "0x20020934":0x80007fff,
    }

    base=run([0,0,0,0,0,0],0)
    probes=[17,23,0x1234,0x5678,0x2345,0x6789]
    influence=[]
    for idx,value in enumerate(probes):
        v=[0]*6;v[idx]=value
        out=run(v,0)
        changed={k:{"before":base[k],"after":out[k],"xor":base[k]^out[k]} for k in base if base[k]!=out[k]}
        influence.append({"field":f"p{idx}","probe_value":value,"changed_registers":changed})
        if len(changed)!=1:raise AssertionError(f"p{idx} influence {changed}")

    expect_regs=[
      "0x2002092c","0x2002092c","0x20020930","0x20020930","0x20020934","0x20020934"
    ]
    for row,reg in zip(influence,expect_regs):
        if list(row["changed_registers"])!=[reg]:raise AssertionError(row)

    report={
      "schema":"M10R_YBLEND_D4480_PRODUCER1A_V1",
      "scope":"software calibration/selector/register-programmer provenance; NOT ISP pixel arithmetic",
      "firmware_evidence":{
        "img_system_sha256":IMG_SHA,
        "b2y_calibration_sha256":B2Y_SHA,
      },
      "record_0x0d":{
        "count":len(recs),
        "index":rec.index,
        "payload_offset":hex(rec.payload_offset),
        "size_bytes":rec.size,
        "raw_hex":raw.hex(),
        "raw_sha256":sha(raw),
        "u32_le":vals,
      },
      "selector":{
        "function":hex(SELECTOR),
        "record_id":hex(0x0d),
        "lookup":hex(LOOKUP),
        "driver":hex(DRIVER),
        "sequential_dataflow":selector_trace,
        "normal_semantic":"lookup result pointer is passed directly to D4480; fallback flag r1=0",
        "lookup_failure_semantic":"r6 becomes 1, r0 remains null lookup result, D4480 uses fallback constants",
      },
      "direct_bl_census":{
        "target":hex(DRIVER),
        "halfword_aligned_encodings":[hex(x) for x in bl_hits],
        "canonical_site_present":True,
        "completeness_claim":False,
        "limitation":"direct Thumb BL encodings only; indirect calls are not excluded",
      },
      "original_d4480_execution":{
        "normal_from_exact_record":normal,
        "fallback_with_same_record_pointer":fallback,
        "field_influence":influence,
        "bit15_mutations_observed":len(p.bit15_changes),
      },
      "new_constraint":[
        "Normal record 0x0D is a single 24-byte B2Y calibration payload, not synthesized by the selector.",
        "The selector passes the lookup-returned record pointer directly to D4480 without per-field arithmetic.",
        "p0 and p1 independently control the two six-bit fields in 0x2002092C; p2/p3 control 0x20020930; p4/p5 control 0x20020934.",
        "Fallback is selected by the selector's lookup-failure flag and replaces the normal record values inside D4480.",
      ],
      "still_unresolved":[
        "pixel-domain source signals blended by Y BLEND",
        "meaning/denominator of p0=0 and p1=32",
        "semantics of paired 0x3FFF fields",
        "hardware scaling, rounding, clipping and stage order",
      ],
      "all_assertions_passed":True,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
