#!/usr/bin/env python3
"""YBLEND REFERENCE1E.

Same-shot Leica M10-R DNG/JPEG reference audit of four bounded Y/C chroma
inheritance models.  This is an offline discriminator, not a recovered ASIC
formula and not an Android renderer change.

Models:
  ABS_k0       scale = 1
  CURRENT_k035 scale = 1 + 0.35*(mappedY/inputY - 1)
  MID_k050     scale = 1 + 0.50*(mappedY/inputY - 1)
  REL_k100     scale = mappedY/inputY

Everything else in the frozen PHOTOAUDIT native-core mathematical mirror stays
unchanged: target matrices, CA9, Y/C conversion, MEDIUM, DG and CC1.
"""
from pathlib import Path
import sys,re,json,hashlib,os,math
import numpy as np
import cv2
from PIL import Image

STEP=4
PATCH=16
MODELS={
    "ABS_k0":0.0,
    "CURRENT_k035":0.35,
    "MID_k050":0.50,
    "REL_k100":1.0,
}
EXPECTED_CURRENT={
 "01":(2.047,5.473),"02":(2.676,2.903),"03":(2.658,7.907),
 "04":(2.460,3.518),"05":(1.923,10.861),"06":(2.479,11.696),
}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def nums(v):
    if isinstance(v,str):return np.array([float(x) for x in v.split()],dtype=np.float64)
    return np.asarray(v,dtype=np.float64)
