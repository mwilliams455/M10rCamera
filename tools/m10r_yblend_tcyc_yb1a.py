#!/usr/bin/env python3
"""M10-R YBLEND TCYC/YB1A.

Source-backed offline discriminator for the two-luminance R2Y topology.

Known Leica/SAM7 facts used:
- TONE row / TCYC = [1024,2661,410] (12-bit fields; sum 4095)
- CC0 trailing row / CCYC = [77,150,29] (8-bit fields; sum 256)
- final YC row = [1224,2403,469] / 4096
- normal TONE: RGB tone enabled, Yb tone disabled, TCYOUT selects TCYC-derived Y
- normal Y BLEND register controls = (YYBLND,YBBLND) = (0,32)

Related Fujitsu/Socionext R2Y source names YYBLND/YBBLND as luminance Y/Yb
blend ratios with documented range 0..32. It does not expose the pixel
equation for the Leica revision. Therefore every candidate below is an
explicit topology hypothesis, not a hardware-equation claim.

Primary holdout: public Leica M10-R pairs 07..10.
No candidate parameters are fitted.
"""
from __future__ import annotations
from pathlib import Path
import hashlib,json,subprocess,urllib.request,shutil,sys
import numpy as np
import cv2
from PIL import Image
import rawpy

import m10r_yblend_reference1e as ref1e

STEP=4
MODELS=(
    "CURRENT_k035",
    "MID_k050",
    "TCYC_ABS",
    "TCYC_RGB",
    "TCYC_RGB_YB32",
)
TCYC=np.array([1024.0,2661.0,410.0])/4096.0
CCYC=np.array([77.0,150.0,29.0])/256.0
YC=np.array([1224.0,2403.0,469.0])/4096.0
CB=np.array([-691.0,-1357.0,2048.0])/4096.0
CR=np.array([2048.0,-1715.0,-333.0])/4096.0
INV=np.array([
 [1.000000000000,-0.001043337611, 1.401991725445],
 [1.000000000000,-0.345114690199,-0.714098755336],
 [1.000000000000, 1.770975790582,-0.000124867533],
],dtype=np.float64)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fresh(sid:str,inputs:Path):
    d=inputs/"fresh";d.mkdir(exist_ok=True)
    paths=[]
    for ext in ("jpg","dng"):
        p=d/f"{sid}.{ext}"
        u=f"https://img.photographyblog.com/reviews/leica_m10_r/sample_images/leica_m10_r_{sid}.{ext}"
        if not p.exists():
            subprocess.run(["curl","-L","--fail","--retry","3","--retry-delay","2",u,"-o",str(p)],check=True)
        paths.append(p)
    meta=json.loads(subprocess.check_output(["exiftool","-j","-n",*map(str,paths)]))
    with rawpy.imread(str(paths[1])) as r:
        raw=r.raw_image.copy()
        pattern=r.raw_pattern.tolist()
        black=list(r.black_level_per_channel)
        white=int(r.white_level)
    return {
      "id":sid,"metadata":meta,"raw_pattern":pattern,
      "black_level_per_channel":black,"white_level":white,
      "jpg_sha256":sha(paths[0]),"dng_sha256":sha(paths[1])
    },raw,paths[0]

def map_scalar(v,tone,dg):
    q=np.floor(np.clip(v,0,1)*16383.0+0.5).astype(np.int64)
    m=(q*tone[q>>1].astype(np.int64))>>15
    return dg[np.clip(m,0,32767)]/16383.0

def ca9clip(x,ca9):
    # Same neutral-domain saturation used by the established reference mirror.
    y=x*ca9/256.0
    y=np.clip(y,0.0,1.0)
    return y*256.0/ca9

def final_from_ycc(y,cb,cr,dst):
    n=np.stack([
      y+INV[0,1]*cb+INV[0,2]*cr,
      y+INV[1,1]*cb+INV[1,2]*cr,
      y+INV[2,1]*cb+INV[2,2]*cr,
    ],axis=-1)
    out=ref1e.xform(n,dst)
    return np.floor(np.clip(out,0,1)*255+0.5).astype(np.uint8),out

