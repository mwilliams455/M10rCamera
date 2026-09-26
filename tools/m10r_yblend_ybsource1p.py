#!/usr/bin/env python3
"""YBSOURCE1P: isolate Yb tap placement.

Frozen main RGB path:
  post-WB RGB -> CC0 working RGB -> TCYC-driven MEDIUM tone gain ->
  common DG per RGB channel -> final YC => Ya/Cb/Cr.

Only Yb source changes:
  POSTCC0_YB: CCYC dot post-CC0 working RGB (TOPOLOGY1K assumption)
  PRECC0_YB:  CCYC dot pre-CC0 post-WB RGB (patent/related-R2Y architecture)

Both use the same DG curve for Yb and final Y=Yb (same provisional
YYBLND interpretation). YA_A1 is retained as a no-Yb control.
"""
from pathlib import Path
import json,sys
import numpy as np
import cv2
from PIL import Image
import m10r_yblend_topology1k as t

MODELS=["CURRENT_K035","POSTCC0_YB","PRECC0_YB","YA_A1"]

def metric(a,b):
    m=t.metrics(a,b)
    m["L_bias"]=float(np.mean(a[:,0]-b[:,0]))
    return m

def common_path(sample,src,ca9,work,tone,dg):
    tr=t.xform(sample.astype(float)/65535.,src)
    # Preserve the exact PHOTOAUDIT/TOPOLOGY1K WB-domain arithmetic.
    tr=np.clip(tr*ca9/256.,0,1)*256./ca9
    w=t.xform(tr,work)
    ytc=w@t.TCYC
    tx=np.floor(np.clip(ytc,0,1)*t.INPUT_MAX+.5).astype(np.int64)
    my=t.medium_coord(tx,tone)
    tone_y=my/float(t.INPUT_MAX)
    tg=np.divide(tone_y,ytc,out=np.zeros_like(ytc),where=ytc>1e-12)
    wrgb=w*tg[...,None]
    rgb_nl=np.stack([t.dg_of(wrgb[...,i],dg) for i in range(3)],-1)
    yc=t.xform(rgb_nl,t.YCM)
    return tr,w,yc,tg

def render_candidate(sample,src,ca9,work,dst,tone,dg,mode):
    tr,w,yc,tg=common_path(sample,src,ca9,work,tone,dg)
    ya=yc[...,0]
    if mode=="YA_A1":
        fy=ya
        yb_pre=None
    elif mode=="POSTCC0_YB":
        yb_pre=w@t.CCYC
        fy=t.dg_of(yb_pre,dg)
    elif mode=="PRECC0_YB":
        yb_pre=tr@t.CCYC
        fy=t.dg_of(yb_pre,dg)
    else:
        raise KeyError(mode)
    outyc=np.stack([fy,yc[...,1],yc[...,2]],-1)
    n=t.xform(outyc,t.YCI)
    out=t.xform(n,dst)
    q=np.floor(np.clip(out,0,1)*255+.5).astype(np.uint8)
    st={
      "ybSource":mode,
      "mean_Ya":float(np.mean(ya)),
      "mean_finalY":float(np.mean(fy)),
      "mean_finalY_minus_Ya":float(np.mean(fy-ya)),
      "mean_abs_finalY_minus_Ya":float(np.mean(np.abs(fy-ya))),
      "mean_tone_gain":float(np.mean(tg[np.isfinite(tg)])),
      "post_cc1_high_R_fraction":float(np.mean(out[...,0]>1)),
      "post_cc1_high_G_fraction":float(np.mean(out[...,1]>1)),
      "post_cc1_high_B_fraction":float(np.mean(out[...,2]>1)),
    }
    if yb_pre is not None:
        st["mean_Yb_preDG"]=float(np.mean(yb_pre))
        st["mean_Yb_postDG"]=float(np.mean(fy))
    return q,st

