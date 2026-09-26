#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM,ARM_OP_REG,ARM_OP_MEM,ARM_REG_PC
import m10r_b2y_assets as assets

LABELS=("M10R-20.20.47.37","M10M-2.12.8.0","M10M-3.21.2.50")
TARGETS={0x06:("colorcorrection0",64,0x20020100),0x0A:("colorcorrection1",68,0x20020880)}

def sha(b): return hashlib.sha256(b).hexdigest()
def s32(v): return v-0x100000000 if v&0x80000000 else v
def rows(sec):
    with (sec/"sections.csv").open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def section(sec,needle):
    h=[sec/r["file"] for r in rows(sec) if needle.lower() in (r["name"]+" "+r["file"]).lower()]
    if len(h)!=1:raise RuntimeError(f"{needle}: {h}")
    return h[0]
def b2y(sec):
    h=[sec/r["file"] for r in rows(sec) if "data/calib/b2y.bin" in (r["name"]+" "+r["file"]).lower()]
    if len(h)==1:return h[0],"named"
    h=[]
    for r in rows(sec):
        t=(r["name"]+" "+r["file"]).lower()
        if "calibration data" not in t and "calib" not in t:continue
        p=sec/r["file"]
        try:q=assets.parse_records(p.read_bytes())
        except:continue
        if len([x for x in q if x.record_id==0x0c and x.size==60])==1 and len([x for x in q if x.record_id==0x0d and x.size==24])==1:h.append(p)
    if len(h)!=1:raise RuntimeError(f"B2Y: {h}")
    return h[0],"structural_0C0D"
def one(md,data,pc):
    x=list(md.disasm(data[pc:pc+4],pc,count=1));return x[0] if x else None
def page_near(data,target,page):
    return data.find(struct.pack("<I",page),max(0,target),min(len(data),target+0x380))>=0
def selector(img,rid,page):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True;hits=[]
    for pc in range(0,len(img)-4,2):
        i=one(md,img,pc)
        if not i or i.mnemonic!="movs" or len(i.operands)<2:continue
        if i.operands[0].type!=ARM_OP_REG or i.reg_name(i.operands[0].reg)!="r1":continue
        if i.operands[1].type!=ARM_OP_IMM or i.operands[1].imm!=rid:continue
        lookup=None
        for q in range(pc+2,min(len(img)-4,pc+0x12),2):
            j=one(md,img,q)
            if j and j.mnemonic=="bl" and j.operands and j.operands[0].type==ARM_OP_IMM:
                lookup=(q,j.operands[0].imm);break
        if not lookup:continue
        setter=None
        for q in range(lookup[0]+2,min(len(img)-4,lookup[0]+0x44),2):
            j=one(md,img,q)
            if j and j.mnemonic=="bl" and j.operands and j.operands[0].type==ARM_OP_IMM:
                t=j.operands[0].imm
                if t!=lookup[1] and page_near(img,t,page):setter=(q,t);break
        if setter:hits.append((pc,lookup,setter))
    uniq=[];seen=set()
    for pc,l,s in hits:
        k=(pc,l[1],s[1])
        if k not in seen:seen.add(k);uniq.append((pc,l,s))
    if len(uniq)!=1:raise RuntimeError(f"rid {rid:#x} candidates {uniq}")
    pc,l,s=uniq[0]
    return dict(record_id_pc=pc,lookup_call_pc=l[0],lookup_target=l[1],setter_call_pc=s[0],setter_target=s[1])
def setter_static(img,entry):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    end=min(len(img),entry+0x360)
    for pc in range(entry+2,end,2):
        i=one(md,img,pc)
        if i and i.mnemonic=="push" and "lr" in i.op_str and pc>entry+0x20:
            end=pc;break
    block=img[entry:end];lits=[];param=[]
    for i in md.disasm(block,entry):
        if i.mnemonic.startswith("ldr") and len(i.operands)>=2 and i.operands[1].type==ARM_OP_MEM:
            m=i.operands[1].mem
            if m.base==ARM_REG_PC:
                la=((i.address+4)&~3)+m.disp
                if 0<=la<=len(img)-4:
                    v=struct.unpack_from("<I",img,la)[0]
                    if 0x20020000<=v<0x20024000:lits.append(dict(pc=hex(i.address),literal_address=hex(la),value=hex(v)))
            elif i.reg_name(m.base)=="r0":
                param.append(dict(pc=hex(i.address),mnemonic=i.mnemonic,offset=hex(m.disp)))
    return dict(start=hex(entry),end=hex(end),size=end-entry,sha256=sha(block),mmio_literals=lits,direct_r0_param_loads=param)
