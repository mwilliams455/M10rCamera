#!/usr/bin/env python3
"""WARMRED1B constrained public-reference screen.

Purpose:
- keep RENDER1T pre-tone colour direction and its S-derived lightness anchor;
- replace the broad saturation-dependent common-gain shoulder with a
  luminance-preserving red-peak opponent compression;
- screen a small fixed candidate set on the same ten public Leica pairs.

This is empirical engineering research, not recovered Leica firmware arithmetic.
"""
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,importlib.util,json,statistics,subprocess,shutil,os
import numpy as np
import cv2
from PIL import Image

import m10r_colorrecon1a_validate as c
import m10r_photoaudit_measure1a as a
import m10r_tonecal1a_validate as t
import m10r_gamut1a_validate as g

CANDIDATES={
    "warm060_red085":{"knee":0.85,"min_y":0.60,"min_relcr":0.04},
    "warm065_red085":{"knee":0.85,"min_y":0.65,"min_relcr":0.04},
    "warm070_red085":{"knee":0.85,"min_y":0.70,"min_relcr":0.04},
    "warm075_red085":{"knee":0.85,"min_y":0.75,"min_relcr":0.04},
    "warm065_red090":{"knee":0.90,"min_y":0.65,"min_relcr":0.04},
    "warm070_red090":{"knee":0.90,"min_y":0.70,"min_relcr":0.04},
    "warm075_red090":{"knee":0.90,"min_y":0.75,"min_relcr":0.04},
    "warm070_red095":{"knee":0.95,"min_y":0.70,"min_relcr":0.04},
}
W=np.array([0.2126,0.7152,0.0722],dtype=np.float64)
YC=np.array([
    [1224.0,2403.0,469.0],
    [-691.0,-1357.0,2048.0],
    [2048.0,-1715.0,-333.0],
],dtype=np.float64)/4096.0

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def warm_candidate(taps,dst,post,spec,render1t_final):
    # WARMRED1B is an exact RENDER1T bypass for every non-target pixel.
    q=render1t_final.reshape(-1,3).copy()

    # RENDER1T colour direction and its existing S-derived lightness anchor.
    lin=a.xform(taps[:,:3],dst)
    baseline=g.oracle(taps[:,6:9])
    anchor=c.decode(baseline)@W
    lum=lin@W

    # Candidate classification uses mapped Yc only as a selector. The candidate
    # never changes Y itself and does not globally replace RENDER1T's shoulder.
    mapped=taps[:,3:6]@YC.T
    my=mapped[:,0]
    relcr=np.divide(mapped[:,2],my,out=np.zeros_like(my),where=np.abs(my)>1e-12)
    neutral=(taps[:,0]==taps[:,1])&(taps[:,1]==taps[:,2])
    finite=np.isfinite(lin).all(1)&np.isfinite(anchor)&np.isfinite(lum)&np.isfinite(my)&np.isfinite(relcr)
    stable=finite&(lum>1e-6)
    red_peak=(lin[:,0]>=lin[:,1])&(lin[:,0]>=lin[:,2])
    selector=stable&red_peak&(my>=spec["min_y"])&(relcr>=spec["min_relcr"])&(~neutral)

    idx=np.flatnonzero(selector)
    active_idx=np.empty(0,dtype=np.int64)
    scales=np.empty(0,dtype=np.float64)
    luma_error=0.0
    if len(idx):
        req=anchor[idx]/lum[idx]
        rgb=lin[idx]*req[:,None]
        red=rgb[:,0]
        red_code=c.encode(np.maximum(red,0.0))
        knee=spec["knee"]; width=1.0-knee
        above=np.maximum(red_code-knee,0.0)
        soft=np.where(red_code>knee,
                      knee+width*above/np.maximum(above+width,1e-12),
                      red_code)
        target_r=c.decode(soft)
        dr=red-anchor[idx]
        use=(red_code>knee)&(dr>1e-9)&np.isfinite(rgb).all(1)&np.isfinite(target_r)
        if np.any(use):
            active_idx=idx[use]
            aa=anchor[active_idx]
            rgb=rgb[use]
            dr=dr[use]
            target_r=target_r[use]
            scales=np.clip((target_r-aa)/dr,0.0,1.0)
            out=aa[:,None]+scales[:,None]*(rgb-aa[:,None])
            luma_error=float(np.max(np.abs(out@W-aa)))
            coded=c.encode(out)
            mapped_out=g.oracle(coded)
            qq=np.floor(np.clip(mapped_out,0,1)*255+.5).astype(np.uint8)
            qq=post(qq)
            q[active_idx]=qq

    active_mask=np.zeros(len(q),dtype=bool); active_mask[active_idx]=True
    assert np.array_equal(q[~active_mask],render1t_final.reshape(-1,3)[~active_mask])
    stats={
        "active_pixels":int(len(active_idx)),
        "active_fraction":float(len(active_idx)/max(1,len(q))),
        "mean_scale_active":float(scales.mean()) if len(scales) else 1.0,
        "min_scale":float(scales.min()) if len(scales) else 1.0,
        "linear_luma_error_max":luma_error,
        "non_target_exact_render1t":True,
    }
    return q,stats