def render_models(rgb,src,ca9,work,dst,tone,dg):
    tr=ref1e.xform(rgb.astype(np.float64)/65535.0,src)
    tr=ca9clip(tr,ca9.reshape(1,1,3))
    w=ref1e.xform(tr,work)

    y=np.tensordot(w,YC,axes=([-1],[0]))
    cb=np.tensordot(w,CB,axes=([-1],[0]))
    cr=np.tensordot(w,CR,axes=([-1],[0]))
    mapped_y=map_scalar(y,tone,dg)
    ratio_y=np.divide(mapped_y,y,out=np.zeros_like(y),where=np.abs(y)>1e-12)

    outputs={}
    stats={}

    # Existing reconstruction control.
    for name,k in (("CURRENT_k035",0.35),("MID_k050",0.50)):
        sc=np.where(np.abs(y)>1e-12,1.0+k*(ratio_y-1.0),0.0)
        im,out=final_from_ycc(mapped_y,cb*sc,cr*sc,dst)
        outputs[name]=im
        stats[name]=stage_stats(sc,out)

    # Recovered tone-coordinate row, but retain absolute final YC chroma.
    ytc=np.tensordot(w,TCYC,axes=([-1],[0]))
    mapped_t=map_scalar(ytc,tone,dg)
    ratio_t=np.divide(mapped_t,ytc,out=np.zeros_like(ytc),where=np.abs(ytc)>1e-12)

    im,out=final_from_ycc(mapped_t,cb,cr,dst)
    outputs["TCYC_ABS"]=im
    stats["TCYC_ABS"]=stage_stats(np.ones_like(ytc),out)

    # Firmware TONE says RGB tone enabled. Apply one TCYC-derived shared gain to RGB,
    # then execute the recovered final YC conversion.
    wt=w*ratio_t[...,None]
    yt=np.tensordot(wt,YC,axes=([-1],[0]))
    cbt=np.tensordot(wt,CB,axes=([-1],[0]))
    crt=np.tensordot(wt,CR,axes=([-1],[0]))
    im,out=final_from_ycc(yt,cbt,crt,dst)
    outputs["TCYC_RGB"]=im
    stats["TCYC_RGB"]=stage_stats(ratio_t,out)

    # Polarity hypothesis from source naming + Leica (0,32): full untone-mapped Yb
    # replaces the final Y carrier while Cb/Cr come from tone-processed RGB.
    # This is intentionally a discriminator; it is NOT promoted as the ASIC equation.
    yb=np.tensordot(w,CCYC,axes=([-1],[0]))
    im,out=final_from_ycc(yb,cbt,crt,dst)
    outputs["TCYC_RGB_YB32"]=im
    stats["TCYC_RGB_YB32"]=stage_stats(ratio_t,out)
    stats["TCYC_RGB_YB32"]["yb_minus_tonedY_mean"]=float(np.mean(yb-yt))
    stats["TCYC_RGB_YB32"]["yb_minus_tonedY_p95_abs"]=float(np.quantile(np.abs(yb-yt),.95))

    return outputs,stats

def stage_stats(scale,out):
    finite=np.isfinite(scale)
    s=scale[finite]
    return {
      "mean_scale":float(np.mean(s)) if s.size else None,
      "p50_scale":float(np.median(s)) if s.size else None,
      "p90_scale":float(np.quantile(s,.9)) if s.size else None,
      "post_cc1_high_R_fraction":float(np.mean(out[...,0]>1)),
      "post_cc1_high_G_fraction":float(np.mean(out[...,1]>1)),
      "post_cc1_high_B_fraction":float(np.mean(out[...,2]>1)),
      "post_cc1_low_R_fraction":float(np.mean(out[...,0]<0)),
      "post_cc1_low_G_fraction":float(np.mean(out[...,1]<0)),
      "post_cc1_low_B_fraction":float(np.mean(out[...,2]<0)),
    }

