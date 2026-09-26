#!/usr/bin/env python3
"""Score a predeclared constant-k Y_BLEND family against same-capture M10-R JPEG/DNG pairs.

This is a family falsification test, not a renderer tuner. No exposure, WB, matrix,
tone, gamma, affine, or per-scene parameter is fitted. Geometry uses the frozen
RAW/JPEG alignment oracle.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import rawpy
from m10r_reference_order_fit import alignment_search,metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference,metrics

PAT=re.compile(r"k_(\d{3})\.ppm$")

def load(p:Path)->np.ndarray:
    with Image.open(p) as im:return np.asarray(im.convert("RGB"),dtype=np.uint8)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--jpg",type=Path,required=True)
    ap.add_argument("--dng",type=Path,required=True)
    ap.add_argument("--render-dir",type=Path,required=True)
    ap.add_argument("--sample",required=True)
    ap.add_argument("--metadata-json",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    files=[]
    for p in sorted(a.render_dir.glob("k_*.ppm")):
        m=PAT.match(p.name)
        if m:files.append((int(m.group(1))/100.0,p))
    if len(files)!=21 or [round(x[0],2) for x in files]!=[round(i*.05,2) for i in range(21)]:
        raise RuntimeError(f"unexpected k grid: {[x[0] for x in files]}")

    with Image.open(a.jpg) as im:
        jpg=np.asarray(ImageOps.exif_transpose(im).convert("RGB"),dtype=np.uint8)
    with rawpy.imread(str(a.dng)) as r:
        z=r.postprocess(use_camera_wb=True,no_auto_bright=True,gamma=(1,1),
                        output_bps=16,output_color=rawpy.ColorSpace.raw)
        white=float(r.white_level);flip=int(r.sizes.flip)
    proxy=z[...,1].astype(np.float32)*(white/65535.0);del z
    oriented,scores=alignment_search(proxy,jpg)
    score,rot,dx,dy=scores[0];rh,rw=oriented.shape;jh,jw=jpg.shape[:2]

    rows={}
    cmp_shape=None
    for k,p in files:
        cand=load(p)
        cand=crop_to_reference(cand,rot,dx,dy,rw,rh,jw,jh)
        h,w=cand.shape[:2]
        ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
        if h>12 and w>12:cand,ref=cand[3:-3,3:-3],ref[3:-3,3:-3]
        if cmp_shape is None:cmp_shape=cand.shape
        elif cand.shape!=cmp_shape:raise RuntimeError("candidate crop geometry changed")
        rows[f"{k:.2f}"]=metrics(cand,ref)

    primary=[
        ("colourful_rgb_rmse",lambda q:q["bins"]["colourful_pixels"]["rgb_rmse"]),
        ("saturation_error",lambda q:q["saturation_error_abs_mean"]),
        ("delta_e76",lambda q:q["delta_e76_mean"]),
        ("hue_error",lambda q:q["hue_error_deg_mean"]),
        ("encoded_rgb_rmse",lambda q:q["encoded_rgb_rmse"]),
        ("luma_rmse",lambda q:q["luma_rmse"]),
    ]
    best={}
    for name,fn in primary:
        vals=[(float(k),fn(v)) for k,v in rows.items() if fn(v) is not None]
        best[name]=min(vals,key=lambda x:x[1])[0] if vals else None

    out={
      "schema":"M10R_YBLEND_REFERENCE1A_SAMPLE_V1",
      "sample":a.sample,
      "metadata":metadata_status(a.metadata_json),
      "fit_family":"constant-k chroma carrier scale = 1 + k*(mappedY/inputY - 1)",
      "k_grid":[round(i*.05,2) for i in range(21)],
      "fit_freedom":"ONLY offline predeclared k grid; no exposure/WB/matrix/tone/gamma/affine/per-scene image fit",
      "pipeline":"CA9 neutral guard -> Leica internal RGB -> exact YC 0x0C -> MEDIUM -> DG(Y) -> k-family CbCr -> exact YC inverse -> corrected factory sRGB CC1 -> sRGB publication",
      "firmware_claim":False,
      "alignment":{"score":float(score),"rot90_k":int(rot),"dx":int(dx),"dy":int(dy),
                   "rawpy_flip":flip,"raw_oriented":[rw,rh],"jpeg":[jw,jh],
                   "comparison":[int(cmp_shape[1]),int(cmp_shape[0])]},
      "best_k_by_metric":best,
      "metrics":rows,
    }
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"sample":a.sample,"best_k_by_metric":best,"alignment":out["alignment"]},indent=2))
    return 0
if __name__=="__main__":raise SystemExit(main())