def analyze(label,sec,fw,dec):
    bp,ident=b2y(sec);ip=section(sec,"IMG-System");bb=bp.read_bytes();im=ip.read_bytes();recs=assets.parse_records(bb)
    out=dict(label=label,firmware_sha256=fw,decoded_sha256=dec,b2y_sha256=sha(bb),img_sha256=sha(im),b2y_identification=ident,records={})
    for rid,(name,size,page) in TARGETS.items():
        rr=[r for r in recs if r.record_id==rid]
        if len(rr)!=1 or rr[0].size!=size:raise RuntimeError(f"{label} {rid:#x} count/size")
        r=rr[0];blob=bb[r.payload_offset:r.payload_offset+r.size];u=list(struct.unpack("<"+"I"*(len(blob)//4),blob));sel=selector(im,rid,page)
        out["records"][f"0x{rid:02x}"]=dict(name=name,index=r.index,relative_offset=hex(r.rel_offset),payload_offset=hex(r.payload_offset),size=r.size,
          payload_sha256=sha(blob),raw_hex=blob.hex(),u32=u,s32=[s32(x) for x in u],
          selector={k:hex(v) for k,v in sel.items()},setter=setter_static(im,sel["setter_target"]))
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("--item",action="append",required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True);a=p.parse_args()
    spec=[]
    for x in a.item:
        q=x.split("|",3)
        if len(q)!=4:raise SystemExit("bad item")
        spec.append((q[0],Path(q[1]),q[2],q[3]))
    if tuple(x[0] for x in spec)!=LABELS:raise SystemExit("bad labels")
    items={l:analyze(l,s,f,d) for l,s,f,d in spec};result=dict(schema="M10R_B2Y_CC01TRACE1A_V1",labels=list(LABELS),items=items,records={})
    md=["# M10-R B2Y CC01TRACE1A","","Static firmware trace only; renderer remains frozen.",""]
    for rid in TARGETS:
        k=f"0x{rid:02x}";vals={l:items[l]["records"][k]["u32"] for l in LABELS};n=len(vals[LABELS[0]]);words=[]
        for i in range(n):
            v={l:vals[l][i] for l in LABELS};words.append(dict(index=i,offset=hex(i*4),status="equal" if len(set(v.values()))==1 else "changed",values={l:f"0x{x:08x}" for l,x in v.items()}))
        result["records"][k]=dict(words=words,setter_code_sha256={l:items[l]["records"][k]["setter"]["sha256"] for l in LABELS},
          setter_code_equal_all=len({items[l]["records"][k]["setter"]["sha256"] for l in LABELS})==1)
        md += [f"## {k} {TARGETS[rid][0]}","",f"Changed words: {sum(x['status']=='changed' for x in words)} / {n}",f"Setter code equal all: {result['records'][k]['setter_code_equal_all']}","",
          "| Word | Offset | M10-R | Mono 2.12.8.0 | Mono 3.21.2.50 |","|---:|---:|---:|---:|---:|"]
        for w in words:
            if w["status"]=="changed":
                v=w["values"];md.append(f"| {w['index']} | {w['offset']} | {v[LABELS[0]]} | {v[LABELS[1]]} | {v[LABELS[2]]} |")
        md += ["","### Setter recovery",""]
        for l in LABELS:
            r=items[l]["records"][k];s=r["selector"];st=r["setter"]
            md.append(f"- {l}: selector {s['record_id_pc']}, lookup {s['lookup_target']}, setter {s['setter_target']}, code SHA {st['sha256']}, MMIO literals {','.join(x['value'] for x in st['mmio_literals'])}")
        md += [""]
    md += ["## Interpretation","","0x06 and 0x0A are clean model-specific calibration differences. 0x0C and 0x0D remain invariant controls. No renderer change is justified until field/register semantics are traced and reproduced offline.",""]
    a.out.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n");a.report.write_text("\n".join(md))
    print(json.dumps({k:{"changed_words":sum(x["status"]=="changed" for x in v["words"]),"setter_code_equal_all":v["setter_code_equal_all"]} for k,v in result["records"].items()},indent=2))
if __name__=="__main__":main()