def constant(s,name):
    m=re.search(r'\b'+name+r'\s*=\s*\{(.*?)\};',s,re.S)
    if not m:raise ValueError("missing "+name)
    return np.array([float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',m.group(1))])
def xform(a,m):
    return np.stack([a[...,0]*m[i,0]+a[...,1]*m[i,1]+a[...,2]*m[i,2] for i in range(3)],axis=-1)
def lab(rgb):
    return cv2.cvtColor(np.ascontiguousarray(rgb,dtype=np.float32).reshape(-1,1,3),cv2.COLOR_RGB2LAB).reshape(-1,3).astype(float)
def circ_abs_deg(a,b):
    d=np.abs(a-b)%360.0
    return np.minimum(d,360.0-d)
def metrics(a,b):
    d=a-b
    Cref=np.linalg.norm(b[:,1:],axis=1);Cr=np.linalg.norm(a[:,1:],axis=1)
    hue_ref=np.degrees(np.arctan2(b[:,2],b[:,1]))%360
    hue_r=np.degrees(np.arctan2(a[:,2],a[:,1]))%360
    chrom=Cref>=20
    warm=(b[:,1]>5)&(b[:,2]>5)&chrom
    out={
      "n":int(len(a)),
      "L_mae":float(np.mean(np.abs(d[:,0]))),
      "ab_error":float(np.mean(np.linalg.norm(d[:,1:],axis=1))),
      "DE76":float(np.mean(np.linalg.norm(d,axis=1))),
      "chroma_ratio_ref_ge20":float(np.mean(Cr[chrom]/Cref[chrom])) if np.any(chrom) else None,
      "hue_abs_error_deg_ref_ge20":float(np.mean(circ_abs_deg(hue_r[chrom],hue_ref[chrom]))) if np.any(chrom) else None,
      "warm_n":int(warm.sum()),
      "warm_ab_error":float(np.mean(np.linalg.norm(d[warm,1:],axis=1))) if np.any(warm) else None,
      "warm_chroma_ratio":float(np.mean(Cr[warm]/Cref[warm])) if np.any(warm) else None,
      "warm_hue_abs_error_deg":float(np.mean(circ_abs_deg(hue_r[warm],hue_ref[warm]))) if np.any(warm) else None,
    }
    return out
def patch_values(a,b):
    h,w=a.shape[:2];h=h//PATCH*PATCH;w=w//PATCH*PATCH
    def block(x):
        return x[:h,:w].reshape(h//PATCH,PATCH,w//PATCH,PATCH,3).transpose(0,2,1,3,4).reshape(-1,PATCH*PATCH,3)/255.
    aa,bb=block(a),block(b);ma,mb=aa.mean(1),bb.mean(1)
    sd=bb.std(1).max(1)
    good=(sd<.035)&(mb.mean(1)>.02)&(mb.mean(1)<.98)
    return lab(ma[good]),lab(mb[good]),int(good.sum())
def solve_alignment(a,b):
    h,w=a.shape[:2];ga=cv2.GaussianBlur(a.astype(np.float32).mean(2),(0,0),2);ga-=cv2.GaussianBlur(ga,(0,0),12)
    best=None
    for k in range(4):
        rb=np.rot90(b,k).copy()
        if rb.shape[:2]!=(h,w):continue
        gb=cv2.GaussianBlur(rb.astype(np.float32).mean(2),(0,0),2);gb-=cv2.GaussianBlur(gb,(0,0),12)
        for dy in range(-3,4):
            for dx in range(-3,4):
                aa=ga[12:-12,12:-12].ravel();bb=gb[12+dy:h-12+dy,12+dx:w-12+dx].ravel()
                den=np.sqrt(np.dot(aa,aa)*np.dot(bb,bb))
                score=float(np.dot(aa,bb)/den) if den else -1
                if best is None or score>best[0]:best=(score,k,dx,dy)
    if best is None:raise ValueError("alignment failed")
    score,k,dx,dy=best
    return {"corr":score,"k":k,"dx":dx,"dy":dy,"margin":16}
def apply_alignment(a,b,al):
    rb=np.rot90(b,al["k"]).copy();h,w=a.shape[:2];m=al["margin"];dx=al["dx"];dy=al["dy"]
    return a[m:h-m,m:w-m],rb[m+dy:h-m+dy,m+dx:w-m+dx]
def render(rgb,src,ca9,work,dst,tone,dg,k):
    tr=xform(rgb.astype(float)/65535.,src)
    tr=np.clip(tr*ca9/256.,0,1)*256./ca9
    w=xform(tr,work)
    y=(1224*w[...,0]+2403*w[...,1]+469*w[...,2])/4096.
    cb=(-691*w[...,0]-1357*w[...,1]+2048*w[...,2])/4096.
    cr=(2048*w[...,0]-1715*w[...,1]-333*w[...,2])/4096.
    xy=np.floor(np.clip(y,0,1)*16383+0.5).astype(np.int64)
    my=(xy*tone[xy>>1].astype(np.int64))>>15
    mapped=dg[np.clip(my,0,32767)]/16383.
    ratio=np.divide(mapped,y,out=np.zeros_like(y),where=y>1e-12)
    scale=np.where(y>1e-12,1.0+k*(ratio-1.0),0.0)
    cb2=cb*scale;cr2=cr*scale
    n=np.stack([
      mapped-.001043337611*cb2+1.401991725445*cr2,
      mapped-.345114690199*cb2-.714098755336*cr2,
      mapped+1.770975790582*cb2-.000124867533*cr2],-1)
    out=xform(n,dst)
    q=np.floor(np.clip(out,0,1)*255+.5).astype(np.uint8)
    return q,{
      "mean_scale":float(np.mean(scale[y>1e-12])),
      "p50_scale":float(np.median(scale[y>1e-12])),
      "p90_scale":float(np.quantile(scale[y>1e-12],.9)),
      "post_cc1_high_R_fraction":float(np.mean(out[...,0]>1)),
      "post_cc1_high_G_fraction":float(np.mean(out[...,1]>1)),
      "post_cc1_high_B_fraction":float(np.mean(out[...,2]>1)),
    }

def main():
    inputs,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
    for e in json.loads((inputs/"manifest.json").read_text()):
        p=inputs/e["path"];assert p.stat().st_size==e["bytes"] and sha(p)==e["sha256"]
    js=(inputs/"source/M10RNativeRenderer.java").read_text()
    cmA=constant(js,"M10_CM_A").reshape(3,3);cmD=constant(js,"M10_CM_D65").reshape(3,3)
    pcs=constant(js,"PCS_TO_INTERNAL").reshape(3,3);dst=constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    br=constant(js,"BRADFORD").reshape(3,3);d50xy=constant(js,"D50_XY")
    d50=np.array([d50xy[0]/d50xy[1],1,(1-d50xy.sum())/d50xy[1]])
    tone=np.fromfile(inputs/"assets/tone_medium_q15.u32le",dtype="<u4")
    dg=np.fromfile(inputs/"assets/dg_expanded_u16le.bin",dtype="<u2")
    assert len(tone)==10240 and len(dg)==32768
    result={"schema":"M10R_YBLEND_REFERENCE1E_V1","status":"STARTED","models":MODELS,
      "scope":"Same-shot genuine M10-R RAW/JPEG reference discriminator; Y/C chroma inheritance model only; no APK.",
      "reference_firmware_note":"Photography Blog pairs report Leica firmware 10.20.27.20; recovered tables are 30.22.23.34.",
      "scenes":[]}
    for sid in [f"{i:02d}" for i in range(1,7)]:
        meta=json.loads((inputs/"samples"/f"{sid}_metadata.json").read_text());j,d=meta["metadata"]
        assert np.max(abs(nums(d["ColorMatrix1"]).reshape(3,3)-cmA))<1e-7
        assert np.max(abs(nums(d["ColorMatrix2"]).reshape(3,3)-cmD))<1e-7
        asn=nums(d["AsShotNeutral"]);ca9=np.clip(np.rint(256/asn),1,2000).astype(int)
        kelvin=float(d["CorrelatedColorTemp"]);xy=nums(d["WhitePoint"])
        f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1);cm=f*cmA+(1-f)*cmD
        white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
        adaptation=np.linalg.inv(br)@np.diag((br@d50)/(br@white))@br
        work=pcs@adaptation@np.linalg.inv(cm)
        whiteY=float((np.linalg.inv(cm)@asn)[1])
        raw=np.load(inputs/"samples"/f"{sid}_raw.npz")["raw"]
        normalized=np.floor(np.clip(raw.astype(np.float64)/15000.,0,1)*65535+.5).astype(np.uint16);del raw
        ref=np.asarray(Image.open(inputs/"samples"/f"{sid}.jpg").convert("RGB"))
        H,W=min(ref.shape[:2]),max(ref.shape[:2]);rh,rw=normalized.shape
        top=(rh-H)//2;left=(rw-W)//2
        sample=np.empty(((H+STEP-1)//STEP,(W+STEP-1)//STEP,3),dtype=np.uint16)
        for y0 in range(0,rh,256):
            y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4)
            tile=cv2.cvtColor(normalized[hs:he],cv2.COLOR_BayerGB2BGR_EA)
            ys=np.arange(max(y0,top),min(y1,top+H));ys=ys[(ys-top)%STEP==0]
            if len(ys):sample[(ys-top)//STEP]=tile[ys-hs,left:left+W:STEP]
        del normalized
        ref=ref[::STEP,::STEP]
        scene={"id":sid,"ISO":j["ISO"],"kelvin":kelvin,"conditions":{}}
        for condition,factor in [("target_native",1.0),("white_normalized",1.0/whiteY)]:
            src=np.eye(3)*factor
            current,_=render(sample,src,ca9,work,dst,tone,dg,.35)
            al=solve_alignment(current,ref)
            assert al["corr"]>.75,al
            condition_rows={}
            for name,k in MODELS.items():
                image,stats=render(sample,src,ca9,work,dst,tone,dg,k)
                aa,bb=apply_alignment(image,ref,al)
                la,lb,npats=patch_values(aa,bb)
                m=metrics(la,lb);m["patches"]=npats;m["stage_stats"]=stats
                condition_rows[name]=m
                if condition=="target_native" and name in ("ABS_k0","CURRENT_k035","MID_k050","REL_k100"):
                    Image.fromarray(aa).save(out/f"{sid}_{name}.jpg",quality=92)
            scene["conditions"][condition]={"alignment":al,"models":condition_rows}
        result["scenes"].append(scene)
        (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    # Baseline sanity against published PHOTOAUDIT1B native metrics. Mirror is allowed <=1 code.
    sanity={}
    for s in result["scenes"]:
        got=s["conditions"]["target_native"]["models"]["CURRENT_k035"]
        exp=EXPECTED_CURRENT[s["id"]]
        sanity[s["id"]]={"L_delta":got["L_mae"]-exp[0],"ab_delta":got["ab_error"]-exp[1]}
        assert abs(sanity[s["id"]]["L_delta"])<0.12,(s["id"],sanity[s["id"]])
        assert abs(sanity[s["id"]]["ab_delta"])<0.12,(s["id"],sanity[s["id"]])
    result["published_baseline_sanity"]=sanity
    # Equal-scene aggregates; no fitting, so report all and held-out 02/04/06.
    ag={}
    for cond in ("target_native","white_normalized"):
        ag[cond]={}
        for name in MODELS:
            rows=[s["conditions"][cond]["models"][name] for s in result["scenes"]]
            held=[s["conditions"][cond]["models"][name] for s in result["scenes"] if s["id"] in ("02","04","06")]
            keys=["L_mae","ab_error","DE76","chroma_ratio_ref_ge20","hue_abs_error_deg_ref_ge20","warm_ab_error","warm_chroma_ratio","warm_hue_abs_error_deg"]
            ag[cond][name]={
              "all_scene_equal":{k:float(np.mean([x[k] for x in rows if x[k] is not None])) for k in keys},
              "heldout_scene_equal":{k:float(np.mean([x[k] for x in held if x[k] is not None])) for k in keys},
            }
    result["aggregates"]=ag
    result["status"]="PASS_YBLEND_REFERENCE_DISCRIMINATOR"
    result["script_sha256"]=sha(__file__)
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# M10-R YBLEND REFERENCE1E","",
      "Same-shot genuine M10-R RAW/JPEG discriminator. Only Y/C chroma inheritance changes. No ASIC-equation claim and no APK.","",
      "## Target-native equal-scene aggregate","",
      "| Model | L* MAE | a*b* error | DE76 | Chroma ratio | Hue err deg | Warm a*b* | Warm chroma ratio | Warm hue err |",
      "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in MODELS:
        m=ag["target_native"][name]["all_scene_equal"]
        lines.append(f"| {name} | {m['L_mae']:.3f} | {m['ab_error']:.3f} | {m['DE76']:.3f} | {m['chroma_ratio_ref_ge20']:.3f} | {m['hue_abs_error_deg_ref_ge20']:.2f} | {m['warm_ab_error']:.3f} | {m['warm_chroma_ratio']:.3f} | {m['warm_hue_abs_error_deg']:.2f} |")
    lines+=["","## Guardrails","",
      "- k=0.50 is a midpoint hypothesis only; p1=32 has not been proven to use denominator 64.",
      "- A lower error does not prove hardware arithmetic.",
      "- Reference firmware version differs from recovered firmware tables.",
      "- No phone capture/exposure/frontend behavior is evaluated.",
      "- Do not promote a renderer solely from this sweep.",""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print(json.dumps(result["aggregates"]["target_native"],indent=2))
if __name__=="__main__":main()