def main():
    inp,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
    for e in json.loads((inp/"manifest.json").read_text()):
        p=inp/e["path"];assert p.stat().st_size==e["bytes"] and t.sha(p)==e["sha256"]
    js=(inp/"source/M10RNativeRenderer.java").read_text()
    A=t.constant(js,"M10_CM_A").reshape(3,3);D=t.constant(js,"M10_CM_D65").reshape(3,3)
    pcs=t.constant(js,"PCS_TO_INTERNAL").reshape(3,3);dst=t.constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    br=t.constant(js,"BRADFORD").reshape(3,3);xy=t.constant(js,"D50_XY")
    d50=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
    tone=np.fromfile(inp/"assets/tone_medium_q15.u32le",dtype="<u4")
    dg=np.fromfile(inp/"assets/dg_expanded_u16le.bin",dtype="<u2")
    assert len(tone)==10240 and len(dg)==32768
    res={
      "schema":"M10R_YBLEND_YBSOURCE1P_V1","status":"RUNNING","models":MODELS,
      "only_variable":"Yb source tap: pre-CC0 post-WB RGB vs post-CC0 working RGB",
      "fixed":{
        "rgbPath":"CC0 -> TCYC MEDIUM gain -> common DG per RGB -> YC",
        "YbTone":"disabled",
        "YbDG":"same recovered DG curve in both Yb candidates",
        "finalY":"Yb for POSTCC0/PRECC0 candidates",
        "CbCr":"from nonlinear RGB YC and unchanged by Yb",
      },
      "evidenceBoundary":{
        "sourceBacked":"Fujitsu architecture forms Yb from RGB before color correction; related R2Y labels CCYC as coefficient of Yb convert.",
        "M10RProven":"CCYC row, TCYC row, RGB-tone enabled, Yb-tone disabled, generic five-bank DG writer.",
        "notProven":"Exact M10-R CCYC pixel tap or Yb gamma-bank contents."
      },
      "splits":{"reused_development":["01","03","05"],"reused_validation":["02","04","06"],"fresh_holdout":["07","08","09","10"]},
      "scenes":{}
    }
    for sid in [f"{i:02d}" for i in range(1,11)]:
        print("BEGIN",sid,flush=True)
        sample,ref,ca9,work,whiteY,meta=t.prep(sid,inp,js,A,D,pcs,dst,br,d50)
        scene={"metadata":meta,"whiteY":whiteY,"conditions":{}}
        for cond,factor in [("target_native",1.0),("white_normalized_control",1.0/whiteY)]:
            src=np.eye(3)*factor
            base,_=t.render_model(sample,src,ca9,work,dst,tone,dg,"CURRENT_K035")
            al=t.solve_alignment(base,ref)
            if cond=="target_native":scene["alignment"]=al
            rows={}
            ba,rr=t.apply_alignment(base,ref,al);pa,pr,n=t.patch_values(ba,rr)
            m=metric(pa,pr);m["patches"]=n;rows["CURRENT_K035"]=m
            print(sid,cond,"CURRENT_K035","DE",round(m["DE76"],4),"ab",round(m["ab_error"],4),"L",round(m["L_mae"],4),flush=True)
            for name in ("POSTCC0_YB","PRECC0_YB","YA_A1"):
                im,st=render_candidate(sample,src,ca9,work,dst,tone,dg,name)
                aa,bb=t.apply_alignment(im,ref,al);la,lb,n=t.patch_values(aa,bb)
                m=metric(la,lb);m["patches"]=n;m["stage_stats"]=st;rows[name]=m
                print(sid,cond,name,"DE",round(m["DE76"],4),"ab",round(m["ab_error"],4),"L",round(m["L_mae"],4),"Lb",round(m["L_bias"],4),flush=True)
                if cond=="target_native" and sid in ("02","04","06","07","08","09","10"):
                    Image.fromarray(aa).save(out/f"{sid}_{name}.jpg",quality=92)
            scene["conditions"][cond]={"alignment":al,"models":rows}
        res["scenes"][sid]=scene;(out/"results.json").write_text(json.dumps(res,indent=2)+"\n")
    ag={}
    for split,ids in res["splits"].items():
        ag[split]={}
        for cond in ("target_native","white_normalized_control"):
            ag[split][cond]={}
            for name in MODELS:
                rr=[res["scenes"][sid]["conditions"][cond]["models"][name] for sid in ids]
                keys=["L_mae","L_bias","ab_error","DE76","chroma_ratio_ref_ge20","hue_abs_error_deg_ref_ge20","warm_ab_error","warm_chroma_ratio","warm_hue_abs_error_deg"]
                ag[split][cond][name]={k:float(np.mean([x[k] for x in rr if x.get(k)is not None])) for k in keys}
    res["aggregates"]=ag;res["status"]="PASS_YBSOURCE1P_EXECUTION";res["script_sha256"]=t.sha(__file__)
    (out/"results.json").write_text(json.dumps(res,indent=2)+"\n")
    lines=["# M10-R YBSOURCE1P","",
      "Only the CCYC/Yb source tap changes between POSTCC0_YB and PRECC0_YB.","",
      "## Fresh holdout 07–10, target-native","",
      "| Model | L* MAE | L* bias | a*b* | DE76 | chroma ratio | warm a*b* |",
      "|---|---:|---:|---:|---:|---:|---:|"]
    for name in MODELS:
        m=ag["fresh_holdout"]["target_native"][name]
        lines.append(f"| {name} | {m['L_mae']:.3f} | {m['L_bias']:.3f} | {m['ab_error']:.3f} | {m['DE76']:.3f} | {m['chroma_ratio_ref_ge20']:.3f} | {m['warm_ab_error']:.3f} |")
    lines+=["","No candidate is promoted by this test; exact M10-R Yb tap remains a hardware question.",""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print(json.dumps(ag["fresh_holdout"]["target_native"],indent=2))
if __name__=="__main__":main()
