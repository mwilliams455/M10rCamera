#!/usr/bin/env python3
"""Native C++ validation for the screened WARMRED1B warm075_red085 candidate."""
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,statistics
import numpy as np
import cv2

import m10r_colorrecon1a_validate as c
import m10r_photoaudit_measure1a as a
import m10r_tonecal1a_validate as t
import m10r_gamut1a_validate as g

W=np.array([0.2126,0.7152,0.0722],dtype=np.float64)
YC=np.array([[1224.,2403.,469.],[-691.,-1357.,2048.],[2048.,-1715.,-333.]],dtype=np.float64)/4096.
SPEC={"knee":0.85,"min_y":0.75,"min_relcr":0.04}

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def python_oracle(taps,dst,post,render1t_final):
    q=render1t_final.reshape(-1,3).copy()
    lin=a.xform(taps[:,:3],dst)
    baseline=g.oracle(taps[:,6:9])
    anchor=c.decode(baseline)@W
    lum=lin@W
    mapped=taps[:,3:6]@YC.T
    my=mapped[:,0]
    relcr=np.divide(mapped[:,2],my,out=np.zeros_like(my),where=np.abs(my)>1e-12)
    neutral=(taps[:,0]==taps[:,1])&(taps[:,1]==taps[:,2])
    finite=np.isfinite(lin).all(1)&np.isfinite(anchor)&np.isfinite(lum)&np.isfinite(my)&np.isfinite(relcr)
    selector=finite&(lum>1e-6)&(lin[:,0]>=lin[:,1])&(lin[:,0]>=lin[:,2])&(my>=.75)&(relcr>=.04)&(~neutral)
    idx=np.flatnonzero(selector)
    active=np.empty(0,dtype=np.int64); scales=np.empty(0)
    lerr=0.
    if len(idx):
        req=anchor[idx]/lum[idx]
        rgb=lin[idx]*req[:,None]
        red=rgb[:,0]; redcode=c.encode(np.maximum(red,0.))
        above=np.maximum(redcode-.85,0.)
        soft=np.where(redcode>.85,.85+.15*above/np.maximum(above+.15,1e-12),redcode)
        target=c.decode(soft);dr=red-anchor[idx]
        use=(redcode>.85)&(dr>1e-9)&np.isfinite(rgb).all(1)&np.isfinite(target)
        if np.any(use):
            active=idx[use]; aa=anchor[active]; rgb=rgb[use];dr=dr[use];target=target[use]
            scales=np.clip((target-aa)/dr,0,1)
            out=aa[:,None]+scales[:,None]*(rgb-aa[:,None])
            lerr=float(np.max(np.abs(out@W-aa)))
            coded=c.encode(out);mappedout=g.oracle(coded)
            qq=np.floor(np.clip(mappedout,0,1)*255+.5).astype(np.uint8)
            q[active]=post(qq)
    return q,{"active":int(len(active)),"luma_error":lerr,
              "mean_scale":float(scales.mean()) if len(scales) else 1.0}

def construct(repo,inp):
    q=(inp/"source/m10rRender.cpp").read_text()
    r=loadmod("rp",repo/"patches/fix-m10r-render1r-tonecal1a.py").patch_cpp(q)
    s=loadmod("sp",repo/"patches/fix-m10r-render1s-gamut1a.py").patch_cpp(r)
    tcpp=loadmod("tp",repo/"patches/fix-m10r-render1t-colorrecon1a.py").patch_cpp(s)
    warm=tcpp
    a1='#include "m10rColorRecon1A.h"'
    assert warm.count(a1)==1
    warm=warm.replace(a1,a1+'\n#include "m10rWarmRed1B.h"',1)
    old='''            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB);
'''
    new=old+'''            m10r_warmred1b::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    mappedY,mappedCr,outR,outG,outB,nullptr);
'''
    assert warm.count(old)==1
    warm=warm.replace(old,new,1)
    return r,tcpp,warm

def metric_groups(im,ref,al):
    v,rf=t.view(im,ref,al)
    cp,rp,ps=a.patch_values(v,rf)
    return a.groups(cp,rp),ps

