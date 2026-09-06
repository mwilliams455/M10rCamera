#!/usr/bin/env python3
"""M10-R v0.58 empirical direct-WB headroom discriminator.

This is deliberately an empirical JPEG/DNG proxy test, not hardware arithmetic
proof.  It reuses the v2.20 public same-capture pairs and alignment logic, but
makes the observable color-sensitive:

* demosaic to linear camera-space RGB with identity WB;
* reconstruct the firmware Q8 WB triplet from DNG AsShotNeutral (gain=256/ASN);
* apply only evidence-backed integer gain candidates (trunc / nearest);
* compare the DNG WhiteLevel ceiling against the 14-bit B2Y ceiling 16383;
* fit nuisance downstream color/tone only on non-highlight patches;
* score held-out bright patches where the ceiling choice can actually matter.

A result can support a software-parity headroom choice.  It cannot prove the
hidden B2Y multiplier, its exact Bayer-domain placement, or its rounding rule.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import rawpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m10r_reference_order_fit import alignment_search

B2Y_14BIT_MAX = 16383.0
UNITY_Q8 = 256.0


def _numbers(v) -> list[float]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out=[]
        for x in v:
            try: out.append(float(x))
            except Exception: pass
        return out
    if isinstance(v, (int, float)):
        return [float(v)]
    return [float(x) for x in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", str(v))]


def load_meta(path: Path) -> tuple[dict, list[float]]:
    ex=json.loads(path.read_text())
    by={Path(x.get("SourceFile","")).suffix.lower():x for x in ex}
    j=by.get(".jpg",{}); d=by.get(".dng",{})
    req=["Make","Model","SerialNumber","ImageUniqueID","DateTimeOriginal","ExposureTime","ISO","FocalLength"]
    identity=all(k in j and k in d and j[k]==d[k] for k in req)
    defaults=all(j.get(k)==0 for k in ("Contrast","Saturation","Sharpness"))
    asn=_numbers(d.get("AsShotNeutral"))
    if len(asn)>=3:
        asn=asn[:3]
    return {"identity_supported":identity,"default_jpeg_controls":defaults,
            "jpg":{k:j.get(k) for k in req+["FNumber","Contrast","Saturation","Sharpness","WhiteBalance"]},
            "dng":{k:d.get(k) for k in req+["AsShotNeutral","WhiteLevel","BlackLevel"]}}, asn


def q8_from_asn(asn: list[float], rawpy_wb: np.ndarray) -> tuple[np.ndarray,str]:
    if len(asn)==3 and all(x>0 for x in asn):
        g=np.rint(UNITY_Q8/np.asarray(asn,dtype=np.float64)).astype(np.int32)
        return g,"DNG AsShotNeutral -> round(256/ASN)"
    w=np.asarray(rawpy_wb,dtype=np.float64).ravel()
    if len(w)>=4 and w[1]>0:
        rgb=np.array([w[0],w[1],w[2]],dtype=np.float64)/w[1]
        return np.rint(rgb*UNITY_Q8).astype(np.int32),"rawpy camera_whitebalance normalized to G -> round(*256)"
    raise RuntimeError("cannot derive WB triplet")


def wb_apply(x: np.ndarray, gains: np.ndarray, rounding: str, ceiling: float) -> np.ndarray:
    # x is native-code-scale post-demosaic camera RGB proxy.
    prod=x.astype(np.float64)*gains.reshape(1,1,3)
    if rounding=="trunc":
        y=np.floor(prod/UNITY_Q8)
    elif rounding=="nearest":
        y=np.floor((prod+UNITY_Q8/2.0)/UNITY_Q8)
    else:
        raise ValueError(rounding)
    return np.clip(y,0.0,ceiling)


def feats(x: np.ndarray) -> np.ndarray:
    # Quadratic nuisance model.  Same basis for every candidate; trained only on
    # midtones so it cannot restore information lost by candidate highlight clip.
    r,g,b=x[:,0],x[:,1],x[:,2]
    return np.column_stack([np.ones(len(x)),r,g,b,r*r,g*g,b*b,r*g,r*b,g*b])


def fit_eval(x: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray) -> dict:
    A=feats(x)
    coef=np.linalg.lstsq(A[train],y[train],rcond=None)[0]
    pred=np.clip(A@coef,0.0,1.0)
    err=pred[test]-y[test]
    rmse=float(np.sqrt(np.mean(err*err)))
    mae=float(np.mean(np.abs(err)))
    ps=pred[test].sum(1,keepdims=True); ys=y[test].sum(1,keepdims=True)
    pc=np.divide(pred[test],ps,out=np.zeros_like(pred[test]),where=ps>1e-9)
    yc=np.divide(y[test],ys,out=np.zeros_like(y[test]),where=ys>1e-9)
    chroma_mae=float(np.mean(np.abs(pc-yc)))
    return {"rgb_rmse":rmse,"rgb_mae":mae,"chromaticity_mae":chroma_mae,
            "train_count":int(train.sum()),"test_count":int(test.sum())}


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--jpg",type=Path,required=True)
    ap.add_argument("--dng",type=Path,required=True)
    ap.add_argument("--metadata-json",type=Path,required=True)
    ap.add_argument("--sample",required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()

    meta,asn=load_meta(args.metadata_json)
    with Image.open(args.jpg) as im:
        jpg=np.asarray(ImageOps.exif_transpose(im).convert("RGB"),dtype=np.uint8)
    jh,jw=jpg.shape[:2]

    with rawpy.imread(str(args.dng)) as r:
        raw_wb=np.asarray(r.camera_whitebalance,dtype=np.float64)
        white=float(r.white_level)
        raw_flip=int(r.sizes.flip)
        pattern=None if r.raw_pattern is None else r.raw_pattern.copy()
        # Force identity WB while retaining rawpy's demosaic/black handling.
        rgb16=r.postprocess(user_wb=[1.0,1.0,1.0,1.0],use_auto_wb=False,use_camera_wb=False,
                            no_auto_bright=True,gamma=(1,1),output_bps=16,
                            output_color=rawpy.ColorSpace.raw)
    rgb=rgb16.astype(np.float32)*(white/65535.0)
    del rgb16

    proxy=rgb[:,:,1]
    oriented_g,scores=alignment_search(proxy,jpg)
    best_score,k,dx,dy=scores[0]
    # Apply exactly the orientation selected by the green alignment to all RGB.
    oriented_rgb=np.rot90(rgb,k)
    rh,rw=oriented_rgb.shape[:2]
    if oriented_rgb.shape[:2] != oriented_g.shape:
        raise RuntimeError("RGB/green orientation mismatch")
    rcrop=oriented_rgb[dy:dy+jh,dx:dx+jw,:]
    if rcrop.shape[:2] != (jh,jw):
        raise RuntimeError(f"crop mismatch {rcrop.shape} vs {(jh,jw)}")

    gains, gain_source=q8_from_asn(asn,raw_wb)
    unclipped=rcrop.astype(np.float64)*gains.reshape(1,1,3)/UNITY_Q8

    block=48; step=72; margin=96
    rows=[]
    for y0 in range(margin,jh-margin-block+1,step):
        for x0 in range(margin,jw-margin-block+1,step):
            jb=jpg[y0:y0+block,x0:x0+block].astype(np.float64)/255.0
            rb=rcrop[y0:y0+block,x0:x0+block].astype(np.float64)
            ub=unclipped[y0:y0+block,x0:x0+block]
            jmean=jb.reshape(-1,3).mean(0); rmean=rb.reshape(-1,3).mean(0); umean=ub.reshape(-1,3).mean(0)
            jlum=0.2126*jb[:,:,0]+0.7152*jb[:,:,1]+0.0722*jb[:,:,2]
            texture=float(jlum.std())
            rows.append((rmean,umean,jmean,texture))

    # Reject highly textured blocks; preserve color rather than selecting neutrals.
    rows=[r for r in rows if r[3] <= 0.12]
    if not rows:
        raise RuntimeError("no usable patches")
    raw_mean=np.asarray([r[0] for r in rows],dtype=np.float64)
    umean=np.asarray([r[1] for r in rows],dtype=np.float64)
    jmean=np.asarray([r[2] for r in rows],dtype=np.float64)

    # Training is safely below either candidate ceiling. Test is explicitly the
    # region where at least one WB-amplified channel approaches/exceeds DNG white.
    umax=umean.max(1)
    train=(umax < white*0.72) & (jmean.max(1) < 0.92) & (jmean.mean(1) > 0.02)
    test=(umax > white*0.92) & (jmean.mean(1) > 0.04) & (jmean.min(1) < 0.995)

    result={
      "sample":args.sample,
      "metadata":meta,
      "alignment":{"score":float(best_score),"rot90_k":int(k),"dx":int(dx),"dy":int(dy),"rawpy_flip":raw_flip},
      "raw":{"white_level":white,"b2y_14bit_max":B2Y_14BIT_MAX,
             "pattern":None if pattern is None else pattern.tolist(),
             "identity_wb_proxy":"rawpy linear camera-space RGB, user_wb=[1,1,1,1], normalized by white_level/65535"},
      "wb":{"asn":asn,"rawpy_camera_whitebalance":raw_wb.tolist(),"gain_q8_rgb":gains.tolist(),"gain_source":gain_source,
            "unity_code":256,"known_driver_limit_exclusive":2048},
      "patches":{"usable":len(rows),"train":int(train.sum()),"test":int(test.sum()),
                 "unclipped_max_range":[float(umax.min()),float(umax.max())]},
      "fits":{},
    }

    if train.sum() < 24 or test.sum() < 10:
        result["error"]="insufficient train/test highlight patches"
    else:
        for ceiling_name,ceiling in (("dng_white",white),("b2y_14bit",B2Y_14BIT_MAX)):
            for rounding in ("trunc","nearest"):
                y=wb_apply(rcrop,gains,rounding,ceiling)
                # Patch means after candidate integer gain and clipping.
                vals=[]
                for y0 in range(margin,jh-margin-block+1,step):
                    for x0 in range(margin,jw-margin-block+1,step):
                        jb=jpg[y0:y0+block,x0:x0+block].astype(np.float64)/255.0
                        jlum=0.2126*jb[:,:,0]+0.7152*jb[:,:,1]+0.0722*jb[:,:,2]
                        if float(jlum.std()) <= 0.12:
                            vals.append(y[y0:y0+block,x0:x0+block].reshape(-1,3).mean(0)/ceiling)
                x=np.asarray(vals,dtype=np.float64)
                if len(x)!=len(jmean):
                    raise RuntimeError("patch reconstruction mismatch")
                result["fits"][f"{ceiling_name}|{rounding}"]=fit_eval(x,jmean,train,test)

        for rounding in ("trunc","nearest"):
            a=result["fits"][f"dng_white|{rounding}"]["rgb_rmse"]
            b=result["fits"][f"b2y_14bit|{rounding}"]["rgb_rmse"]
            result.setdefault("headroom_delta",{})[rounding]=a-b  # positive => 14-bit better
        for ceiling_name in ("dng_white","b2y_14bit"):
            t=result["fits"][f"{ceiling_name}|trunc"]["rgb_rmse"]
            n=result["fits"][f"{ceiling_name}|nearest"]["rgb_rmse"]
            result.setdefault("rounding_delta",{})[ceiling_name]=n-t  # positive => trunc better

    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