def metric_groups(im,ref,al):
    v,rf=t.view(im,ref,al)
    cp,rp,ps=a.patch_values(v,rf)
    return a.groups(cp,rp),ps

def main():
    if not __debug__: raise RuntimeError("Assertions required")
    ap=argparse.ArgumentParser();ap.add_argument("inputs",type=Path);ap.add_argument("out",type=Path)
    args=ap.parse_args()
    inp=args.inputs.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[1]
    cv2.setNumThreads(1)

    q=(inp/"source/m10rRender.cpp").read_text()
    r=loadmod("rp",repo/"patches/fix-m10r-render1r-tonecal1a.py").patch_cpp(q)
    s=loadmod("sp",repo/"patches/fix-m10r-render1s-gamut1a.py").patch_cpp(r)
    tcpp=loadmod("tp",repo/"patches/fix-m10r-render1t-colorrecon1a.py").patch_cpp(s)

    R=c.compile_native(repo,out,r,"host_r",True)
    T=c.compile_native(repo,out,tcpp,"host_t")
    _,post=g.host_header(repo,out)

    js=(inp/"source/M10RNativeRenderer.java").read_text()
    dst=a.constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    tone=np.fromfile(inp/"assets/tone_medium_q15.u32le",dtype="<u4").astype(np.int32)
    dg=np.fromfile(inp/"assets/dg_expanded_u16le.bin",dtype="<u2").astype(np.int32)
    eye=np.eye(3,dtype=np.float64)

    result={
      "schema":"M10R_WARMRED1B_SCREEN_V1",
      "source_commit":os.getenv("GITHUB_SHA"),
      "candidate_specs":CANDIDATES,
      "private_inputs_used":False,
      "reference_pair_count":10,
      "baseline":"RENDER1T_COLORRECON1A",
      "candidate_intent":"exact_RENDER1T_everywhere_except_selected_warm_highlight_red_peaks; selected_pixels_use_luminance_preserving_opponent_compression",
      "cases":{}
    }

    for sid in [f"{i:02}" for i in range(1,11)]:
        sample,ref,ca,work,wy,meta=c.data(sid,inp,js)
        scene={"metadata":meta,"conditions":{}}
        for mode,srcscale in [("target_native",1.0),("white_normalized_control",1.0/wy)]:
            src=eye*srcscale
            rr,_,taps,_=c.native(R,sample,src,ca,work,dst,tone,dg,tap=True)
            tim,_,_,_=c.native(T,sample,src,ca,work,dst,tone,dg)
            if mode=="target_native":
                al=t.align(rr,ref);scene["alignment"]=al
            tg,ps=metric_groups(tim,ref,al)
            cond={"render1t":tg,"candidates":{},"activity":{},"patches":ps}
            for name,spec in CANDIDATES.items():
                flat,st=warm_candidate(taps,dst,post,spec,tim)
                im=flat.reshape(tim.shape)
                mg,ps2=metric_groups(im,ref,al)
                assert ps2==ps
                cond["candidates"][name]=mg
                cond["activity"][name]=st
            scene["conditions"][mode]=cond
            print(sid,mode,
                  "T_DE",tg["all"]["DE76_mean"],
                  "best",min((cond["candidates"][n]["all"]["DE76_mean"],n) for n in CANDIDATES),
                  flush=True)
        result["cases"][sid]=scene
        (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")

    summary={}
    for mode in ["target_native","white_normalized_control"]:
        t_de=statistics.mean(result["cases"][sid]["conditions"][mode]["render1t"]["all"]["DE76_mean"] for sid in result["cases"])
        t_l=statistics.mean(result["cases"][sid]["conditions"][mode]["render1t"]["all"]["L_mae"] for sid in result["cases"])
        t_ab=statistics.mean(result["cases"][sid]["conditions"][mode]["render1t"]["all"]["ab_error_mean"] for sid in result["cases"])
        rows={}
        for name in CANDIDATES:
            de=statistics.mean(result["cases"][sid]["conditions"][mode]["candidates"][name]["all"]["DE76_mean"] for sid in result["cases"])
            lm=statistics.mean(result["cases"][sid]["conditions"][mode]["candidates"][name]["all"]["L_mae"] for sid in result["cases"])
            ab=statistics.mean(result["cases"][sid]["conditions"][mode]["candidates"][name]["all"]["ab_error_mean"] for sid in result["cases"])
            wins=sum(result["cases"][sid]["conditions"][mode]["candidates"][name]["all"]["DE76_mean"] <= result["cases"][sid]["conditions"][mode]["render1t"]["all"]["DE76_mean"] for sid in result["cases"])
            max_luma=max(result["cases"][sid]["conditions"][mode]["activity"][name]["linear_luma_error_max"] for sid in result["cases"])
            active=statistics.mean(result["cases"][sid]["conditions"][mode]["activity"][name]["active_fraction"] for sid in result["cases"])
            rows[name]={
              "mean_DE76":de,"DE_ratio_vs_RENDER1T":de/t_de,
              "mean_L_mae":lm,"L_delta_vs_RENDER1T":lm-t_l,
              "mean_ab_error":ab,"ab_ratio_vs_RENDER1T":ab/t_ab,
              "DE_wins_or_ties_vs_RENDER1T":wins,
              "mean_active_fraction":active,
              "max_linear_luma_error":max_luma,
            }
        summary[mode]={
          "render1t":{"mean_DE76":t_de,"mean_L_mae":t_l,"mean_ab_error":t_ab},
          "candidates":rows
        }

    # Conservative screen: do not materially give back RENDER1T's public
    # colour advantage; exact lightness-preservation math must also hold.
    passing=[]
    for name in CANDIDATES:
        ok=True
        for mode in summary:
            z=summary[mode]["candidates"][name]
            ok &= z["DE_ratio_vs_RENDER1T"]<=1.05
            ok &= z["ab_ratio_vs_RENDER1T"]<=1.05
            ok &= z["L_delta_vs_RENDER1T"]<=0.10
            ok &= z["DE_wins_or_ties_vs_RENDER1T"]>=4
            ok &= z["max_linear_luma_error"]<=1e-9
            ok &= z["mean_active_fraction"]>=0.0005
        if ok: passing.append(name)
    result["summary"]=summary
    result["passing_candidates"]=passing
    if passing:
        # Rank only among candidates that meet all predeclared non-regression gates.
        result["preferred_candidate"]=min(
            passing,
            key=lambda n: summary["target_native"]["candidates"][n]["mean_DE76"]
        )
        result["status"]="PASS_WARMRED1B_SCREEN"
    else:
        result["preferred_candidate"]=None
        result["status"]="NO_WARMRED1B_CANDIDATE_PASSES"

    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# M10-R WARMRED1B SCREEN","",
           "Public-reference screen only; no private household RAWs used.","",
           f"Status: **{result['status']}**",
           f"Preferred candidate: **{result['preferred_candidate']}**",""]
    for mode in summary:
        lines += [f"## {mode}","",f"RENDER1T: {summary[mode]['render1t']}",""]
        for n,z in summary[mode]["candidates"].items():
            lines.append(f"- {n}: {z}")
        lines.append("")
    lines += ["## Interpretation boundary","",
              "Passing this screen would only establish public-reference non-regression for a bounded empirical warm/red-highlight treatment that is exact RENDER1T outside its selector. It would not prove Leica firmware arithmetic or private-scene correctness.",
              "No APK should be built unless at least one candidate passes this screen.",
              ""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