def main():
    if not __debug__: raise RuntimeError("Assertions required")
    ap=argparse.ArgumentParser();ap.add_argument("inputs",type=Path);ap.add_argument("out",type=Path)
    x=ap.parse_args();inp=x.inputs.resolve();out=x.out.resolve();out.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[1];cv2.setNumThreads(1)
    r,tcpp,warm=construct(repo,inp)
    R=c.compile_native(repo,out,r,"host_r",True)
    T=c.compile_native(repo,out,tcpp,"host_t")
    WARM=c.compile_native(repo,out,warm,"host_warm")
    _,post=g.host_header(repo,out)
    js=(inp/"source/M10RNativeRenderer.java").read_text()
    dst=a.constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    tone=np.fromfile(inp/"assets/tone_medium_q15.u32le",dtype="<u4").astype(np.int32)
    dg=np.fromfile(inp/"assets/dg_expanded_u16le.bin",dtype="<u2").astype(np.int32)
    eye=np.eye(3,dtype=np.float64)

    result={"schema":"M10R_WARMRED1B_NATIVE_VALIDATE_V1","source_commit":os.getenv("GITHUB_SHA"),
      "candidate":"warm075_red085","private_inputs_used":False,
      "warm_cpp_sha256":hashlib.sha256(warm.encode()).hexdigest(),
      "helper_sha256":hashlib.sha256((repo/"native/m10rWarmRed1B.h").read_bytes()).hexdigest(),
      "cases":{},"max_oracle_code_error":0}

    for sid in [f"{i:02}" for i in range(1,11)]:
        sample,ref,ca,work,wy,meta=c.data(sid,inp,js)
        scene={"metadata":meta,"conditions":{}}
        for mode,scale in [("target_native",1.0),("white_normalized_control",1.0/wy)]:
            src=eye*scale
            rr,_,taps,_=c.native(R,sample,src,ca,work,dst,tone,dg,tap=True)
            tim,_,_,_=c.native(T,sample,src,ca,work,dst,tone,dg)
            wim,_,_,_=c.native(WARM,sample,src,ca,work,dst,tone,dg)
            exp,ost=python_oracle(taps,dst,post,tim)
            exp=exp.reshape(tim.shape)
            err=int(np.max(np.abs(wim.astype(np.int16)-exp.astype(np.int16))))
            result["max_oracle_code_error"]=max(result["max_oracle_code_error"],err)
            if err>1: raise RuntimeError(f"{sid} {mode} native/oracle max code error {err}")
            if mode=="target_native":
                al=t.align(rr,ref);scene["alignment"]=al
            tg,ps=metric_groups(tim,ref,al);wg,ps2=metric_groups(wim,ref,al)
            assert ps2==ps
            scene["conditions"][mode]={"render1t":tg,"warmred1b":wg,"oracle":ost,
                                       "native_oracle_max_code_error":err,"patches":ps}
            print(sid,mode,"DE",tg["all"]["DE76_mean"],"->",wg["all"]["DE76_mean"],
                  "active",ost["active"],"err",err,flush=True)
        result["cases"][sid]=scene
        (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")

    summary={}
    for mode in ["target_native","white_normalized_control"]:
        base={k:statistics.mean(result["cases"][sid]["conditions"][mode]["render1t"]["all"][k] for sid in result["cases"])
              for k in ("DE76_mean","L_mae","ab_error_mean")}
        cand={k:statistics.mean(result["cases"][sid]["conditions"][mode]["warmred1b"]["all"][k] for sid in result["cases"])
              for k in ("DE76_mean","L_mae","ab_error_mean")}
        wins=sum(result["cases"][sid]["conditions"][mode]["warmred1b"]["all"]["DE76_mean"] <=
                 result["cases"][sid]["conditions"][mode]["render1t"]["all"]["DE76_mean"]
                 for sid in result["cases"])
        active=statistics.mean(result["cases"][sid]["conditions"][mode]["oracle"]["active"]/
              np.prod(c.data(sid,inp,js)[0].shape[:2]) for sid in result["cases"])
        summary[mode]={"render1t":base,"warmred1b":cand,
          "DE_ratio":cand["DE76_mean"]/base["DE76_mean"],
          "ab_ratio":cand["ab_error_mean"]/base["ab_error_mean"],
          "L_delta":cand["L_mae"]-base["L_mae"],"DE_wins_or_ties":wins,
          "mean_active_fraction":active}
    result["summary"]=summary
    result["gate_passed"]=all(
      z["DE_ratio"]<=1.05 and z["ab_ratio"]<=1.05 and z["L_delta"]<=0.10 and
      z["DE_wins_or_ties"]>=4 and z["mean_active_fraction"]>=0.0005
      for z in summary.values()) and result["max_oracle_code_error"]<=1
    result["status"]="PASS_WARMRED1B_NATIVE" if result["gate_passed"] else "FAIL_WARMRED1B_NATIVE"
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# M10-R WARMRED1B NATIVE VALIDATION","",f"Status: **{result['status']}**",
           f"Native/Python max code error: **{result['max_oracle_code_error']}**",""]
    for mode,z in summary.items():
        lines += [f"## {mode}","",f"- RENDER1T: {z['render1t']}",f"- WARMRED1B: {z['warmred1b']}",
                  f"- DE ratio: {z['DE_ratio']}",f"- ab ratio: {z['ab_ratio']}",
                  f"- L delta: {z['L_delta']}",f"- wins/ties: {z['DE_wins_or_ties']}/10",
                  f"- mean active fraction: {z['mean_active_fraction']}",""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print("\n".join(lines))
    if not result["gate_passed"]: raise SystemExit(2)

if __name__=="__main__":
    main()
