#!/usr/bin/env python3
"""WARMRED1A constrained public-reference screen.

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
    "red085":{"knee":0.85,"min_y":0.0,"min_relcr":-1e9},
    "red090":{"knee":0.90,"min_y":0.0,"min_relcr":-1e9},
    "red095":{"knee":0.95,"min_y":0.0,"min_relcr":-1e9},
    "warm060_red090":{"knee":0.90,"min_y":0.60,"min_relcr":0.04},
    "warm065_red090":{"knee":0.90,"min_y":0.65,"min_relcr":0.04},
    "warm070_red090":{"knee":0.90,"min_y":0.70,"min_relcr":0.04},
    "warm065_red095":{"knee":0.95,"min_y":0.65,"min_relcr":0.04},
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

def warm_candidate(taps,dst,post,spec):
    # RENDER1T colour direction: CC1 applied to pre-tone working RGB.
    lin=a.xform(taps[:,:3],dst)
    baseline=g.oracle(taps[:,6:9])
    anchor=c.decode(baseline)@W
    lum=np.maximum(lin@W,1e-12)
    requested=anchor/lum
    rgb=lin*requested[:,None]

    # Exact neutral invariant is inherited from RENDER1T's original input.
    neutral=(taps[:,0]==taps[:,1])&(taps[:,1]==taps[:,2])

    # Derive mapped Yc from the reconstructed post-Yc RGB only for candidate
    # classification. No mapped-Y or chroma value is changed by classification.
    mapped=taps[:,3:6]@YC.T
    my=mapped[:,0]
    relcr=np.where(np.abs(my)>1e-12,mapped[:,2]/my,0.0)

    red=rgb[:,0]
    red_peak=(red>=rgb[:,1])&(red>=rgb[:,2])
    active=red_peak&(my>=spec["min_y"])&(relcr>=spec["min_relcr"])&(~neutral)

    red_code=c.encode(np.maximum(red,0.0))
    knee=spec["knee"];width=1.0-knee
    above=np.maximum(red_code-knee,0.0)
    soft=np.where(red_code>knee,
                  knee+width*above/np.maximum(above+width,1e-12),
                  red_code)
    target_r=c.decode(soft)

    # Opponent ray around exact linear luminance anchor. Since W dot
    # (rgb-anchor) == 0, scaling this vector preserves anchor exactly.
    dr=red-anchor
    scale=np.ones(len(rgb),dtype=np.float64)
    good=active&(red_code>knee)&(dr>1e-12)
    scale[good]=np.clip((target_r[good]-anchor[good])/dr[good],0.0,1.0)
    out=anchor[:,None]+scale[:,None]*(rgb-anchor[:,None])

    coded=c.encode(out)
    mapped_out=g.oracle(coded)
    mapped_out[neutral]=baseline[neutral]
    q=np.floor(np.clip(mapped_out,0,1)*255+.5).astype(np.uint8)
    q=post(q)
    stats={
        "active_pixels":int(good.sum()),
        "active_fraction":float(good.mean()),
        "mean_scale_active":float(scale[good].mean()) if good.any() else 1.0,
        "min_scale":float(scale.min()),
        "linear_luma_error_max":float(np.max(np.abs(out@W-anchor))),
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
      "schema":"M10R_WARMRED1A_SCREEN_V1",
      "source_commit":os.getenv("GITHUB_SHA"),
      "candidate_specs":CANDIDATES,
      "private_inputs_used":False,
      "reference_pair_count":10,
      "baseline":"RENDER1T_COLORRECON1A",
      "candidate_intent":"preserve_RENDER1T_colour_direction_and_linear_lightness_anchor; replace_broad_saturation_shoulder_with_red_peak_opponent_compression",
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
                flat,st=warm_candidate(taps,dst,post,spec)
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
            ok &= z["max_linear_luma_error"]<=1e-10
        if ok: passing.append(name)
    result["summary"]=summary
    result["passing_candidates"]=passing
    if passing:
        # Rank only among candidates that meet all predeclared non-regression gates.
        result["preferred_candidate"]=min(
            passing,
            key=lambda n: summary["target_native"]["candidates"][n]["mean_DE76"]
        )
        result["status"]="PASS_WARMRED1A_SCREEN"
    else:
        result["preferred_candidate"]=None
        result["status"]="NO_WARMRED1A_CANDIDATE_PASSES"

    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# M10-R WARMRED1A SCREEN","",
           "Public-reference screen only; no private household RAWs used.","",
           f"Status: **{result['status']}**",
           f"Preferred candidate: **{result['preferred_candidate']}**",""]
    for mode in summary:
        lines += [f"## {mode}","",f"RENDER1T: {summary[mode]['render1t']}",""]
        for n,z in summary[mode]["candidates"].items():
            lines.append(f"- {n}: {z}")
        lines.append("")
    lines += ["## Interpretation boundary","",
              "Passing this screen would only establish public-reference non-regression for a bounded empirical warm/red-highlight treatment. It would not prove Leica firmware arithmetic or private-scene correctness.",
              "No APK should be built unless at least one candidate passes this screen.",
              ""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
