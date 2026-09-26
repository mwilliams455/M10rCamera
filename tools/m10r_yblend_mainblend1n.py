#!/usr/bin/env python3
"""MAINBLEND1N: sweep only final main-line Y blend on frozen TOPO_RGBDG_YBDG."""
from pathlib import Path
import json,sys,subprocess
import numpy as np
import cv2
from PIL import Image
import m10r_yblend_topology1k as t

ALPHAS={"YB_A0":0.0,"A025":0.25,"A050":0.50,"A075":0.75,"YA_A1":1.0}
MODELS=["CURRENT_K035"]+list(ALPHAS)

def metrics(a,b):
    m=t.metrics(a,b)
    m["L_bias"]=float(np.mean(a[:,0]-b[:,0]))
    return m

def render_alpha(sample,src,ca9,work,dst,tone,dg,alpha):
    tr=t.xform(sample.astype(float)/65535.,src)
    tr=np.clip(tr*ca9/256.,0,1)*256./ca9
    w=t.xform(tr,work)

    ytc=w@t.TCYC
    tx=np.floor(np.clip(ytc,0,1)*t.INPUT_MAX+.5).astype(np.int64)
    my=t.medium_coord(tx,tone);tone_y=my/float(t.INPUT_MAX)
    tg=np.divide(tone_y,ytc,out=np.zeros_like(ytc),where=ytc>1e-12)
    wrgb=w*tg[...,None]
    rgb_nl=np.stack([t.dg_of(wrgb[...,i],dg) for i in range(3)],-1)

    yb_pre=w@t.CCYC
    yb=t.dg_of(yb_pre,dg)
    ya_cb_cr=t.xform(rgb_nl,t.YCM)
    ya=ya_cb_cr[...,0]
    fy=alpha*ya+(1.0-alpha)*yb
    yc=np.stack([fy,ya_cb_cr[...,1],ya_cb_cr[...,2]],-1)
    n=t.xform(yc,t.YCI);out=t.xform(n,dst)
    q=np.floor(np.clip(out,0,1)*255+.5).astype(np.uint8)
    return q,{
      "alpha_Ya":float(alpha),"alpha_Yb":float(1-alpha),
      "mean_Ya":float(np.mean(ya)),"mean_Yb":float(np.mean(yb)),
      "mean_finalY":float(np.mean(fy)),
      "mean_Yb_minus_Ya":float(np.mean(yb-ya)),
      "post_cc1_high_R_fraction":float(np.mean(out[...,0]>1)),
      "post_cc1_high_G_fraction":float(np.mean(out[...,1]>1)),
      "post_cc1_high_B_fraction":float(np.mean(out[...,2]>1)),
    }

def main():
    inp,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
    for e in json.loads((inp/"manifest.json").read_text()):
        p=inp/e["path"];assert p.stat().st_size==e["bytes"] and t.sha(p)==e["sha256"]
    js=(inp/"source/M10RNativeRenderer.java").read_text()
    A=t.constant(js,"M10_CM_A").reshape(3,3);D=t.constant(js,"M10_CM_D65").reshape(3,3)
    pcs=t.constant(js,"PCS_TO_INTERNAL").reshape(3,3);dst=t.constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    br=t.constant(js,"BRADFORD").reshape(3,3);xy=t.constant(js,"D50_XY");d50=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
    tone=np.fromfile(inp/"assets/tone_medium_q15.u32le",dtype="<u4");dg=np.fromfile(inp/"assets/dg_expanded_u16le.bin",dtype="<u2")
    result={"schema":"M10R_YBLEND_MAINBLEND1N_V1","status":"RUNNING","models":MODELS,
      "only_variable":"final_mainline_Y = alpha*Ya + (1-alpha)*Yb",
      "fixed_path":"TCYC tone gain -> common DG per RGB channel -> YC gives Ya/Cb/Cr; CCYC Yb -> DG; Cb/Cr frozen",
      "alphas":ALPHAS,
      "splits":{"reused_development":["01","03","05"],"reused_validation":["02","04","06"],"fresh_holdout":["07","08","09","10"]},
      "scenes":{}}
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
            ba,bb=t.apply_alignment(base,ref,al);la,lb,npats=t.patch_values(ba,bb)
            m=metrics(la,lb);m["patches"]=npats;rows["CURRENT_K035"]=m
            print(sid,cond,"CURRENT_K035","DE",round(m["DE76"],4),"L",round(m["L_mae"],4),"Lb",round(m["L_bias"],4),flush=True)
            for name,a in ALPHAS.items():
                im,st=render_alpha(sample,src,ca9,work,dst,tone,dg,a)
                aa,rr=t.apply_alignment(im,ref,al);pa,pr,npats=t.patch_values(aa,rr)
                m=metrics(pa,pr);m["patches"]=npats;m["stage_stats"]=st;rows[name]=m
                print(sid,cond,name,"DE",round(m["DE76"],4),"ab",round(m["ab_error"],4),"L",round(m["L_mae"],4),"Lb",round(m["L_bias"],4),flush=True)
                if cond=="target_native" and sid in ("02","04","06","07","08","09","10"):
                    Image.fromarray(aa).save(out/f"{sid}_{name}.jpg",quality=92)
            scene["conditions"][cond]={"alignment":al,"models":rows}
        result["scenes"][sid]=scene;(out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    ag={}
    for split,ids in result["splits"].items():
        ag[split]={}
        for cond in ("target_native","white_normalized_control"):
            ag[split][cond]={}
            for name in MODELS:
                rr=[result["scenes"][sid]["conditions"][cond]["models"][name] for sid in ids]
                keys=["L_mae","L_bias","ab_error","DE76","chroma_ratio_ref_ge20","hue_abs_error_deg_ref_ge20","warm_ab_error","warm_chroma_ratio","warm_hue_abs_error_deg"]
                ag[split][cond][name]={k:float(np.mean([x[k] for x in rr if x.get(k)is not None])) for k in keys}
    result["aggregates"]=ag;result["status"]="PASS_MAINBLEND1N_EXECUTION";result["script_sha256"]=t.sha(__file__)
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# M10-R MAINBLEND1N","",
      "Only final main-line Y blend changes; RGB/chroma topology is frozen.","",
      "## Fresh holdout 07–10, target-native","",
      "| Model | alpha Ya | L* MAE | L* bias | a*b* | DE76 | chroma ratio | warm a*b* |",
      "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in MODELS:
        m=ag["fresh_holdout"]["target_native"][name];alpha=ALPHAS.get(name,None)
        lines.append(f"| {name} | {'' if alpha is None else f'{alpha:.2f}'} | {m['L_mae']:.3f} | {m['L_bias']:.3f} | {m['ab_error']:.3f} | {m['DE76']:.3f} | {m['chroma_ratio_ref_ge20']:.3f} | {m['warm_ab_error']:.3f} |")
    lines+=["","No alpha is promoted from this sweep; it is a polarity/placement discriminator. Fresh 07–10 were not used to choose the values.",""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print(json.dumps(ag["fresh_holdout"]["target_native"],indent=2))
if __name__=="__main__":main()