def load_scene(sid,inputs,A,D,PCS,BR,D50):
    if int(sid)<=6:
        meta=json.loads((inputs/"samples"/f"{sid}_metadata.json").read_text())
        raw=np.load(inputs/"samples"/f"{sid}_raw.npz")["raw"]
        jpg=inputs/"samples"/f"{sid}.jpg"
    else:
        meta,raw,jpg=fresh(sid,inputs)
    j,d=meta["metadata"]
    keys=["Model","SerialNumber","ImageUniqueID","DateTimeOriginal","ISO","ExposureTime","FNumber","FocalLength"]
    assert all(j.get(k)==d.get(k) and j.get(k) is not None for k in keys),(sid,j,d)
    assert all(j.get(k)==0 for k in ("Contrast","Saturation","Sharpness"))
    assert j["ColorSpace"]==1
    assert meta["raw_pattern"]==[[3,2],[0,1]]
    assert all(v==0 for v in meta["black_level_per_channel"])
    assert meta["white_level"]==15000
    assert np.max(np.abs(ref1e.nums(d["ColorMatrix1"]).reshape(3,3)-A))<1e-7
    assert np.max(np.abs(ref1e.nums(d["ColorMatrix2"]).reshape(3,3)-D))<1e-7

    asn=ref1e.nums(d["AsShotNeutral"])
    ca9=np.clip(np.rint(256/asn),1,2000).astype(np.float64)
    kelvin=float(d["CorrelatedColorTemp"])
    xy=ref1e.nums(d["WhitePoint"])
    white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
    f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1)
    cm=f*A+(1-f)*D
    adaptation=np.linalg.inv(BR)@np.diag((BR@D50)/(BR@white))@BR
    work=PCS@adaptation@np.linalg.inv(cm)
    whiteY=float((np.linalg.inv(cm)@asn)[1])

    ref=np.asarray(Image.open(jpg).convert("RGB"))
    H,W=sorted(ref.shape[:2])
    rh,rw=raw.shape
    top,left=(rh-H)//2,(rw-W)//2
    assert min(top,left)>=0
    lut=np.floor(np.clip(np.arange(65536)/15000.0,0,1)*65535+0.5).astype(np.uint16)
    norm=lut[raw];del raw
    sample=np.empty(((H+STEP-1)//STEP,(W+STEP-1)//STEP,3),dtype=np.uint16)
    for y0 in range(0,rh,256):
        y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4)
        tile=cv2.cvtColor(norm[hs:he],cv2.COLOR_BayerGB2BGR_EA)
        ys=np.arange(max(y0,top),min(y1,top+H))
        ys=ys[(ys-top)%STEP==0]
        if len(ys):
            sample[(ys-top)//STEP]=tile[ys-hs,left:left+W:STEP]
    del norm
    return sample,ref[::STEP,::STEP],ca9,work,whiteY,{
      "ISO":j["ISO"],"kelvin":kelvin,
      "jpg_sha256":meta["jpg_sha256"],"dng_sha256":meta["dng_sha256"],
    }

def aggregate(scenes,ids,condition):
    out={}
    keys=("L_mae","ab_error","DE76","chroma_ratio_ref_ge20",
          "hue_abs_error_deg_ref_ge20","warm_ab_error",
          "warm_chroma_ratio","warm_hue_abs_error_deg")
    for m in MODELS:
        rows=[s["conditions"][condition]["models"][m] for s in scenes if s["id"] in ids]
        out[m]={k:float(np.mean([x[k] for x in rows if x[k] is not None])) for k in keys}
        out[m]["post_cc1_high_R_fraction"]=float(np.mean([
            s["conditions"][condition]["stage_stats"][m]["post_cc1_high_R_fraction"]
            for s in scenes if s["id"] in ids]))
    return out

def main():
    if not __debug__: raise RuntimeError("assertions required")
    inputs=Path(sys.argv[1]).resolve()
    out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=True)
    for e in json.loads((inputs/"manifest.json").read_text()):
        p=inputs/e["path"]
        assert p.stat().st_size==e["bytes"] and sha(p)==e["sha256"]
    js=(inputs/"source/M10RNativeRenderer.java").read_text()
    A=ref1e.constant(js,"M10_CM_A").reshape(3,3)
    D=ref1e.constant(js,"M10_CM_D65").reshape(3,3)
    PCS=ref1e.constant(js,"PCS_TO_INTERNAL").reshape(3,3)
    dst=ref1e.constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    BR=ref1e.constant(js,"BRADFORD").reshape(3,3)
    d50xy=ref1e.constant(js,"D50_XY")
    D50=np.array([d50xy[0]/d50xy[1],1,(1-d50xy.sum())/d50xy[1]])
    tone=np.fromfile(inputs/"assets/tone_medium_q15.u32le",dtype="<u4")
    dg=np.fromfile(inputs/"assets/dg_expanded_u16le.bin",dtype="<u2")
    assert len(tone)==10240 and len(dg)==32768

    result={
      "schema":"M10R_YBLEND_TCYC_YB1A_V1",
      "status":"RUNNING",
      "models":list(MODELS),
      "primary_holdout":["07","08","09","10"],
      "development_context":["01","02","03","04","05","06"],
      "fit_freedom":"NONE; TCYC/CCYC/final-YC coefficients and Leica control states fixed before scoring",
      "firmware_facts":{
        "TCYC_Q12_storage":[1024,2661,410],
        "CCYC_Q8_storage":[77,150,29],
        "final_YC_Q12_storage":[1224,2403,469],
        "tone_rgb_enabled":1,
        "tone_yb_enabled":0,
        "tone_ytc_select":0,
        "yblend_controls":[0,32],
      },
      "interpretation_boundary":[
        "TCYC denominator 4096 is a Q12 candidate consistent with field width, not recovered pixel arithmetic.",
        "TCYC_RGB_YB32 assumes source-name polarity (YBBLND full Yb) only as a falsifiable discriminator.",
        "No Android renderer or APK is changed."
      ],
      "scenes":[]
    }

    for sid in [f"{i:02d}" for i in range(1,11)]:
        print("BEGIN",sid,flush=True)
        sample,ref,ca9,work,whiteY,meta=load_scene(sid,inputs,A,D,PCS,BR,D50)
        scene={"id":sid,"metadata":meta,"conditions":{}}
        for cond,scale in (("target_native",1.0),("white_normalized",1.0/whiteY)):
            src=np.eye(3)*scale
            imgs,stats=render_models(sample,src,ca9,work,dst,tone,dg)
            al=ref1e.solve_alignment(imgs["CURRENT_k035"],ref)
            assert al["corr"]>.75,(sid,cond,al)
            models={}
            for name in MODELS:
                aa,bb=ref1e.apply_alignment(imgs[name],ref,al)
                la,lb,n=ref1e.patch_values(aa,bb)
                m=ref1e.metrics(la,lb);m["patches"]=n
                models[name]=m
                if cond=="target_native" and sid in ("07","08","09","10"):
                    Image.fromarray(aa).save(out/f"{sid}_{name}.jpg",quality=92)
            scene["conditions"][cond]={"alignment":al,"models":models,"stage_stats":stats}
            print(sid,cond," ".join(
              f"{m}:DE={models[m]['DE76']:.3f},ab={models[m]['ab_error']:.3f},L={models[m]['L_mae']:.3f}"
              for m in MODELS),flush=True)
        result["scenes"].append(scene)
        (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")

    result["aggregates"]={
      "holdout_07_10":{
        c:aggregate(result["scenes"],["07","08","09","10"],c)
        for c in ("target_native","white_normalized")
      },
      "development_01_06":{
        c:aggregate(result["scenes"],["01","02","03","04","05","06"],c)
        for c in ("target_native","white_normalized")
      },
      "all_01_10":{
        c:aggregate(result["scenes"],[f"{i:02d}" for i in range(1,11)],c)
        for c in ("target_native","white_normalized")
      }
    }
    hold=result["aggregates"]["holdout_07_10"]["target_native"]
    result["holdout_ranking_DE76"]=sorted(MODELS,key=lambda m:hold[m]["DE76"])
    result["holdout_ranking_ab"]=sorted(MODELS,key=lambda m:hold[m]["ab_error"])
    result["status"]="PASS_TCYC_YB_DISCRIMINATOR"
    result["script_sha256"]=sha(__file__)
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")

    lines=[
      "# M10-R YBLEND TCYC/YB1A","",
      "Source-backed two-luminance offline discriminator. No APK and no parameter fitting.","",
      "## Primary holdout 07-10 / target-native","",
      "| Model | L* MAE | a*b* error | DE76 | Chroma ratio | Warm a*b* | Warm chroma | High-R frac |",
      "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in MODELS:
        q=hold[m]
        lines.append(f"| {m} | {q['L_mae']:.3f} | {q['ab_error']:.3f} | {q['DE76']:.3f} | {q['chroma_ratio_ref_ge20']:.3f} | {q['warm_ab_error']:.3f} | {q['warm_chroma_ratio']:.3f} | {q['post_cc1_high_R_fraction']:.5f} |")
    lines += [
      "",
      "DE76 ranking: "+", ".join(result["holdout_ranking_DE76"]),
      "a*b* ranking: "+", ".join(result["holdout_ranking_ab"]),
      "",
      "Interpretation: a winning topology is evidence for further reconstruction only. It does not prove the Leica ASIC equation or authorize Android promotion.",
      ""
    ]
    (out/"REPORT.md").write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
